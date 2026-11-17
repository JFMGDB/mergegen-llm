"""Resolve the conflicts of a run folder with Claude through the Anthropic API.

Reads <run>/RAW_DATA/raw_data, <run>/RAW_DATA/raw_data_ids.json and <run>/all_index (written by
prepare_mergebert.py or mine_conflicts.py). The prompt is in prompts/system.txt and
prompts/conflict.txt: the conflict region of each side in diff3 form, with the context lines
apart, and the answer between <resolution> tags. The API key comes from ANTHROPIC_API_KEY, in the
environment or in a .env file at the repository root.

Output in <run>/OUTPUT/claude/<model>/<split>/:
  results.jsonl  one line per conflict (answer, match, tokens, time); resumable, conflicts that
                 failed with an API error are tried again on the next run
  summary.json   accuracy, tokens and total time

Match = answer and developer resolution equal after collapsing whitespace (' '.join(s.split())).
The models used reject temperature, top_p and top_k, so none is sent: run each model several
times and rename the output folder to <model>-r<k> after each run (see summary.py).

Example (from the repository root):
  python3 src/run_claude.py --run ../datasets/java-2m --model claude-opus-5-5 --workers 4
"""
import argparse
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from conflict_context import split_context

ROOT = Path(__file__).resolve().parent.parent
SYSTEM = (ROOT / "prompts/system.txt").read_text(encoding="utf-8").rstrip("\n")
PROMPT = (ROOT / "prompts/conflict.txt").read_text(encoding="utf-8").rstrip("\n")
RESOLUTION_RE = re.compile(r"<resolution>(.*?)</resolution>", re.S)

# variables already set in the environment take precedence over the .env file
load_dotenv(ROOT / ".env")


def normalize(s):
    return " ".join(s.split())


def build_prompt(lang, base, a, b):
    """Prompt for one conflict: context lines apart, each side's region between diff3 markers."""
    before, after = split_context(base, a, b)
    n_before, n_after = len(before.splitlines()), len(after.splitlines())
    chunks = []
    for v in (base, a, b):
        lines = v.splitlines(keepends=True)
        chunk = "".join(lines[n_before:len(lines) - n_after])
        # each region ends with a newline, so the markers stay on their own lines
        chunks.append(chunk if not chunk or chunk.endswith("\n") else chunk + "\n")
    c_base, c_a, c_b = chunks
    return PROMPT.format(lang=lang, before=before or "(none)\n", after=after or "(none)\n",
                         base=c_base, a=c_a, b=c_b)


def resolve(client, model, effort, lang, base, a, b):
    start = time.perf_counter()
    response = client.beta.messages.create(
        model=model,
        max_tokens=16000,
        system=SYSTEM,
        messages=[{"role": "user", "content": build_prompt(lang, base, a, b)}],
        output_config={"effort": effort},
        # if the safety classifiers refuse by mistake, the API retries on another model
        # instead of returning the refusal
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    elapsed = time.perf_counter() - start
    text = "".join(blk.text for blk in response.content if blk.type == "text")
    found = RESOLUTION_RE.findall(text)
    return {
        "output": found[-1].strip("\n") if found else "",
        "parse_error": not found,
        "stop_reason": response.stop_reason,
        "model": response.model,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "time_s": round(elapsed, 3),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--run", required=True, help="folder with RAW_DATA/ and all_index")
    p.add_argument("--split", default="test", choices=["test", "valid"])
    p.add_argument("--limit", type=int, help="only the first N conflicts of the split")
    p.add_argument("--model", default="claude-opus-5-5")
    p.add_argument("--effort", default="medium", choices=["low", "medium", "high", "xhigh", "max"])
    p.add_argument("--workers", type=int, default=4, help="parallel requests")
    args = p.parse_args()

    run = Path(args.run)
    all_base, all_a, all_b, all_res = json.loads((run / "RAW_DATA/raw_data").read_text(encoding="utf-8"))
    ids_path = run / "RAW_DATA/raw_data_ids.json"
    langs = [i[0] for i in json.loads(ids_path.read_text(encoding="utf-8"))] if ids_path.exists() else None
    split_index = json.loads((run / "all_index").read_text())[args.split]
    if args.limit:
        split_index = split_index[:args.limit]

    out = run / "OUTPUT/claude" / args.model / args.split
    out.mkdir(parents=True, exist_ok=True)
    results_path = out / "results.jsonl"
    done = {}
    if results_path.exists():
        for line in open(results_path, encoding="utf-8"):
            r = json.loads(line)
            done[r["index"]] = r
    todo = [i for i in split_index if i not in done]
    print(f"{args.split}: {len(split_index)} conflicts, {len(done)} already solved, {len(todo)} to solve "
          f"with {args.model} (effort {args.effort})", flush=True)

    # keys scoped to an organization need the anthropic-workspace-id header
    workspace_id = os.environ.get("ANTHROPIC_WORKSPACE_ID")
    client = anthropic.Anthropic(
        default_headers={"anthropic-workspace-id": workspace_id} if workspace_id else None)
    lock = threading.Lock()

    def work(i):
        r = resolve(client, args.model, args.effort, langs[i] if langs else "unknown",
                    all_base[i], all_a[i], all_b[i])
        r["index"] = i
        r["match"] = normalize(r["output"]) == normalize(all_res[i])
        return r

    errors = 0
    with ThreadPoolExecutor(args.workers) as pool, open(results_path, "a", encoding="utf-8") as f:
        futures = {pool.submit(work, i): i for i in todo}
        for n, fut in enumerate(as_completed(futures), 1):
            i = futures[fut]
            try:
                r = fut.result()
            except anthropic.APIError as e:
                # not written: the next run tries again
                errors += 1
                print(f"  [{n}/{len(todo)}] {i}: error {type(e).__name__}: {e}", flush=True)
                continue
            with lock:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
                f.flush()
                done[i] = r
            flag = "ok" if r["match"] else ("refusal" if r["stop_reason"] == "refusal" else "fail")
            print(f"  [{n}/{len(todo)}] {i}: {flag}", flush=True)

    resolved = [i for i in split_index if i in done]
    matches = sum(done[i]["match"] for i in resolved)
    summary = {
        "model": args.model,
        "effort": args.effort,
        "split": args.split,
        "num_examples": len(split_index),
        "num_resolved": len(resolved),
        "exactly_match": matches / len(resolved) if resolved else 0.0,
        "refusals": sum(done[i]["stop_reason"] == "refusal" for i in resolved),
        "parse_errors": sum(done[i]["parse_error"] for i in resolved),
        "input_tokens": sum(done[i]["input_tokens"] for i in resolved),
        "output_tokens": sum(done[i]["output_tokens"] for i in resolved),
        "total_time_s": round(sum(done[i].get("time_s", 0) for i in resolved), 1),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"exact match: {summary['exactly_match']:.4f} ({matches}/{len(resolved)})"
          + (f"; {errors} with errors, run again to retry them" if errors else ""))
    print(f"output in {out}")


if __name__ == "__main__":
    main()
