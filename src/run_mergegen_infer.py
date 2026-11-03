"""Run the trained MergeGen model (the one from the course's miningframework) on conflicts
from a run folder of the ase-merge fork, one by one, on CPU or GPU.

It uses `MergeInference.generate_resolution(base, a, b)` from the miningframework branch
`sepmerge`, folder `dependencies/dependencies/mergegen`. That folder must contain
`mergegen_inference.py`, `codet5-small-local/` and the trained `best_model.pt`
(from `mergegen.zip` in the course Drive folder; none of these files is versioned here).

Example (from the fork folder that has RAW_DATA/raw_data):
    python3 ../mergegen-llm/src/run_mergegen_infer.py --run . \
        --mergegen-dir ../miningframework/dependencies/dependencies/mergegen --limit 5

Output: <run>/OUTPUT/mergegen_course/results.jsonl, one line per conflict
({index, output, time_s, error}). It is resumable: indexes already there are skipped.
Then: python3 src/compare.py --run <run> --model <claude model> \
        --mergegen-jsonl <run>/OUTPUT/mergegen_course/results.jsonl
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path


class StubInference:
    """Offline stand-in (--stub) to test the plumbing without the model."""

    def generate_resolution(self, base, a, b):
        return a


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", default=".", help="folder with RAW_DATA/raw_data (and all_index)")
    p.add_argument("--mergegen-dir", help="folder with mergegen_inference.py and best_model.pt")
    p.add_argument("--model-file", default="best_model.pt")
    p.add_argument("--split", choices=["all", "train", "valid", "test"], default="all",
                   help="which conflicts to run (needs all_index for train/valid/test)")
    p.add_argument("--limit", type=int)
    p.add_argument("--out", help="results.jsonl path")
    p.add_argument("--stub", action="store_true", help="do not load the model (plumbing test)")
    args = p.parse_args()

    run = Path(args.run).resolve()
    bases, a_s, b_s, _ = json.loads((run / "RAW_DATA/raw_data").read_text(encoding="utf-8"))
    indexes = list(range(len(bases)))
    if args.split != "all":
        indexes = json.loads((run / "all_index").read_text())[args.split]
    if args.limit:
        indexes = indexes[: args.limit]

    out = Path(args.out).resolve() if args.out else run / "OUTPUT/mergegen_course/results.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        done = {json.loads(line)["index"] for line in out.read_text(encoding="utf-8").splitlines() if line}
    todo = [i for i in indexes if i not in done]
    print(f"{len(indexes)} conflicts, {len(done)} already done, {len(todo)} to run", flush=True)

    if args.stub:
        tool = StubInference()
    else:
        if not args.mergegen_dir:
            sys.exit("--mergegen-dir is required (or use --stub)")
        mdir = Path(args.mergegen_dir).resolve()
        if not (mdir / args.model_file).exists():
            sys.exit(f"{mdir / args.model_file} not found: get best_model.pt from mergegen.zip (course Drive)")
        os.chdir(mdir)  # the course code uses relative paths (./codet5-small-local, best_model.pt)
        sys.path.insert(0, str(mdir))
        from mergegen_inference import MergeInference
        tool = MergeInference(model_path=args.model_file)

    with out.open("a", encoding="utf-8") as f:
        for n, i in enumerate(todo, 1):
            start = time.perf_counter()
            try:
                res, err = tool.generate_resolution(bases[i], a_s[i], b_s[i]), ""
            except Exception as e:  # noqa: BLE001 - record the failure and keep going
                res, err = "", f"{type(e).__name__}: {e}"
            f.write(json.dumps({"index": i, "output": res, "time_s": round(time.perf_counter() - start, 3),
                                "error": err}, ensure_ascii=False) + "\n")
            f.flush()
            print(f"  [{n}/{len(todo)}] {i}: {'ok' if not err else 'ERROR ' + err[:80]}", flush=True)
    print(f"saved {out}")


if __name__ == "__main__":
    main()
