"""Mine merge conflicts from local git clones into the MergeBERT-style raw_data format.

For every two-parent merge commit (optionally after --since), each file git reports as conflicting
is re-merged with `git merge-file --diff3`. Every conflict region becomes one example:
  base/a/b = 2 lines of context before + region of that version + 2 lines of context after
  res      = what the developer wrote for that region in the merge commit
The resolution is found by anchoring the non-conflicting text around the region in the merged
file; regions whose anchors are missing or ambiguous are dropped (like found_res_region=false).

Output (same layout prepare_toy.py writes, so run_claude.py, run_mergegen_infer.py and
compare.py work unchanged):
  <out>/RAW_DATA/raw_data            [bases, as, bs, resolutions]
  <out>/RAW_DATA/raw_data_ids.json   [language, "repo@merge:path", region index] per example
  <out>/RAW_DATA/raw_data_meta.jsonl merge date, parents and file per example
  <out>/all_index                    every example in "test"

Example:
  python3 src/mine_conflicts.py ../repos/jackson-databind ../repos/accumulo --langs Java \
      --out ../datasets/java-recent --since 2024-01-01
"""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path

LANGS = {".java": "Java", ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript",
         ".cjs": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript", ".cs": "CSharp"}
CONTEXT_LINES = 2  # same as prepare_raw_data.CONTEXT_LINES
MAX_ANCHOR = 20    # lines of surrounding text tried to make an anchor unique


def git(repo, *args, check=True):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=check)
    return r.stdout.decode("utf-8", errors="replace")


def show(repo, rev, path):
    r = subprocess.run(["git", "-C", str(repo), "show", f"{rev}:{path}"], capture_output=True)
    if r.returncode != 0 or b"\0" in r.stdout:  # missing on that side, or binary
        return None
    return r.stdout.decode("utf-8", errors="replace")


def merges(repo, since):
    args = ["rev-list", "--all", "--merges", "--min-parents=2", "--max-parents=2",
            "--format=%H %P %cI", "--no-commit-header"]
    if since:
        args.append(f"--since={since}")
    for line in git(repo, *args).splitlines():
        h, p1, p2, date = line.split()
        yield h, p1, p2, date


def conflicted(repo, p1, p2):
    """Files git reports as conflicting when re-merging p1 and p2 (empty if the merge is clean)."""
    out = git(repo, "merge-tree", "--write-tree", "--name-only", "--no-messages", p1, p2,
              check=False)
    return set(out.splitlines()[1:])


def merge_regions(base, a, b):
    """Run git merge-file --diff3 and return its output as a list of segments:
    ("clean", lines) or ("conflict", (a_lines, base_lines, b_lines))."""
    with tempfile.TemporaryDirectory() as d:
        paths = []
        for name, text in (("a", a), ("base", base), ("b", b)):
            p = Path(d) / name
            p.write_text(text, encoding="utf-8")
            paths.append(str(p))
        r = subprocess.run(["git", "merge-file", "-p", "--diff3", *paths], capture_output=True)
    lines = r.stdout.decode("utf-8", errors="replace").splitlines(keepends=True)
    segments, clean, i = [], [], 0
    while i < len(lines):
        if not lines[i].startswith("<<<<<<< "):
            clean.append(lines[i])
            i += 1
            continue
        parts, cur = [], []
        i += 1
        while i < len(lines) and not lines[i].startswith(">>>>>>> "):
            if lines[i].startswith("||||||| ") or lines[i].rstrip("\n") == "=======":
                parts.append(cur)
                cur = []
            else:
                cur.append(lines[i])
            i += 1
        parts.append(cur)
        i += 1
        if len(parts) != 3:  # unexpected marker layout (e.g. markers inside the file itself)
            return None
        segments.append(("clean", clean))
        segments.append(("conflict", tuple(parts)))
        clean = []
    segments.append(("clean", clean))
    return segments


def find_unique(hay, needle, start=0):
    """Index of needle (a list of lines) in hay at or after start, or None if absent or repeated."""
    n, hits = len(needle), []
    for i in range(start, len(hay) - n + 1):
        if hay[i:i + n] == needle:
            hits.append(i)
            if len(hits) > 1:
                return None
    return hits[0] if hits else None


