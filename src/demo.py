"""One-command demo: Claude models x course MergeGen x dataset on the same conflicts.

Runs compare.py once per Claude model (CSV per model in results/), then prints one summary
table (all conflicts and only those within the MergeGen length limits), the pairwise
agreement, time, tokens and cost, and a few conflicts where the tools disagree.

Example (from the mergegen-llm folder):
    python3 src/demo.py --run ../ase-merge --name java100 \
        --models claude-opus-5-5 claude-haiku-5-5 \
        --mergegen-jsonl ../ase-merge/OUTPUT/mergegen_course/results.jsonl \
        --mergegen-limits ../ase-merge/OUTPUT/mergegen_course/limits.jsonl
"""
import argparse
import csv
import subprocess
import sys
from pathlib import Path

from compare import norm, wilson, mcnemar_exact

HERE = Path(__file__).resolve().parent
# USD per million tokens (input, output), Anthropic API list prices (docs cached 2026-10-06)
PRICES = {"claude-opus-5-5": (4.00, 20.00), "claude-haiku-5-5": (0.10, 0.50),
          "claude-sonnet-5-5": (2.00, 10.00)}
csv.field_size_limit(sys.maxsize)


def pct(k, n):
    if not n:
        return "-"
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {k / n:.0%} ({lo:.0%}-{hi:.0%})"


def is_true(v):
    return v == "True"


def short(text, lines=8):
    rows = text.strip("\n").splitlines() or ["(empty)"]
    cut = rows[:lines] + ([f"... (+{len(rows) - lines} lines)"] if len(rows) > lines else [])
    return "\n".join("      " + r for r in cut)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True, help="ase-merge run folder (RAW_DATA/, OUTPUT/)")
    p.add_argument("--name", default="demo", help="tag for the CSV names")
    p.add_argument("--models", nargs="+", default=["claude-opus-5-5", "claude-haiku-5-5"])
    p.add_argument("--mergegen-jsonl", required=True)
    p.add_argument("--mergegen-limits")
    p.add_argument("--examples", type=int, default=3, help="disagreement examples to show")
    args = p.parse_args()

    data = {}
    for m in args.models:
        out = Path("results") / f"compare-{args.name}-{m}.csv"
        cmd = [sys.executable, str(HERE / "compare.py"), "--run", args.run, "--model", m,
               "--mergegen-jsonl", args.mergegen_jsonl, "--out", str(out)]
        if args.mergegen_limits:
            cmd += ["--mergegen-limits", args.mergegen_limits]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        with out.open(encoding="utf-8") as f:
            data[m] = {int(r["index"]): r for r in csv.DictReader(f)}

    # only conflicts that every tool answered
    common = sorted(set.intersection(*(set(i for i, r in d.items() if r["mergegen_eq_dataset"] != "")
                                       for d in data.values())))
    first = data[args.models[0]]
    inside = [i for i in common if is_true(first[i]["within_mergegen_limits"])]
    n = len(common)

    print(f"\n=== {n} Java conflicts, same conflicts for every tool ===")
    print("'Equal' = exact match with the developer resolution after collapsing whitespace.")
    print(f"{'tool':<18}{'equal to dataset (all)':<30}{'within MergeGen limits':<30}"
          f"{'mean time':<12}{'tokens in/out':<18}{'cost (USD)'}")
    for m in args.models:
        d = data[m]
        k = sum(is_true(d[i]["claude_eq_dataset"]) for i in common)
        ki = sum(is_true(d[i]["claude_eq_dataset"]) for i in inside)
        t = sum(float(d[i]["time_s"]) for i in common) / n
        tin = sum(int(d[i]["input_tokens"]) for i in common)
        tout = sum(int(d[i]["output_tokens"]) for i in common)
        pin, pout = PRICES.get(m, (float("nan"), float("nan")))
        cost = tin * pin / 1e6 + tout * pout / 1e6
        print(f"{m:<18}{pct(k, n):<30}{pct(ki, len(inside)):<30}{t:>6.1f}s API  "
              f"{tin}/{tout:<10}{cost:.2f} ({cost / n:.4f}/conflict)")
    k = sum(is_true(first[i]["mergegen_eq_dataset"]) for i in common)
    ki = sum(is_true(first[i]["mergegen_eq_dataset"]) for i in inside)
    t = sum(float(first[i]["mergegen_time_s"]) for i in common) / n
    print(f"{'MergeGen (course)':<18}{pct(k, n):<30}{pct(ki, len(inside)):<30}{t:>6.1f}s CPU  "
          f"{'-':<18}0 (local)")
    print(f"(95% Wilson CI in parentheses; {len(inside)} of {n} conflicts fit the MergeGen limits "
          "of 500 input / 200 output tokens)")

    print("\n=== Each Claude model vs MergeGen (all conflicts) ===")
    for m in args.models:
        d = data[m]
        c = {i: is_true(d[i]["claude_eq_dataset"]) for i in common}
        g = {i: is_true(d[i]["mergegen_eq_dataset"]) for i in common}
        both = sum(c[i] and g[i] for i in common)
        oc = sum(c[i] and not g[i] for i in common)
        og = sum(g[i] and not c[i] for i in common)
        same = sum(is_true(d[i]["claude_eq_mergegen"]) for i in common)
        print(f"{m:<18} both right {both:>3} | only Claude {oc:>3} | only MergeGen {og:>3} | "
              f"neither {n - both - oc - og:>3} | same answer {same:>3} | McNemar p = {mcnemar_exact(oc, og):.4f}")
    if len(args.models) > 1:
        a, b = args.models[:2]
        same = sum(norm(data[a][i]["resolution_claude"]) == norm(data[b][i]["resolution_claude"]) for i in common)
        print(f"{a} and {b} give the same answer in {same}/{n}")

    if args.examples:
        m = args.models[0]
        d = data[m]
        groups = [
            (f"{m} right, MergeGen wrong",
             [i for i in common if is_true(d[i]["claude_eq_dataset"]) and not is_true(d[i]["mergegen_eq_dataset"])]),
            (f"MergeGen right, {m} wrong",
             [i for i in common if is_true(d[i]["mergegen_eq_dataset"]) and not is_true(d[i]["claude_eq_dataset"])]),
            ("both wrong",
             [i for i in common if not is_true(d[i]["claude_eq_dataset"]) and not is_true(d[i]["mergegen_eq_dataset"])]),
        ]
        print(f"\n=== Disagreement examples ({m}) ===")
        for title, idx in groups:
            for i in idx[: max(1, args.examples // len(groups))]:
                r = d[i]
                print(f"\n--- conflict {i}: {title} ---")
                for label, key in (("A (with context)", "scenario_a"), ("B (with context)", "scenario_b"),
                                   ("dataset (developer)", "resolution_dataset"),
                                   ("MergeGen (context + region)", "resolution_mergegen"),
                                   (m, "resolution_claude")):
                    print(f"  {label}:")
                    print(short(r[key]))

    print("\nSetup: Claude via API with adaptive thinking, effort 'medium', same prompt for every model;"
          "\nno temperature/top_p/top_k sent (rejected by the current Claude models, per the API docs)."
          "\nMergeGen: course model best_model.pt (CodeT5-small) on CPU, beam 3. Its answer has the"
          "\ncontext lines around the region, so the same context is added to the dataset resolution."
          "\nMergeGen CPU time and Claude API latency are not directly comparable.")


if __name__ == "__main__":
    main()
