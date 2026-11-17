# mergegen-llm

An academic project for the MSc course **Merge and Code Review** at the Informatics Center (CIn), Federal University of Pernambuco (UFPE), taught by Prof. Paulo Borba.

## What is this project?

When two developers change the same code, merging their work can produce a **merge conflict**. [MergeGen](https://doi.org/10.1109/ASE56229.2023.00155) (Dong et al., ASE 2023) resolves conflicts by *generating* the resolution with a small model (CodeT5-small, 60M parameters).

This project asks: **does MergeGen resolve conflicts as well as a large LLM?** We run the same conflicts through MergeGen and through Claude, and compare both with the resolution the developer committed.

## Research questions

1. **RQ1.** Do large LLMs resolve more merge conflicts than MergeGen, on conflicts MergeGen was not trained on?
2. **Future work.** Does the structured conflict representation of MergeGen also help an LLM when used in the prompt? Not evaluated in this iteration: every run uses the prompt in [`prompts/`](prompts/).

## Results

Share of conflicts where the tool gave the developer's resolution. Claude: mean of 3 runs per model.

| Dataset | Conflicts | MergeGen | Claude Opus 5.5 | Claude Sonnet 5.5 |
|---|---|---|---|---|
| MergeBERT (MergeGen was trained on it) | 400 | 47.5% | 73.3% | 70.1% |
| **Java, merges of the last 2 months** | 509 | **38.9%** | **80.1%** | **73.7%** |
| Private JavaScript/TypeScript projects | 337 | 30.0% | 51.5% | 45.7% |

Exact match after collapsing whitespace, the metric of the MergeGen paper. Ignoring comments, MergeGen goes to 49.0%, 41.8% and 30.0%, and Opus to 75.3%, 80.7% and 52.4%.

- Claude is ahead on every dataset (exact McNemar test, p < 0.001). Opus is ahead for every kind of developer resolution.
- MergeGen drops from the data it was trained on to the recent merges; Claude does not. MergeGen's split mixes commits in time (temporal leakage), so its accuracy on MergeBERT is optimistic: when the developer kept side B, MergeGen goes from 68.5% to 39.3%.
- The largest gap is when the developer **combined both sides** or wrote new code (Java, recent: Opus 85.7%, MergeGen 36.3%), which is what generation was proposed for.
- Claude's typical error is the opposite: **combining both sides when the developer kept one** (e.g. keeping an extra import).
- Claude's spread between runs was at most 2 percentage points. A run of Opus costs about US$ 4 per 500 conflicts (3.6 s per call); MergeGen takes 2 to 4 s per conflict on CPU.

Details:

- [`results/summary.md`](results/summary.md): accuracy over the runs, consistency, paired comparison, cost and time.
- [`results/analysis.md`](results/analysis.md): manual reading of the cases where Claude and MergeGen disagree.
- [`results/answers/`](results/answers/): every answer of every tool on the public datasets, with their provenance.

## Reproducing the results

The tables can be checked without calling the API or running MergeGen: `reproduce.sh` rebuilds the run folders of the two public datasets from their sources, puts the versioned answers in them, regenerates the tables and compares them with `results/summary.md`.

```bash
./reproduce.sh --mergebert ../fse2022 --java-clones ../repos
```

`--mergebert` is the extracted Zenodo dataset; `--java-clones` holds full clones of the repositories listed in [`data/samples/java-2m.json`](data/samples/java-2m.json). The conflicts of each sample are listed in [`data/samples/`](data/samples/), so the same sample is rebuilt even after the repositories get new merges. The private dataset cannot be reproduced.

## Datasets

1. **MergeBERT** (Java, [Zenodo 6366908](https://zenodo.org/record/6366908)): the data of the MergeGen paper, first 400 Java conflicts. MergeGen was trained on it, so it only serves as a reference point.
2. **Recent Java merges:** merge commits since 2026-09-16 (two months before mining) in Java projects of the MergeBERT dataset (jackson-databind, accumulo, sis, spring-boot, stroom and rumble), at most 150 conflicts per project. They are years newer than MergeGen's training data and newer than the training cutoff of the Claude models used.
3. **Private projects** (JavaScript/TypeScript): every conflict of the whole history of two private repositories (merges from 2022-08 to 2026-10), which no model can have seen because the code was never public. Their code and conflicts are never versioned; only aggregate numbers are reported.

See [`data/README.md`](data/README.md) for the folder layout and how each dataset is built.

## Pipeline

```
MergeBERT dataset -> prepare_mergebert.py -+
                                           +-> run folder -> run_claude.py   (Claude, 3 runs per model) -+
git repositories  -> mine_conflicts.py    -+                -> run_mergegen.py (MergeGen, course model)   +-> compare.py / summary.py / demo.py
                     sample_conflicts.py                     -> mergegen_limits.py                         -+
```

Every step reads and writes a **run folder**: `RAW_DATA/raw_data` (base, A, B and developer resolution of each conflict, with 2 context lines on each side), `RAW_DATA/raw_data_ids.json` (origin of each conflict), `all_index` (every conflict in `test`) and `OUTPUT/` (answers of each tool).

**Prompt.** Claude gets the conflict in diff3 form (ours, base, theirs) with the context lines apart and answers only the resolved region, inside `<resolution>` tags: [`prompts/system.txt`](prompts/system.txt) and [`prompts/conflict.txt`](prompts/conflict.txt). The prompt was written for this project; MergeGen does not use a prompt (it reads the conflict as a token sequence).

## Repository structure

```
.
├── prompts/       # the prompt used in every Claude run
├── src/
│   ├── prepare_mergebert.py   # run folder from the MergeBERT dataset
│   ├── mine_conflicts.py      # run folder from the merge commits of git repositories
│   ├── sample_conflicts.py    # reproducible sample of a mined run folder, by date and per project
│   ├── run_claude.py          # Claude through the Anthropic API (resumable)
│   ├── run_mergegen.py        # course MergeGen model, one conflict at a time (resumable)
│   ├── mergegen_limits.py     # which conflicts fit the MergeGen limits (500 / 200 tokens)
│   ├── conflict_context.py    # context lines around a conflict (shared helper)
│   ├── compare.py             # one Claude run x MergeGen x developer, per conflict (CSV)
│   ├── summary.py             # every dataset and run: accuracy, consistency, cost (Markdown)
│   └── demo.py                # one-command demo for one dataset, with disagreement examples
├── tests/
├── data/
│   └── samples/   # the conflicts of each public sample (the conflict code itself is not versioned)
├── results/       # aggregate results and answers/ (every answer on the public datasets)
├── reproduce.sh   # regenerate and check the public tables from results/answers/
├── requirements.txt            # Claude, mining and analysis (pinned versions)
├── requirements-mergegen.txt   # MergeGen (Python 3.10, pinned versions)
├── CITATION.cff
└── LICENSE        # MIT
```

## Setup

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env    # then set ANTHROPIC_API_KEY; never commit .env
```

MergeGen needs a separate Python 3.10 environment (see `requirements-mergegen.txt`) and the course MergeGen folder (`mergegen_inference.py`, `codet5-small-local/`, `best_model.pt`), here in `../mergegen`. The model weights are not versioned.

## Running

The examples keep the data next to the repository, in `../datasets/<name>`.

```bash
# 1. Conflicts: MergeBERT, or the merges of local clones
python3 src/prepare_mergebert.py --data ../fse2022 --langs Java --limit 400 --out ../datasets/mergebert
python3 src/mine_conflicts.py ../repos/jackson-databind ../repos/accumulo --langs Java \
    --since 2024-01-01 --out ../datasets/java-recent
python3 src/sample_conflicts.py --run ../datasets/java-recent --out ../datasets/java-2m \
    --since 2026-09-16 --until 2026-11-16 --per-repo 150 --seed 42

# 2. Claude: 3 runs per model; rename the output after each run
python3 src/run_claude.py --run ../datasets/java-2m --model claude-opus-5-5 --workers 4
mv ../datasets/java-2m/OUTPUT/claude/claude-opus-5-5 ../datasets/java-2m/OUTPUT/claude/claude-opus-5-5-r1

# 3. MergeGen (Python 3.10 environment): answers and length limits
python3 src/run_mergegen.py --run ../datasets/java-2m --mergegen-dir ../mergegen \
    --out ../datasets/java-2m/OUTPUT/mergegen/results.jsonl
python3 src/mergegen_limits.py --run ../datasets/java-2m --mergegen-dir ../mergegen

# 4. Results
python3 src/summary.py --models claude-opus-5-5 claude-sonnet-5-5 --out results/summary.md \
    --dataset "Java, last 2 months" ../datasets/java-2m \
        ../datasets/java-2m/OUTPUT/mergegen/results.jsonl ../datasets/java-2m/OUTPUT/mergegen_course/limits.jsonl
python3 src/demo.py --run ../datasets/java-2m --name java-2m --models claude-opus-5-5-r1 claude-sonnet-5-5-r1 \
    --mergegen-jsonl ../datasets/java-2m/OUTPUT/mergegen/results.jsonl \
    --mergegen-limits ../datasets/java-2m/OUTPUT/mergegen_course/limits.jsonl
```

`summary.py` takes `--dataset` once per dataset. `compare.py` and `demo.py` write CSVs with the code of each conflict: use them only for public datasets, or keep their CSVs out of the repository.

## How answers are compared

- **Exact match:** equal to the developer resolution after collapsing whitespace, as in the MergeGen paper. Equivalent answers written differently count as wrong.
- **Ignoring comments** (`summary.py`): the same, without `//` and `/* */` comments.
- **MergeGen output** has no line breaks, so where a `//` comment ends is unknown: comparisons with MergeGen ignore only `/* */` comments.
- **Context:** Claude answers only the conflict region; the course MergeGen model answers the context lines plus the region. The same context is put around the developer resolution and Claude's answer before comparing them with MergeGen.
- **Length limits:** MergeGen cuts the input at 500 tokens and generates at most 200 (53 of the 509 recent Java conflicts are beyond them). They are counted as MergeGen errors, and the tables also show the conflicts within the limits.
- **Claude settings:** adaptive thinking, effort `medium`. The models used reject `temperature`, `top_p` and `top_k`, so each model is run 3 times; `summary.py` reports the mean and the spread, and uses the majority of the runs for the paired comparison.
- **Decoder start token:** the course `mergegen_inference.py` starts the decoder at `<pad>`; MergeGen is trained and evaluated starting at `<s>`, which `run_mergegen.py` uses (`--decoder-start config` keeps the course behaviour).

## Threats to validity

- **The LLM may have seen the code.** The recent Java merges are newer than the models' training cutoff, and the private projects were never public, which reduces this risk; models can still be updated after their cutoff.
- **Exact match** counts equivalent resolutions (another order, an extra unused import) as wrong; ignoring comments only removes comments. A structural (AST) comparison, building and running the tests are left for the next iteration.
- **Mining:** a conflict enters the recent and private datasets only when its resolution can be located without ambiguity in the merge commit; conflicts whose surrounding lines were also changed are dropped.
- **Private dataset:** JavaScript/TypeScript; the MergeGen paper trains and evaluates per language, so the drop there mixes language and project effects.
- **Sample size:** 400, 509 and 337 conflicts, from a few projects; 95% confidence intervals are in `results/summary.md`.
- **LLM variability:** 3 runs per model; the spread was at most 2 percentage points.

## Next steps

- Structural (AST) comparison and build/test checks, as in the course tooling.
- Run the same pipeline, packaged in Docker, on the private Java dataset of the course group.
- Evaluate the MergeGen structured representation in the prompt (RQ2).

## Reference

Jinhao Dong, Qihao Zhu, Zeyu Sun, Yiling Lou, Dan Hao.
*Merge Conflict Resolution: Classification or Generation?*
38th IEEE/ACM International Conference on Automated Software Engineering (ASE), 2023.
DOI: [10.1109/ASE56229.2023.00155](https://doi.org/10.1109/ASE56229.2023.00155)

## Authors

José Felipe Guerra and Rafael Figueirôa, MSc students at CIn/UFPE.
