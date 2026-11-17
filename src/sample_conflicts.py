"""Draw a reproducible sample from a run folder written by mine_conflicts.py.

Keeps the conflicts whose merge was committed between --since and --until, then draws at most
--per-repo of them from each repository with a fixed --seed (a larger --per-repo keeps the
conflicts of a smaller one), so no single project dominates. With --ids, keeps exactly the
conflicts listed in a sample file (data/samples/*.json), in its order: this rebuilds a published
sample even if the repositories got new merges after it was drawn.
Writes a new run folder with the same layout (RAW_DATA/, all_index).

Examples:
  python3 src/sample_conflicts.py --run ../datasets/java-recent --out ../datasets/java-2m \
      --since 2026-09-16 --until 2026-11-16 --per-repo 150 --seed 42
  python3 src/sample_conflicts.py --run ../datasets/java-recent --out ../datasets/java-2m \
      --ids data/samples/java-2m.json
"""
import argparse
import json
import random
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--run", required=True, help="run folder from mine_conflicts.py")
    p.add_argument("--out", required=True, help="run folder to create")
    p.add_argument("--since", help="keep merges committed on or after this date (YYYY-MM-DD)")
    p.add_argument("--until", help="keep merges committed on or before this date (YYYY-MM-DD)")
    p.add_argument("--ids", help="sample file: keep exactly these conflicts, in this order")
    p.add_argument("--per-repo", type=int, help="at most this many conflicts per repository")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    run, out = Path(args.run), Path(args.out)
    cols = json.loads((run / "RAW_DATA/raw_data").read_text(encoding="utf-8"))
    ids = json.loads((run / "RAW_DATA/raw_data_ids.json").read_text(encoding="utf-8"))
    meta = [json.loads(l) for l in (run / "RAW_DATA/raw_data_meta.jsonl").read_text(encoding="utf-8").splitlines()]

    keep = []
    by_repo = {}
    if args.ids:
        where = {tuple(x[1:]): i for i, x in enumerate(ids)}
        wanted = json.loads(Path(args.ids).read_text(encoding="utf-8"))["conflicts"]
        missing = [w["id"] for w in wanted if (w["id"], w["region"]) not in where]
        if missing:
            raise SystemExit(f"{len(missing)} conflicts of {args.ids} are not in {run}, e.g. {missing[0]}")
        keep = [where[w["id"], w["region"]] for w in wanted]
    else:
        for i, m in enumerate(meta):
            day = m["date"][:10]
            if (not args.since or day >= args.since) and (not args.until or day <= args.until):
                by_repo.setdefault(m["repo"], []).append(i)
    for repo in sorted(by_repo):
        cur = by_repo[repo]
        if args.per_repo and len(cur) > args.per_repo:
            # one shuffle per repository, then a prefix: a larger --per-repo keeps every
            # conflict a smaller one drew, so a sample can grow without redrawing
            order = cur[:]
            random.Random(f"{args.seed}:{repo}").shuffle(order)
            cur = sorted(order[:args.per_repo])
        print(f"{repo}: {len(cur)} of {len(by_repo[repo])}")
        keep += cur

    (out / "RAW_DATA").mkdir(parents=True, exist_ok=True)
    (out / "RAW_DATA/raw_data").write_text(json.dumps([[c[i] for i in keep] for c in cols]),
                                           encoding="utf-8")
    (out / "RAW_DATA/raw_data_ids.json").write_text(json.dumps([ids[i] for i in keep]),
                                                    encoding="utf-8")
    with open(out / "RAW_DATA/raw_data_meta.jsonl", "w", encoding="utf-8") as f:
        for i in keep:
            f.write(json.dumps(meta[i]) + "\n")
    index = {"train": [], "valid": [], "test": list(range(len(keep)))}
    (out / "all_index").write_text(json.dumps(index), encoding="utf-8")
    print(f"Total: {len(keep)} conflicts -> {out}/RAW_DATA/raw_data")


if __name__ == "__main__":
    main()
