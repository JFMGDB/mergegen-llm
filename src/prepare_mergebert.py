"""Build a run folder from the MergeBERT dataset (Zenodo 6366908), one example per conflict.

The conflicts come from the conflicting_chunks of each <id>_metadata.json in
automated-analysis-data/<language>/. For each conflict:
  base, a, b = context before + region of that version + context after
  resolution = res_region (the developer resolution of that region only)
with CONTEXT_LINES lines of context on each side, taken from lookback/lookahead. Conflicts with
no resolution found (found_res_region), whose resolved file is empty (RES_FILE_EMPTY), with
corrupted metadata or from minified files are dropped. Files are read in id order, so the
output is deterministic.

Output (the layout mine_conflicts.py also writes):
  <out>/RAW_DATA/raw_data            [bases, as, bs, resolutions]
  <out>/RAW_DATA/raw_data_ids.json   [language, file id, conflict index] per example
  <out>/all_index                    every example in "test"

Example (the first 400 Java conflicts, the MergeBERT sample used in results/):
  python3 src/prepare_mergebert.py --data ../fse2022 --langs Java --limit 400 --out ../datasets/mergebert
"""
import argparse
import json
from itertools import islice
from pathlib import Path

from conflict_context import CONTEXT_LINES

LANGS = ["Java", "CSharp", "JavaScript", "TypeScript"]


def conflicts(data: Path, lang: str):
    """Yield (id, index, base, a, b, resolution) for each valid conflict of the language."""
    d = data / "automated-analysis-data" / lang
    ids = sorted(f.name[:-len("_metadata.json")] for f in d.glob("*_metadata.json"))
    for cid in ids:
        m = json.loads((d / f"{cid}_metadata.json").read_text(encoding="utf-8", errors="replace"))
        if m.get("metadata_corrupted") or m.get("minified"):
            continue
        for k, c in enumerate(m.get("conflicting_chunks", [])):
            if not c.get("found_res_region") or c.get("label") == "RES_FILE_EMPTY":
                continue
            before = c["lookback"].replace("<START\\>", "").splitlines(keepends=True)[-CONTEXT_LINES:]
            after = c["lookahead"].replace("<END\\>", "").splitlines(keepends=True)[:CONTEXT_LINES]
            before, after = "".join(before), "".join(after)
            yield (cid, k,
                   before + c["base_contents"] + after,
                   before + c["a_contents"] + after,
                   before + c["b_contents"] + after,
                   c["res_region"])


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--data", required=True, help="extracted Zenodo folder (has automated-analysis-data/)")
    p.add_argument("--langs", nargs="+", default=["Java"], choices=LANGS)
    p.add_argument("--limit", type=int, help="only the first N conflicts of each language")
    p.add_argument("--out", required=True)
    args = p.parse_args()

    examples = []
    for lang in args.langs:
        cur = [(lang,) + c for c in islice(conflicts(Path(args.data), lang), args.limit)]
        print(f"{lang}: {len(cur)} conflicts")
        examples += cur

    out = Path(args.out)
    (out / "RAW_DATA").mkdir(parents=True, exist_ok=True)
    raw = [[e[i] for e in examples] for i in (3, 4, 5, 6)]
    (out / "RAW_DATA/raw_data").write_text(json.dumps(raw), encoding="utf-8")
    (out / "RAW_DATA/raw_data_ids.json").write_text(json.dumps([list(e[:3]) for e in examples]),
                                                   encoding="utf-8")
    (out / "all_index").write_text(json.dumps({"train": [], "valid": [], "test": list(range(len(examples)))}))
    print(f"{len(examples)} conflicts -> {out}")


if __name__ == "__main__":
    main()
