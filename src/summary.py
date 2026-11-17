"""Summary across datasets and repeated Claude runs: accuracy, consistency, cost.

Claude's sampling cannot be fixed on these models (the API rejects temperature), so each
model is run several times; each run lives in <run>/OUTPUT/claude/<model>-r<k>/. MergeGen
(beam search) is deterministic and runs once. For each dataset only the conflicts that every
run of every tool answered are counted, so all numbers in a row use the same conflicts.

Reports, per dataset: MergeGen accuracy; each Claude model's accuracy as the mean of its runs
(min-max); how many conflicts Claude got right in every run, in some runs or in none; the
paired comparison with MergeGen using Claude's majority vote across runs (with the exact
McNemar test); and tokens, cost and time per run. Only aggregate numbers are written, never
code, so the output can be versioned even for private datasets.

Example (from the mergegen-llm folder):
  python3 src/summary.py --models claude-opus-5-5 claude-sonnet-5-5 --out results/summary.md \
    --dataset "MergeBERT (MergeGen trained on it)" ../datasets/mergebert \
        ../datasets/mergebert/OUTPUT/mergegen_course_bos/results.jsonl \
        ../datasets/mergebert/OUTPUT/mergegen_course/limits.jsonl \
    --dataset "Java, last 2 months" ../datasets/java-2m \
        ../datasets/java-2m/OUTPUT/mergegen/results.jsonl ../datasets/java-2m/OUTPUT/mergegen_course/limits.jsonl
"""
import argparse
from pathlib import Path

from compare import build_rows, mcnemar_exact, wilson
from demo import PRICES


def pct(k, n):
    return f"{k / n:.1%}" if n else "-"


def ci(k, n):
    lo, hi = wilson(k, n)
    return f"{k / n:.1%} ({lo:.0%}-{hi:.0%})" if n else "-"


def runs_of(run: Path, model: str) -> list:
    return sorted(d.name for d in (run / "OUTPUT/claude").glob(f"{model}-r*") if d.is_dir())


def summarize(name, run, mergegen_jsonl, limits, models, key):
    run = Path(run)
    rows = {}  # (model, rep) -> {index: row}
    for m in models:
        for rep in runs_of(run, m):
            rows[m, rep] = {r["index"]: r for r in build_rows(run, rep, "test", mergegen_jsonl, 2, limits)}
    if not rows:
        return None
    common = set.intersection(*({i for i, r in d.items() if r["mergegen_eq_dataset"] != ""}
                                for d in rows.values()))
    common = sorted(common)
    n = len(common)
    any_rows = next(iter(rows.values()))
    mg_ok = {i: any_rows[i]["mergegen_eq_dataset" + key] for i in common}
    mg_time = [any_rows[i]["mergegen_time_s"] for i in common if any_rows[i]["mergegen_time_s"] != ""]
    out = {"name": name, "n": n, "mergegen": sum(mg_ok.values()),
           "mergegen_time": sum(mg_time) / len(mg_time) if mg_time else None, "models": {}}
    for m in models:
        reps = [r for (mm, r) in rows if mm == m]
        if not reps:
            continue
        ok = {rep: {i: rows[m, rep][i]["claude_eq_dataset" + key] for i in common} for rep in reps}
        per_rep = [sum(ok[rep].values()) for rep in reps]
        hits = {i: sum(ok[rep][i] for rep in reps) for i in common}
        majority = {i: hits[i] * 2 > len(reps) for i in common}
        both = sum(majority[i] and mg_ok[i] for i in common)
        only_c = sum(majority[i] and not mg_ok[i] for i in common)
        only_m = sum(mg_ok[i] and not majority[i] for i in common)
        tok_in = [sum(rows[m, rep][i]["input_tokens"] for i in common) for rep in reps]
        tok_out = [sum(rows[m, rep][i]["output_tokens"] for i in common) for rep in reps]
        times = [rows[m, rep][i]["time_s"] for rep in reps for i in common if rows[m, rep][i]["time_s"] != ""]
        pin, pout = PRICES.get(m, (0, 0))
        out["models"][m] = {
            "runs": len(reps), "per_run": per_rep,
            "always": sum(h == len(reps) for h in hits.values()),
            "never": sum(h == 0 for h in hits.values()),
            "majority": sum(majority.values()),
            "both": both, "only_claude": only_c, "only_mergegen": only_m,
            "neither": n - both - only_c - only_m, "p": mcnemar_exact(only_c, only_m),
            "tokens_in": sum(tok_in) / len(reps), "tokens_out": sum(tok_out) / len(reps),
            "cost": sum((ti * pin + to * pout) / 1e6 for ti, to in zip(tok_in, tok_out)) / len(reps),
            "time": sum(times) / len(times) if times else None,
        }
    return out


