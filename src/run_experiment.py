"""Run the LLM over a set of conflicts and save one CSV per execution in results/.

Example:
    python src/run_experiment.py --backend cli --model sonnet --variants A B
    python src/run_experiment.py --backend mock            # offline test
"""
import argparse
import csv
import json
import re
import time
from datetime import datetime
from pathlib import Path

from backends import BACKENDS
from prompts import build_prompt

ROOT = Path(__file__).resolve().parent.parent
FIELDS = [
    "id", "difficulty", "variant", "backend", "model",
    "scenario_base", "scenario_a", "scenario_b",
    "resolution_dataset", "resolution_mergegen", "resolution_llm",
    "igual_dataset", "igual_mergegen",
    "time_s", "input_tokens", "output_tokens", "cost_usd", "attempts", "error",
]


def clean(text: str) -> str:
    """Remove markdown fences if the model added them anyway. Exact match is otherwise untouched."""
    t = text.strip("\n")
    m = re.fullmatch(r"\s*```[a-zA-Z]*\n(.*?)\n?```\s*", t, flags=re.S)
    return m.group(1) if m else t


def call_with_retry(fn, prompt, model, retries, timeout):
    last = None
    for attempt in range(1, retries + 1):
        if attempt > 1:
            time.sleep(2 ** (attempt - 1))
        try:
            start = time.perf_counter()
            out = fn(prompt, model, timeout)
            return out, time.perf_counter() - start, attempt, ""
        except Exception as e:  # noqa: BLE001 - we record any failure and retry
            last = str(e)
    return None, 0.0, retries, last


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", default=str(ROOT / "data" / "toys.json"))
    p.add_argument("--backend", choices=BACKENDS, default="cli")
    p.add_argument("--model", default="sonnet")
    p.add_argument("--variants", nargs="+", default=["A", "B"])
    p.add_argument("--mergegen", help="JSON {id: resolution} with the MergeGen output (optional)")
    p.add_argument("--retries", type=int, default=3)
    p.add_argument("--timeout", type=int, default=300)
    p.add_argument("--limit", type=int, help="only the first N conflicts")
    args = p.parse_args()

    toys = json.loads(Path(args.data).read_text(encoding="utf-8"))[: args.limit]
    mergegen = json.loads(Path(args.mergegen).read_text()) if args.mergegen else {}
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    raw_dir = ROOT / "results" / "raw" / run_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_csv = ROOT / "results" / f"run-{run_id}-{args.backend}-{args.model}.csv"
    fn = BACKENDS[args.backend]
    if args.backend == "cli":
        from backends import cli_version
        (raw_dir / "VERSION.txt").write_text(f"claude code {cli_version()}\nmodel alias: {args.model}\n")

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for toy in toys:
            for variant in args.variants:
                prompt = build_prompt(variant, toy)
                out, secs, attempts, err = call_with_retry(
                    fn, prompt, args.model, args.retries, args.timeout)
                row = {
                    "id": toy["id"], "difficulty": toy.get("difficulty", ""),
                    "variant": variant, "backend": args.backend, "model": args.model,
                    "scenario_base": toy["base"], "scenario_a": toy["a"], "scenario_b": toy["b"],
                    "resolution_dataset": toy["resolution"],
                    "resolution_mergegen": mergegen.get(toy["id"], ""),
                    "attempts": attempts, "error": err,
                }
                if out:
                    llm = clean(out["text"])
                    row.update({
                        "resolution_llm": llm,
                        "igual_dataset": llm == toy["resolution"],
                        "igual_mergegen": (llm == mergegen[toy["id"]]) if toy["id"] in mergegen else "",
                        "time_s": round(secs, 3),
                        "input_tokens": out["input_tokens"],
                        "output_tokens": out["output_tokens"],
                        "cost_usd": out["cost_usd"],
                    })
                    (raw_dir / f"{toy['id']}_{variant}.json").write_text(
                        json.dumps({"prompt": prompt, "response": out["raw"]}, indent=2, ensure_ascii=False))
                w.writerow(row)
                f.flush()  # a crash or a limit stop keeps what was already done
                print(f"{toy['id']} {variant}: {'ok' if out else 'ERROR ' + err[:80]}")
    print(f"saved {out_csv}")


if __name__ == "__main__":
    main()
