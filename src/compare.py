"""Compare Claude, MergeGen and the dataset on the same conflicts of an archived run.

Reads a run folder produced by the ase-merge fork (e.g. runs/toy400-java):
  RAW_DATA/raw_data               [bases, as, bs, resolutions]
  RAW_DATA/raw_data_ids.json      language per conflict (optional)
  all_index                       split -> conflict indexes
  OUTPUT/test_OUTPUT/SUCCEED|FAIL one file per MergeGen test example (MergeGen output),
                                  or --mergegen-jsonl from run_mergegen_infer.py
  OUTPUT/claude/<model>/<split>/results.jsonl   Claude output, time and tokens

Example:
    python3 src/compare.py --run ../ase-merge/runs/toy400-java --model claude-opus-5-5
Writes results/compare-<run>-<model>.csv and prints the summary.

"Equal" = same text after collapsing whitespace (' '.join(s.split())), as in MergeGen.
MergeGen is only evaluated on the test split.

The course MergeGen model (--mergegen-jsonl) answers the conflict region WITH the context
lines around it, while the dataset resolution and Claude's answer are only the region. So,
for MergeGen, the same context (src/conflict_context.py) is put around the dataset resolution
and around Claude's answer before comparing (--mergegen-context-lines 0 turns this off).
With --mergegen-limits (from mergegen_limits.py), the comparison is also shown only for the
conflicts within the MergeGen length limits (500 input / 200 output tokens).
"""
import argparse
import csv
import json
import math
from pathlib import Path

from conflict_context import split_context, with_context

SEP = "---------------------------------"


def norm(s: str) -> str:
    return " ".join(s.split())


