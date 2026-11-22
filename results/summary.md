# MergeGen x Claude: summary

'Right' = equal to the developer resolution after collapsing whitespace.

## Exact match

| Dataset | Conflicts | MergeGen | claude-opus-5-5 (mean of runs, min-max) | claude-sonnet-5-5 (mean of runs, min-max) |
|---|---|---|---|---|
| MergeBERT (MergeGen trained on it) | 400 | 47.5% (43%-52%) | 73.3% (73.0%-73.8%), 3 runs | 70.1% (69.2%-70.8%), 3 runs |
| Java, last 2 months | 509 | 38.9% (35%-43%) | 80.1% (79.8%-80.6%), 3 runs | 73.7% (73.3%-74.1%), 3 runs |
| Private JS/TS | 337 | 30.0% (25%-35%) | 51.5% (50.7%-52.8%), 3 runs | 45.7% (44.8%-46.6%), 3 runs |

Consistency across Claude runs and paired comparison with MergeGen (Claude = right in the majority of its runs):

| Dataset | Model | Right in every run | In some runs | In none | Both right | Only Claude | Only MergeGen | Neither | McNemar p |
|---|---|---|---|---|---|---|---|---|---|
| MergeBERT (MergeGen trained on it) | claude-opus-5-5 | 290 | 7 | 103 | 169 | 124 | 21 | 86 | 0.0000 |
| MergeBERT (MergeGen trained on it) | claude-sonnet-5-5 | 267 | 24 | 109 | 161 | 122 | 29 | 88 | 0.0000 |
| Java, last 2 months | claude-opus-5-5 | 396 | 22 | 91 | 182 | 227 | 16 | 84 | 0.0000 |
| Java, last 2 months | claude-sonnet-5-5 | 349 | 51 | 109 | 176 | 200 | 22 | 111 | 0.0000 |
| Private JS/TS | claude-opus-5-5 | 163 | 20 | 154 | 85 | 90 | 16 | 146 | 0.0000 |
| Private JS/TS | claude-sonnet-5-5 | 142 | 26 | 169 | 77 | 75 | 24 | 161 | 0.0000 |

## Ignoring comments

| Dataset | Conflicts | MergeGen | claude-opus-5-5 (mean of runs, min-max) | claude-sonnet-5-5 (mean of runs, min-max) |
|---|---|---|---|---|
| MergeBERT (MergeGen trained on it) | 400 | 49.0% (44%-54%) | 75.3% (75.0%-75.8%), 3 runs | 71.9% (71.5%-72.2%), 3 runs |
| Java, last 2 months | 509 | 41.8% (38%-46%) | 80.7% (80.2%-81.3%), 3 runs | 74.3% (73.9%-74.7%), 3 runs |
| Private JS/TS | 337 | 30.0% (25%-35%) | 52.4% (51.6%-53.7%), 3 runs | 46.6% (45.7%-47.5%), 3 runs |

Consistency across Claude runs and paired comparison with MergeGen (Claude = right in the majority of its runs):

| Dataset | Model | Right in every run | In some runs | In none | Both right | Only Claude | Only MergeGen | Neither | McNemar p |
|---|---|---|---|---|---|---|---|---|---|
| MergeBERT (MergeGen trained on it) | claude-opus-5-5 | 298 | 6 | 96 | 175 | 127 | 21 | 77 | 0.0000 |
| MergeBERT (MergeGen trained on it) | claude-sonnet-5-5 | 278 | 18 | 104 | 165 | 124 | 31 | 80 | 0.0000 |
| Java, last 2 months | claude-opus-5-5 | 399 | 22 | 88 | 196 | 216 | 17 | 80 | 0.0000 |
| Java, last 2 months | claude-sonnet-5-5 | 352 | 51 | 106 | 190 | 189 | 23 | 107 | 0.0000 |
| Private JS/TS | claude-opus-5-5 | 166 | 20 | 151 | 85 | 93 | 16 | 143 | 0.0000 |
| Private JS/TS | claude-sonnet-5-5 | 145 | 26 | 166 | 77 | 78 | 24 | 158 | 0.0000 |

## Ignoring formatting (same code tokens)

| Dataset | Conflicts | MergeGen | claude-opus-5-5 (mean of runs, min-max) | claude-sonnet-5-5 (mean of runs, min-max) |
|---|---|---|---|---|
| MergeBERT (MergeGen trained on it) | 400 | 54.8% (50%-60%) | 75.8% (75.5%-76.2%), 3 runs | 72.5% (72.0%-73.0%), 3 runs |
| Java, last 2 months | 509 | 45.0% (41%-49%) | 81.3% (80.6%-82.1%), 3 runs | 75.6% (75.0%-76.0%), 3 runs |
| Private JS/TS | 337 | 37.4% (32%-43%) | 53.9% (53.1%-55.2%), 3 runs | 48.5% (47.8%-49.6%), 3 runs |

Consistency across Claude runs and paired comparison with MergeGen (Claude = right in the majority of its runs):

| Dataset | Model | Right in every run | In some runs | In none | Both right | Only Claude | Only MergeGen | Neither | McNemar p |
|---|---|---|---|---|---|---|---|---|---|
| MergeBERT (MergeGen trained on it) | claude-opus-5-5 | 300 | 6 | 94 | 197 | 107 | 22 | 74 | 0.0000 |
| MergeBERT (MergeGen trained on it) | claude-sonnet-5-5 | 281 | 17 | 102 | 187 | 104 | 32 | 77 | 0.0000 |
| Java, last 2 months | claude-opus-5-5 | 403 | 20 | 86 | 211 | 205 | 18 | 75 | 0.0000 |
| Java, last 2 months | claude-sonnet-5-5 | 360 | 49 | 100 | 207 | 179 | 22 | 101 | 0.0000 |
| Private JS/TS | claude-opus-5-5 | 171 | 20 | 146 | 110 | 73 | 16 | 138 | 0.0000 |
| Private JS/TS | claude-sonnet-5-5 | 151 | 26 | 160 | 100 | 62 | 26 | 149 | 0.0002 |

## Cost and time per run

| Dataset | Model | Input tokens | Output tokens | Cost (USD) | Claude s/call | MergeGen s/conflict (CPU) |
|---|---|---|---|---|---|---|
| MergeBERT (MergeGen trained on it) | claude-opus-5-5 | 292,914 | 109,202 | 3.36 | 3.36 | 2.19 |
| MergeBERT (MergeGen trained on it) | claude-sonnet-5-5 | 292,914 | 116,146 | 1.75 | 3.03 | 2.19 |
| Java, last 2 months | claude-opus-5-5 | 317,424 | 143,714 | 4.14 | 3.58 | 1.94 |
| Java, last 2 months | claude-sonnet-5-5 | 317,424 | 158,449 | 2.22 | 3.26 | 1.94 |
| Private JS/TS | claude-opus-5-5 | 232,765 | 114,311 | 3.22 | 3.78 | 3.92 |
| Private JS/TS | claude-sonnet-5-5 | 232,765 | 111,079 | 1.58 | 3.24 | 3.92 |

Claude latency (API) and MergeGen time (local CPU) are not directly comparable.
