#!/usr/bin/env bash
# Regenerate the public rows of results/summary.md from the versioned answers in results/answers/,
# with no API call and no MergeGen model: rebuild the run folders of the two public datasets,
# put the answers in them, run summary.py and check the tables against results/summary.md.
# The private dataset cannot be reproduced (its code is not published).
#
# Usage:
#   ./reproduce.sh --mergebert ../fse2022 --java-clones ../repos
#   ./reproduce.sh --mergebert ../fse2022 --java-mined ../datasets/java-recent
#
#   --mergebert DIR    extracted MergeBERT dataset (Zenodo 6366908, has automated-analysis-data/)
#   --java-clones DIR  full clones (git clone --no-checkout) of the repositories listed in
#                      data/samples/java-2m.json, one folder per repository, named as there
#   --java-mined DIR   or a run folder already mined from those clones (skips the mining)
#   --work DIR         where to build the run folders (default: ../reproduce)
set -euo pipefail
cd "$(dirname "$0")"

work=../reproduce
mergebert="" clones="" mined=""
while [ $# -gt 0 ]; do
  case "$1" in
    --mergebert) mergebert=$2; shift 2 ;;
    --java-clones) clones=$2; shift 2 ;;
    --java-mined) mined=$2; shift 2 ;;
    --work) work=$2; shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
if [ -z "$mergebert" ] || { [ -z "$clones" ] && [ -z "$mined" ]; }; then
  sed -n '7,16p' "$0" >&2
  exit 2
fi
mkdir -p "$work"

echo "== MergeBERT: first 400 Java conflicts"
python3 src/prepare_mergebert.py --data "$mergebert" --langs Java --limit 400 --out "$work/mergebert"
python3 - "$work/mergebert" <<'EOF'
import json, sys
got = [tuple(x[1:]) for x in json.load(open(sys.argv[1] + "/RAW_DATA/raw_data_ids.json"))]
want = [(c["id"], c["region"]) for c in json.load(open("data/samples/mergebert-java-400.json"))["conflicts"]]
sys.exit(0 if got == want else "the MergeBERT conflicts differ from data/samples/mergebert-java-400.json")
EOF

echo "== Java, last 2 months"
if [ -z "$mined" ]; then
  repos=$(python3 -c "import json; print(' '.join(json.load(open('data/samples/java-2m.json'))['repositories']))")
  mined=$work/java-recent
  python3 src/mine_conflicts.py $(for r in $repos; do echo "$clones/$r"; done) --langs Java \
      --since 2024-01-01 --out "$mined"
fi
python3 src/sample_conflicts.py --run "$mined" --out "$work/java-2m" --ids data/samples/java-2m.json

echo "== Versioned answers -> run folders"
for ds in mergebert java-2m; do
  for f in results/answers/$ds/claude-*.jsonl; do
    run=$(basename "$f" .jsonl)
    mkdir -p "$work/$ds/OUTPUT/claude/$run/test"
    cp "$f" "$work/$ds/OUTPUT/claude/$run/test/results.jsonl"
  done
done

echo "== Summary"
python3 src/summary.py --models claude-opus-5-5 claude-sonnet-5-5 --out "$work/summary-public.md" \
  --dataset "MergeBERT (MergeGen trained on it)" "$work/mergebert" \
      results/answers/mergebert/mergegen.jsonl results/answers/mergebert/mergegen-limits.jsonl \
  --dataset "Java, last 2 months" "$work/java-2m" \
      results/answers/java-2m/mergegen.jsonl results/answers/java-2m/mergegen-limits.jsonl > /dev/null

python3 - "$work/summary-public.md" <<'EOF'
import sys
public = ("| MergeBERT", "| Java, last 2 months")
rows = lambda path: [l for l in open(path, encoding="utf-8") if l.startswith(public)]
got, want = rows(sys.argv[1]), rows("results/summary.md")
if got != want:
    sys.exit("the regenerated tables differ from results/summary.md:\n" + "".join(
        f"- {w}+ {g}" for w, g in zip(want, got) if w != g))
print(f"OK: the {len(got)} public rows of results/summary.md were reproduced ({sys.argv[1]})")
EOF
