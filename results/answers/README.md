# Answers of each tool (public datasets)

Raw answers behind `results/summary.md`, so the tables can be checked without calling the API or
running MergeGen (`./reproduce.sh`). The private dataset is not here: its code is never published.

```
<dataset>/claude-opus-5-5-r{1,2,3}.jsonl     one line per conflict, from src/run_claude.py
<dataset>/claude-sonnet-5-5-r{1,2,3}.jsonl
<dataset>/mergegen.jsonl                     course MergeGen model, from src/run_mergegen.py
<dataset>/mergegen-limits.jsonl              MergeGen length limits, from src/mergegen_limits.py
```

`index` is the position of the conflict in the run folder, i.e. in the sample file of
`data/samples/` (`mergebert` -> `mergebert-java-400.json`, `java-2m` -> `java-2m.json`).

| File | Fields |
|---|---|
| `claude-*.jsonl` | `output` (resolved region), `match` (exact match after collapsing whitespace), `parse_error`, `stop_reason`, `model` (as returned by the API), `input_tokens`, `output_tokens`, `time_s` (API latency) |
| `mergegen.jsonl` | `output` (context lines + region, as one token stream), `time_s` (local CPU), `error`; a conflict may appear twice when a failed attempt was retried, the last line wins |
| `mergegen-limits.jsonl` | `conflict_tokens`, `reference_tokens`, `within_limits` (500 input / 200 output BPE tokens) |

## Provenance

| | |
|---|---|
| Claude models | `claude-opus-5-5` and `claude-sonnet-5-5`, Anthropic Messages API, adaptive thinking with effort `medium`, no sampling parameters (rejected by these models); 3 runs each |
| Claude runs | 2026-11-16 and 2026-11-17 |
| Prompt | `prompts/system.txt` and `prompts/conflict.txt` |
| MergeGen | course model `best_model.pt` (CodeT5-small), decoder started at `<s>`, beam search on CPU (deterministic: 50 of 50 conflicts gave the same answer twice) |
| Environments | Python 3.15.2 with `requirements.txt` (Claude, analysis); Python 3.10.22 with `requirements-mergegen.txt` and torch 2.14.1+cpu (MergeGen); git 2.56.0 (mining) |

The code in these answers comes from the open-source projects of each dataset and keeps their
licenses.
