# Data

The conflicts' code and the model weights are not versioned in this repository; only the list of
conflicts of each public sample is (`samples/`). The scripts read and write **run folders**, kept
outside the repository (the examples use `../datasets/<name>`).

## Run folder layout

```
<run>/
  RAW_DATA/raw_data             [bases, as, bs, resolutions], one entry per conflict
  RAW_DATA/raw_data_ids.json    [language, origin, conflict index] per conflict
  RAW_DATA/raw_data_meta.jsonl  merge date, parents and file (mined datasets only)
  all_index                     {"train": [], "valid": [], "test": [every conflict]}
  OUTPUT/claude/<model>-r<k>/test/results.jsonl   one Claude run (run_claude.py)
  OUTPUT/mergegen/results.jsonl                   MergeGen answers (run_mergegen.py)
  OUTPUT/mergegen_course/limits.jsonl             MergeGen length limits (mergegen_limits.py)
```

Base, A and B carry the conflict region of each version with up to 2 context lines on each side;
the resolution is the developer's resolution of the region only.

## Datasets used

| Dataset | Source | Build |
|---|---|---|
| MergeBERT, 400 Java conflicts | [Zenodo 6366908](https://zenodo.org/record/6366908), extracted (has `automated-analysis-data/`) | `prepare_mergebert.py --langs Java --limit 400` |
| Java, last 2 months, 509 conflicts | full clones of jackson-databind, accumulo, sis, spring-boot, stroom, rumble, ontop and ditto | `mine_conflicts.py --langs Java --since 2024-01-01`, then `sample_conflicts.py --since 2026-09-16 --until 2026-11-16 --per-repo 150 --seed 42` |
| Private JS/TS, 341 conflicts | two private repositories | `mine_conflicts.py` over the whole history (no `--since`), no sampling; merges from 2022-08 to 2026-10 |

## Published samples

`samples/` lists the conflicts of each public sample, in run-folder order (the `index` of the
answers in `results/answers/`):

- `mergebert-java-400.json`: MergeBERT file id and conflict index of each conflict.
- `java-2m.json`: repository URLs, mining and sampling parameters, and for each conflict the
  merge commit, its date, the file and the region. `sample_conflicts.py --ids` rebuilds exactly
  this sample from a newly mined run folder, even if the repositories got new merges since.

`mine_conflicts.py` needs full clones (`git clone --no-checkout <url>`); the clones can be deleted
after mining. In the private dataset, 4 conflicts are larger than the Claude context window (a data
file); they stay in the run folder and are left out of the comparisons, which use only conflicts
answered by every tool (337).

Never put a run folder of a private dataset, or a CSV or HTML page made from it, inside this
repository: only aggregate numbers (`summary.py`) can be versioned.