def find_resolution(merged, before, after):
    """Lines of the merged file between the text before and after a conflict region.
    before/after: the clean text around the region (before[-k:] and after[:k] are tried
    as anchors for growing k). An empty before/after means the start/end of the file."""
    if before:
        start = None
        for k in range(min(CONTEXT_LINES, len(before)), min(MAX_ANCHOR, len(before)) + 1):
            pos = find_unique(merged, before[-k:])
            if pos is not None:
                start = pos + k
                break
        if start is None:
            return None
    else:
        start = 0
    if not after:
        return merged[start:]
    for k in range(min(CONTEXT_LINES, len(after)), min(MAX_ANCHOR, len(after)) + 1):
        pos = find_unique(merged, after[:k], start)
        if pos is not None:
            return merged[start:pos]
    return None


def with_newline(lines):
    text = "".join(lines)
    return text if not text or text.endswith("\n") else text + "\n"


def file_examples(base, a, b, merged):
    segments = merge_regions(base, a, b)
    if segments is None:
        return
    merged_lines = merged.splitlines(keepends=True)
    if merged_lines and not merged_lines[-1].endswith("\n"):
        merged_lines[-1] += "\n"
    if any(line.startswith(("<<<<<<< ", ">>>>>>> ")) for line in merged_lines):
        return  # developer committed the conflict markers
    for k in range(1, len(segments), 2):
        before, (ca, cbase, cb), after = segments[k - 1][1], segments[k][1], segments[k + 1][1]
        res = find_resolution(merged_lines, before, after)
        if res is None:
            continue
        ctx_before = "".join(before[-CONTEXT_LINES:])
        ctx_after = with_newline(after[:CONTEXT_LINES])
        yield (k // 2,
               ctx_before + with_newline(cbase) + ctx_after,
               ctx_before + with_newline(ca) + ctx_after,
               ctx_before + with_newline(cb) + ctx_after,
               "".join(res))


def mine(repo, since):
    repo = Path(repo).resolve()
    name = repo.name
    for h, p1, p2, date in merges(repo, since):
        bases = git(repo, "merge-base", "--all", p1, p2, check=False).split()
        if len(bases) != 1:  # criss-cross or unrelated histories: no single base
            continue
        base = bases[0]
        for path in sorted(conflicted(repo, p1, p2)):
            lang = LANGS.get(Path(path).suffix)
            if not lang:
                continue
            versions = [show(repo, rev, path) for rev in (base, p1, p2, h)]
            if any(v is None for v in versions):
                continue
            for idx, vbase, va, vb, res in file_examples(*versions):
                yield {"lang": lang, "id": f"{name}@{h[:12]}:{path}", "idx": idx,
                       "base": vbase, "a": va, "b": vb, "res": res,
                       "repo": name, "merge": h, "parents": [p1, p2], "date": date, "path": path}


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("repos", nargs="+", help="local git clones")
    p.add_argument("--out", required=True, help="run folder to create (RAW_DATA/, all_index)")
    p.add_argument("--since", help="only merges committed on or after this date (YYYY-MM-DD)")
    p.add_argument("--langs", default="Java,JavaScript,TypeScript",
                   help="comma-separated languages to keep")
    args = p.parse_args()

    keep = set(args.langs.split(","))
    examples, seen = [], set()
    for repo in args.repos:
        cur = []
        for e in mine(repo, args.since):
            # the same conflict often reappears when the branches are merged again elsewhere
            key = (e["base"], e["a"], e["b"], e["res"])
            if e["lang"] in keep and key not in seen:
                seen.add(key)
                cur.append(e)
        by_lang = {}
        for e in cur:
            by_lang[e["lang"]] = by_lang.get(e["lang"], 0) + 1
        print(f"{Path(repo).name}: {len(cur)} conflicts {by_lang}", flush=True)
        examples += cur

    out = Path(args.out)
    (out / "RAW_DATA").mkdir(parents=True, exist_ok=True)
    cols = [[e[k] for e in examples] for k in ("base", "a", "b", "res")]
    (out / "RAW_DATA/raw_data").write_text(json.dumps(cols), encoding="utf-8")
    ids = [[e["lang"], e["id"], e["idx"]] for e in examples]
    (out / "RAW_DATA/raw_data_ids.json").write_text(json.dumps(ids), encoding="utf-8")
    with open(out / "RAW_DATA/raw_data_meta.jsonl", "w", encoding="utf-8") as f:
        for e in examples:
            meta = {k: e[k] for k in ("repo", "merge", "parents", "date", "path", "idx", "lang")}
            f.write(json.dumps(meta) + "\n")
    index = {"train": [], "valid": [], "test": list(range(len(examples)))}
    (out / "all_index").write_text(json.dumps(index), encoding="utf-8")
    print(f"Total: {len(examples)} conflicts -> {out}/RAW_DATA/raw_data")


if __name__ == "__main__":
    main()