def wilson(k: int, n: int, z: float = 1.96):
    """95% Wilson confidence interval for a proportion k/n."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def mcnemar_exact(only_a: int, only_b: int) -> float:
    """Two-sided exact McNemar test (binomial, p=0.5) on the discordant pairs."""
    n = only_a + only_b
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(only_a, only_b) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def fmt(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    return f"{k}/{n} ({k / n:.1%}, 95% CI {lo:.1%}-{hi:.1%})" if n else "0/0"


def read_mergegen(run: Path) -> dict:
    """index -> MergeGen output text, from OUTPUT/test_OUTPUT/{SUCCEED,FAIL}/<index>."""
    out = {}
    for sub in ("SUCCEED", "FAIL"):
        d = run / "OUTPUT" / "test_OUTPUT" / sub
        if not d.exists():
            continue
        for f in d.iterdir():
            parts = f.read_text(encoding="utf-8").split(SEP + "\n")
            text = parts[1] if len(parts) > 1 else ""
            out[int(f.name)] = text.removeprefix("output:\n").rstrip("\n")
    return out


def print_paired(both: list, title: str):
    """Claude x MergeGen x dataset on the conflicts both tools answered."""
    m = len(both)
    print(f"--- {title} ---")
    if not m:
        return
    cds = sum(r["claude_eq_dataset"] for r in both)
    md = sum(r["mergegen_eq_dataset"] for r in both)
    cm = sum(r["claude_eq_mergegen"] for r in both)
    only_c = sum(r["claude_eq_dataset"] and not r["mergegen_eq_dataset"] for r in both)
    only_m = sum(r["mergegen_eq_dataset"] and not r["claude_eq_dataset"] for r in both)
    both_ok = sum(r["claude_eq_dataset"] and r["mergegen_eq_dataset"] for r in both)
    print(f"Claude   = dataset : {fmt(cds, m)}")
    print(f"MergeGen = dataset : {fmt(md, m)}")
    print(f"Claude   = MergeGen: {cm}/{m}")
    print(f"both right {both_ok} | only Claude {only_c} | only MergeGen {only_m} | neither {m - both_ok - only_c - only_m}")
    print(f"paired exact McNemar test (only Claude vs only MergeGen): p = {mcnemar_exact(only_c, only_m):.4f}")
    mt = [r["mergegen_time_s"] for r in both if r["mergegen_time_s"] != ""]
    if mt:
        print(f"MergeGen time (local CPU): mean {sum(mt) / len(mt):.2f}s per conflict")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True, help="run folder, e.g. runs/toy400-java")
    p.add_argument("--model", default="claude-opus-5-5")
    p.add_argument("--split", default="test")
    p.add_argument("--mergegen-jsonl", help="MergeGen outputs from run_mergegen_infer.py "
                   "(instead of OUTPUT/test_OUTPUT; then any split works)")
    p.add_argument("--mergegen-context-lines", type=int, default=2,
                   help="context lines the MergeGen output carries around the region (0: none)")
    p.add_argument("--mergegen-limits", help="limits.jsonl from mergegen_limits.py")
    p.add_argument("--out", help="CSV path (default: results/compare-<run>-<model>.csv)")
    args = p.parse_args()

    run = Path(args.run)
    bases, a_s, b_s, refs = json.loads((run / "RAW_DATA/raw_data").read_text(encoding="utf-8"))
    ids_path = run / "RAW_DATA/raw_data_ids.json"
    langs = [i[0] for i in json.loads(ids_path.read_text(encoding="utf-8"))] if ids_path.exists() else None
    claude_path = run / "OUTPUT/claude" / args.model / args.split / "results.jsonl"
    claude = {}
    for line in claude_path.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        claude[r["index"]] = r
    mergegen_time = {}
    if args.mergegen_jsonl:
        mergegen = {}
        for line in Path(args.mergegen_jsonl).read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if not r.get("error"):
                mergegen[r["index"]] = r["output"]
                mergegen_time[r["index"]] = r.get("time_s", "")
    else:
        mergegen = read_mergegen(run) if args.split == "test" else {}
    limits = {}
    if args.mergegen_limits:
        for line in Path(args.mergegen_limits).read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            limits[r["index"]] = r

    rows = []
    for i in sorted(claude):
        c = claude[i]
        ref = norm(refs[i])
        c_out = norm(c["output"])
        m_out = norm(mergegen[i]) if i in mergegen else None
        before, after = (split_context(bases[i], a_s[i], b_s[i], args.mergegen_context_lines)
                         if args.mergegen_jsonl and args.mergegen_context_lines else ("", ""))
        m_ref = norm(with_context(before, refs[i], after))
        c_ctx = norm(with_context(before, c["output"], after))
        lim = limits.get(i, {})
        rows.append({
            "index": i, "lang": langs[i] if langs else "",
            "scenario_base": bases[i], "scenario_a": a_s[i], "scenario_b": b_s[i],
            "resolution_dataset": refs[i],
            "resolution_mergegen": mergegen.get(i, ""), "resolution_claude": c["output"],
            "claude_eq_dataset": c_out == ref,
            "mergegen_eq_dataset": (m_out == m_ref) if m_out is not None else "",
            "claude_eq_mergegen": (c_ctx == m_out) if m_out is not None else "",
            "time_s": c.get("time_s", ""), "input_tokens": c["input_tokens"],
            "output_tokens": c["output_tokens"], "model": c.get("model", ""),
            "claude_parse_error": c.get("parse_error", ""), "claude_stop_reason": c.get("stop_reason", ""),
            "mergegen_time_s": mergegen_time.get(i, ""),
            "conflict_tokens": lim.get("conflict_tokens", ""),
            "reference_tokens": lim.get("reference_tokens", ""),
            "within_mergegen_limits": lim.get("within_limits", ""),
        })

    out = Path(args.out) if args.out else Path("results") / f"compare-{run.name}-{args.model}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    n = len(rows)
    cd = sum(r["claude_eq_dataset"] for r in rows)
    print(f"{n} conflicts with a Claude answer ({args.split}), model asked: {args.model}")
    models = sorted({r["model"] for r in rows if r["model"]})
    print(f"models that actually answered: {', '.join(models) or 'unknown'}"
          + ("  <-- more than one: fallback was used" if len(models) > 1 else ""))
    perr = sum(1 for r in rows if r["claude_parse_error"] is True)
    refu = sum(1 for r in rows if r["claude_stop_reason"] == "refusal")
    print(f"Claude parse errors: {perr}, refusals: {refu} (both count as 'different')")
    print(f"Claude   = dataset : {fmt(cd, n)}")
    both = [r for r in rows if r["mergegen_eq_dataset"] != ""]
    if both:
        print_paired(both, f"Same {len(both)} conflicts for both tools (the fair comparison)")
        inside = [r for r in both if r["within_mergegen_limits"] is True]
        if limits:
            print_paired(inside, f"Only the {len(inside)} of them within the MergeGen limits "
                                 "(500 input / 200 output tokens)")
    times = [r["time_s"] for r in rows if r["time_s"] != ""]
    if times:
        print(f"Claude time (API call): total {sum(times):.1f}s, mean {sum(times) / len(times):.2f}s per call")
    print(f"Claude tokens: input {sum(r['input_tokens'] for r in rows)}, output {sum(r['output_tokens'] for r in rows)}")
    print("Note: CPU time of MergeGen and API latency of Claude are not directly comparable.")
    print(f"saved {out}")


if __name__ == "__main__":
    main()
