"""Compare Claude, MergeGen and the dataset on the same conflicts of a run folder.

Reads a run folder written by prepare_mergebert.py or mine_conflicts.py:
  RAW_DATA/raw_data               [bases, as, bs, resolutions]
  RAW_DATA/raw_data_ids.json      language per conflict (optional)
  all_index                       split -> conflict indexes
  OUTPUT/claude/<model>/<split>/results.jsonl   Claude output, time and tokens (run_claude.py)
  --mergegen-jsonl                MergeGen output (run_mergegen.py); without it, one file per
                                  test example in OUTPUT/test_OUTPUT/SUCCEED|FAIL, as written by
                                  the training code of the MergeGen replication package

Example:
    python3 src/compare.py --run ../datasets/java-2m --model claude-opus-5-5-r1 \
        --mergegen-jsonl ../datasets/java-2m/OUTPUT/mergegen/results.jsonl \
        --mergegen-limits ../datasets/java-2m/OUTPUT/mergegen_course/limits.jsonl
Writes results/compare-<run>-<model>.csv and prints the summary.

"Equal" = same text after collapsing whitespace (' '.join(s.split())), as in MergeGen.
Each comparison is also shown ignoring comments (// and /* */, as in Java, JavaScript and
TypeScript), since a resolution that differs only in a comment is the same code. MergeGen
outputs a token stream without line breaks, so where a // comment ends is unknown: comparisons
with MergeGen ignore only /* */ comments. An exact match always counts as equal here too.
A third comparison ignores formatting: both texts are reduced to code tokens (identifiers,
literals, operators; comments, whitespace and line breaks dropped) and compared as sequences.
It matters most for MergeGen, whose output joins tokens where the developer broke the line
(e.g. "true)" + newline + ".expireAfterWrite" becomes "true).expireAfterWrite").
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
import re
from pathlib import Path

from conflict_context import split_context, with_context

SEP = "---------------------------------"


def norm(s: str) -> str:
    return " ".join(s.split())


def strip_comments(s: str, line_comments: bool = True) -> str:
    """Drop /* */ (and, if line_comments, //) comments, keeping string literals untouched."""
    out, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c in "'\"`":
            j = i + 1
            while j < n and s[j] != c and (c == "`" or s[j] != "\n"):
                j += 2 if s[j] == "\\" else 1
            out.append(s[i:j + 1])
            i = j + 1
        elif line_comments and s.startswith("//", i):
            j = s.find("\n", i)
            i = n if j < 0 else j
        elif s.startswith("/*", i):
            j = s.find("*/", i + 2)
            out.append(" ")
            i = n if j < 0 else j + 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def loose(s: str, line_comments: bool = True) -> str:
    return norm(strip_comments(s, line_comments))


_TOKEN_BODY = (r'/\*.*?\*/|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'|`(?:\\.|[^`\\])*`'
               r'|[A-Za-z_$][A-Za-z0-9_$]*|\d[A-Za-z0-9_.]*|\S')
_TOKEN = re.compile(r'//[^\n]*|' + _TOKEN_BODY, re.S)
_TOKEN_NO_LINE_COMMENTS = re.compile(_TOKEN_BODY, re.S)


def code_tokens(s: str, line_comments: bool = True) -> list:
    """Code tokens of s (Java, JavaScript, TypeScript), without comments and formatting."""
    rx = _TOKEN if line_comments else _TOKEN_NO_LINE_COMMENTS
    return [t for t in rx.findall(s) if not t.startswith("/*") and not (line_comments and t.startswith("//"))]


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


def print_paired(both: list, title: str, suffix: str = ""):
    """Claude x MergeGen x dataset on the conflicts both tools answered
    (suffix "_nocomments" or "_tokens" uses the comparisons that ignore comments or formatting)."""
    m = len(both)
    print(f"--- {title} ---")
    if not m:
        return
    c_ok = [r["claude_eq_dataset" + suffix] for r in both]
    m_ok = [r["mergegen_eq_dataset" + suffix] for r in both]
    cds, md = sum(c_ok), sum(m_ok)
    cm = sum(r["claude_eq_mergegen" + suffix] for r in both)
    only_c = sum(c and not g for c, g in zip(c_ok, m_ok))
    only_m = sum(g and not c for c, g in zip(c_ok, m_ok))
    both_ok = sum(c and g for c, g in zip(c_ok, m_ok))
    print(f"Claude   = dataset : {fmt(cds, m)}")
    print(f"MergeGen = dataset : {fmt(md, m)}")
    print(f"Claude   = MergeGen: {cm}/{m}")
    print(f"both right {both_ok} | only Claude {only_c} | only MergeGen {only_m} | neither {m - both_ok - only_c - only_m}")
    print(f"paired exact McNemar test (only Claude vs only MergeGen): p = {mcnemar_exact(only_c, only_m):.4f}")
    mt = [r["mergegen_time_s"] for r in both if r["mergegen_time_s"] != ""]
    if mt:
        print(f"MergeGen time (local CPU): mean {sum(mt) / len(mt):.2f}s per conflict")


def build_rows(run: Path, model: str, split: str = "test", mergegen_jsonl=None,
               mergegen_context_lines: int = 2, mergegen_limits=None) -> list:
    """One row per conflict Claude answered: the scenario, the three resolutions and the
    comparisons (see the module docstring)."""
    bases, a_s, b_s, refs = json.loads((run / "RAW_DATA/raw_data").read_text(encoding="utf-8"))
    ids_path = run / "RAW_DATA/raw_data_ids.json"
    langs = [i[0] for i in json.loads(ids_path.read_text(encoding="utf-8"))] if ids_path.exists() else None
    claude_path = run / "OUTPUT/claude" / model / split / "results.jsonl"
    claude = {}
    for line in claude_path.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        claude[r["index"]] = r
    mergegen_time = {}
    if mergegen_jsonl:
        mergegen = {}
        for line in Path(mergegen_jsonl).read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if not r.get("error"):
                mergegen[r["index"]] = r["output"]
                mergegen_time[r["index"]] = r.get("time_s", "")
    else:
        mergegen = read_mergegen(run) if split == "test" else {}
    limits = {}
    if mergegen_limits:
        for line in Path(mergegen_limits).read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            limits[r["index"]] = r

    rows = []
    for i in sorted(claude):
        c = claude[i]
        ref = norm(refs[i])
        c_out = norm(c["output"])
        m_out = norm(mergegen[i]) if i in mergegen else None
        m_loose = loose(mergegen[i], False) if i in mergegen else None
        m_tokens = code_tokens(mergegen[i], False) if i in mergegen else None
        before, after = (split_context(bases[i], a_s[i], b_s[i], mergegen_context_lines)
                         if mergegen_jsonl and mergegen_context_lines else ("", ""))
        m_ref = with_context(before, refs[i], after)
        c_ctx = with_context(before, c["output"], after)
        lim = limits.get(i, {})
        rows.append({
            "index": i, "lang": langs[i] if langs else "",
            "scenario_base": bases[i], "scenario_a": a_s[i], "scenario_b": b_s[i],
            "resolution_dataset": refs[i],
            "resolution_mergegen": mergegen.get(i, ""), "resolution_claude": c["output"],
            "claude_eq_dataset": c_out == ref,
            "mergegen_eq_dataset": (m_out == norm(m_ref)) if m_out is not None else "",
            "claude_eq_mergegen": (norm(c_ctx) == m_out) if m_out is not None else "",
            "claude_eq_dataset_nocomments": c_out == ref or loose(c["output"]) == loose(refs[i]),
            "mergegen_eq_dataset_nocomments": (m_out == norm(m_ref) or m_loose == loose(m_ref, False))
                                              if m_out is not None else "",
            "claude_eq_mergegen_nocomments": (norm(c_ctx) == m_out or loose(c_ctx, False) == m_loose)
                                             if m_out is not None else "",
            "claude_eq_dataset_tokens": c_out == ref or code_tokens(c["output"]) == code_tokens(refs[i]),
            "mergegen_eq_dataset_tokens": (m_out == norm(m_ref) or m_tokens == code_tokens(m_ref, False))
                                          if m_out is not None else "",
            "claude_eq_mergegen_tokens": (norm(c_ctx) == m_out or code_tokens(c_ctx, False) == m_tokens)
                                         if m_out is not None else "",
            "time_s": c.get("time_s", ""), "input_tokens": c["input_tokens"],
            "output_tokens": c["output_tokens"], "model": c.get("model", ""),
            "claude_parse_error": c.get("parse_error", ""), "claude_stop_reason": c.get("stop_reason", ""),
            "mergegen_time_s": mergegen_time.get(i, ""),
            "conflict_tokens": lim.get("conflict_tokens", ""),
            "reference_tokens": lim.get("reference_tokens", ""),
            "within_mergegen_limits": lim.get("within_limits", ""),
        })
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True, help="run folder, e.g. runs/toy400-java")
    p.add_argument("--model", default="claude-opus-5-5")
    p.add_argument("--split", default="test")
    p.add_argument("--mergegen-jsonl", help="MergeGen outputs from run_mergegen.py "
                   "(instead of OUTPUT/test_OUTPUT; then any split works)")
    p.add_argument("--mergegen-context-lines", type=int, default=2,
                   help="context lines the MergeGen output carries around the region (0: none)")
    p.add_argument("--mergegen-limits", help="limits.jsonl from mergegen_limits.py")
    p.add_argument("--out", help="CSV path (default: results/compare-<run>-<model>.csv)")
    args = p.parse_args()

    run = Path(args.run)
    rows = build_rows(run, args.model, args.split, args.mergegen_jsonl, args.mergegen_context_lines,
                      args.mergegen_limits)

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
    cdl = sum(r["claude_eq_dataset_nocomments"] for r in rows)
    print(f"Claude   = dataset, ignoring comments: {fmt(cdl, n)}")
    cdt = sum(r["claude_eq_dataset_tokens"] for r in rows)
    print(f"Claude   = dataset, ignoring formatting (same code tokens): {fmt(cdt, n)}")
    both = [r for r in rows if r["mergegen_eq_dataset"] != ""]
    if both:
        print_paired(both, f"Same {len(both)} conflicts for both tools (the fair comparison)")
        print_paired(both, "Same conflicts, ignoring comments", "_nocomments")
        print_paired(both, "Same conflicts, ignoring formatting (same code tokens)", "_tokens")
        inside = [r for r in both if r["within_mergegen_limits"] is True]
        if args.mergegen_limits:
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