def report(results, models, title):
    lines = [f"## {title}", ""]
    head = "| Dataset | Conflicts | MergeGen |" + "".join(f" {m} (mean of runs, min-max) |" for m in models)
    lines += [head, "|" + "---|" * (3 + len(models))]
    for r in results:
        cells = [r["name"], str(r["n"]), ci(r["mergegen"], r["n"])]
        for m in models:
            s = r["models"].get(m)
            if not s:
                cells.append("-")
                continue
            mean = sum(s["per_run"]) / s["runs"]
            cells.append(f"{pct(mean, r['n'])} ({pct(min(s['per_run']), r['n'])}-"
                         f"{pct(max(s['per_run']), r['n'])}), {s['runs']} runs")
        lines.append("| " + " | ".join(cells) + " |")
    lines += ["", "Consistency across Claude runs and paired comparison with MergeGen "
              "(Claude = right in the majority of its runs):", "",
              "| Dataset | Model | Right in every run | In some runs | In none | Both right | "
              "Only Claude | Only MergeGen | Neither | McNemar p |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        for m, s in r["models"].items():
            some = r["n"] - s["always"] - s["never"]
            lines.append(f"| {r['name']} | {m} | {s['always']} | {some} | {s['never']} | {s['both']} | "
                         f"{s['only_claude']} | {s['only_mergegen']} | {s['neither']} | {s['p']:.4f} |")
    return lines


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--dataset", nargs=4, action="append", required=True,
                   metavar=("NAME", "RUN", "MERGEGEN_JSONL", "MERGEGEN_LIMITS"))
    p.add_argument("--models", nargs="+", default=["claude-opus-5-5", "claude-sonnet-5-5"])
    p.add_argument("--out", help="also write the tables to this Markdown file")
    args = p.parse_args()

    exact = [r for r in (summarize(*d, args.models, "") for d in args.dataset) if r]
    loose = [r for r in (summarize(*d, args.models, "_nocomments") for d in args.dataset) if r]
    lines = ["# MergeGen x Claude: summary", "",
             "'Right' = equal to the developer resolution after collapsing whitespace.", ""]
    lines += report(exact, args.models, "Exact match")
    lines += [""] + report(loose, args.models, "Ignoring comments")
    lines += ["", "## Cost and time per run", "",
              "| Dataset | Model | Input tokens | Output tokens | Cost (USD) | Claude s/call | MergeGen s/conflict (CPU) |",
              "|---|---|---|---|---|---|---|"]
    for r in exact:
        for m, s in r["models"].items():
            mg = f"{r['mergegen_time']:.2f}" if r["mergegen_time"] else "-"
            t = f"{s['time']:.2f}" if s["time"] else "-"
            lines.append(f"| {r['name']} | {m} | {s['tokens_in']:,.0f} | {s['tokens_out']:,.0f} | "
                         f"{s['cost']:.2f} | {t} | {mg} |")
    lines += ["", "Claude latency (API) and MergeGen time (local CPU) are not directly comparable."]
    text = "\n".join(lines)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
