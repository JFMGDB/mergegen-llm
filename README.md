# mergegen-llm

An academic project for the MSc course **Merge and Code Review** at the Informatics Center (CIn), Federal University of Pernambuco (UFPE), taught by Prof. Paulo Borba.

> Work in progress. This repository is part of a course project, not a finished tool.

## What is this project?

When two developers change the same code, merging their work can produce a **merge conflict**. [MergeGen](https://doi.org/10.1109/ASE56229.2023.00155) (Dong et al., ASE 2023) resolves conflicts by *generating* the resolution with a small model (CodeT5-small, 60M parameters).

This project asks: **what happens if we replace that small local model with large-scale LLMs?**
We run the same conflicts through MergeGen and through LLMs, and compare the results.

## Research questions

1. **RQ1.** Do large LLMs resolve more merge conflicts than MergeGen?
2. **RQ2.** Does the structured conflict representation proposed by MergeGen also help an LLM when used in the prompt?

## Approach

- **Data:** three sets of conflicts, so that the result does not depend on data MergeGen was trained on:
  1. **MergeBERT dataset** (Java): the data the MergeGen paper used. MergeGen was trained on it, so it only serves as a reference point.
  2. **Recent Java merges:** merge commits of the last two months (from 2026-09-16) in Java projects of the MergeBERT dataset. They are years newer than MergeGen's training data and also newer than the training cutoff of the Claude models used.
  3. **Private projects** (JavaScript/TypeScript): conflicts from two private repositories, which no model can have seen. The conflicts and their code are never versioned; only aggregate numbers are reported.
- **LLMs:** Claude Opus 5.5 and Claude Sonnet 5.5 through the Anthropic API, each run 3 times per conflict (their sampling cannot be fixed).
- **Prompt A:** the three versions of the conflict (base, A, B) given as they are.
- **Prompt B:** the same conflict in the MergeGen structured representation.
- **Metric:** exact match with the resolution written by the developer, also shown ignoring comments.
- **Baseline:** MergeGen, run on the same conflicts.
- **Start small:** first a handful of simple "toy" examples, then a larger sample.

## Pipeline

```
conflicts -> build prompt (A or B) -> call LLM -> evaluate -> results (CSV)
                                                      ^
                          MergeGen output (baseline) -+
```

For each conflict, we record:

- the conflict scenario (base, A and B versions);
- the developer resolution (dataset), the MergeGen resolution and the LLM resolution;
- whether the LLM resolution is equal to the dataset one and to the MergeGen one;
- time and number of tokens used.

## Repository structure

```
.
├── data/       # conflict samples (raw dataset and model weights are NOT versioned)
├── prompts/    # versioned prompt templates (A and B)
├── src/        # pipeline code
├── results/    # CSV files with the outputs of each run
├── slides/     # course presentations
├── .env.example
└── README.md
```

## Getting started

Run the LLM over the conflicts in `data/toys.json` (one CSV per run is saved in `results/`):

```bash
python3 src/run_experiment.py --backend cli --model sonnet --variants A B   # Claude Code, logged-in account
python3 src/run_experiment.py --backend api --model <model-id>              # Anthropic API (needs LLM_API_KEY)
python3 src/run_experiment.py --backend mock                                # offline test, no cost
```

Pass `--mergegen mergegen_output.json` (`{id: resolution}`) to also compare with the MergeGen output.
Note: the `cli` backend runs isolated (no user settings, MCP or tools); the remaining fixed overhead is ~2.4k input tokens per call. The Claude Code version is saved in `results/raw/<run>/VERSION.txt`.

Configuration is done with environment variables. Copy the example file and fill it in:

```bash
cp .env.example .env
```

Never commit your `.env` file or any API key.

## Comparing Claude, MergeGen and the dataset

These scripts work on a run folder of the [ase-merge fork](https://github.com/RafaFigueiroa/ase-merge) (`RAW_DATA/raw_data` plus the Claude outputs from its `run_claude.py`). The MergeGen scripts need the course MergeGen folder (`mergegen_inference.py`, `codet5-small-local/`, `best_model.pt`) and a Python 3.10 environment with the versions from the course Dockerfile.

```bash
# 1. MergeGen output, one conflict at a time (resumable)
python3 src/run_mergegen_infer.py --run ../ase-merge --mergegen-dir ../mergegen --limit 100
# 2. Which conflicts fit the MergeGen limits (500 input / 200 output tokens)
python3 src/mergegen_limits.py --run ../ase-merge --mergegen-dir ../mergegen --limit 100
# 3. One Claude model vs MergeGen vs dataset (CSV in results/)
python3 src/compare.py --run ../ase-merge --model claude-opus-5-5 \
    --mergegen-jsonl ../ase-merge/OUTPUT/mergegen_course/results.jsonl \
    --mergegen-limits ../ase-merge/OUTPUT/mergegen_course/limits.jsonl
# 4. Demo: summary table for several Claude models, plus disagreement examples
python3 src/demo.py --run ../ase-merge --name java100 --models claude-opus-5-5 claude-haiku-5-5 \
    --mergegen-jsonl ../ase-merge/OUTPUT/mergegen_course/results.jsonl \
    --mergegen-limits ../ase-merge/OUTPUT/mergegen_course/limits.jsonl
```

## Mining new conflicts

`mine_conflicts.py` builds the same `RAW_DATA/raw_data` format from any local git clone: for each merge commit it re-merges the files git reports as conflicting (`git merge-file --diff3`) and takes the developer resolution of each conflict region from the merge commit, anchored on the surrounding lines (regions whose anchors are missing or ambiguous are dropped, and repeated conflicts are kept once). `sample_conflicts.py` then draws a reproducible sample by date and per repository.

```bash
git clone --no-checkout https://github.com/FasterXML/jackson-databind ../repos/jackson-databind
python3 src/mine_conflicts.py ../repos/jackson-databind ../repos/accumulo --langs Java \
    --since 2024-01-01 --out ../datasets/java-recent
python3 src/sample_conflicts.py --run ../datasets/java-recent --out ../datasets/java-2m \
    --since 2026-09-16 --per-repo 150 --seed 42
```

The output folder works with `run_claude.py --run`, `run_mergegen_infer.py --run` and `compare.py --run`. Projects used for the recent Java merges: jackson-databind, accumulo, sis, spring-boot, stroom and rumble (ontop and ditto had no conflicts in the period).

## Repeated runs and summary

The Claude models used here reject `temperature`, so the same conflict can get different answers. Each model is run 3 times; after each run, rename `OUTPUT/claude/<model>` to `OUTPUT/claude/<model>-r<k>`. `summary.py` then reports, for each dataset, the mean accuracy over the runs (min-max), how many conflicts Claude got right in every run, in some or in none, the paired comparison with MergeGen (Claude's majority vote, exact McNemar test), and tokens, cost and time per run. It writes only aggregate numbers.

```bash
python3 src/summary.py --models claude-opus-5-5 claude-sonnet-5-5 --out results/summary.md \
    --dataset "MergeBERT (MergeGen trained on it)" ../ase-merge \
        ../ase-merge/OUTPUT/mergegen_course_bos/results.jsonl ../ase-merge/OUTPUT/mergegen_course/limits.jsonl \
    --dataset "Java, last 2 months" ../datasets/java-2m \
        ../datasets/java-2m/OUTPUT/mergegen/results.jsonl ../datasets/java-2m/OUTPUT/mergegen_course/limits.jsonl
```

Notes on the comparison:

- **Equal** means exact match with the developer resolution after collapsing whitespace, as in MergeGen. Answers that are equivalent but written differently (for example, modifiers or imports in another order) count as different.
- **Ignoring comments:** each comparison is also made without `//` and `/* */` comments. MergeGen outputs tokens without line breaks, so where a `//` comment ends is unknown: comparisons with MergeGen ignore only `/* */` comments.
- **Context:** in `raw_data`, base, A and B carry up to 2 context lines on each side, but the developer resolution is only the conflict region. The course MergeGen model answers context + region, so the same context (`src/conflict_context.py`) is put around the dataset resolution and around Claude's answer before comparing them with MergeGen.
- **Length limits:** MergeGen cuts the input at 500 tokens and generates at most 200, so it cannot give the full resolution of longer conflicts. The comparison is shown for all conflicts and for those within the limits.
- **Claude settings:** adaptive thinking with effort `medium`; no `temperature`, `top_p` or `top_k` is sent, since the current Claude models reject them (per the Anthropic API docs).
- MergeGen CPU time and Claude API latency are not directly comparable.
- **Decoder start token:** MergeGen is trained and evaluated in its original code with the decoder starting at `<s>`, but the course `mergegen_inference.py` starts it at `<pad>` (the config default). `run_mergegen_infer.py` now starts at `<s>` (`--decoder-start config` keeps the old behaviour). This barely changes the CodeT5-small model (41/100 to 42/100 on the first 100 Java conflicts), but the CodeT5-base model only generates repeated tokens without it.
- **Java model:** to run `best_model_Java_codet5-base.pt`, add `--model-file best_model_Java_codet5-base.pt --model-type ./codet5-base --out <path>`, and name it in `demo.py` with `--mergegen-label` and `--mergegen-setup`. `--model-type` needs `MergeInference` to accept a `model_type` parameter: the course file hardcodes `./codet5-small-local`, so change it locally. The training data of this model is unknown, so it may have seen the conflicts being compared.
- **Cost:** `demo.py` prints the Claude cost (from the token counts of each call and the API list prices) in total, per conflict and per correct resolution, projected to other run sizes (`--project`, by default 400 and all 63,199 valid Java conflicts), with and without the Batch API discount. For MergeGen it projects the CPU time instead; it has no API cost, but needs a trained model.

## Data and model weights

The dataset and the MergeGen weights are not stored in this repository. See [`data/README.md`](data/README.md) for where to get them.

## Reference

Jinhao Dong, Qihao Zhu, Zeyu Sun, Yiling Lou, Dan Hao.
*Merge Conflict Resolution: Classification or Generation?*
38th IEEE/ACM International Conference on Automated Software Engineering (ASE), 2023.
DOI: [10.1109/ASE56229.2023.00155](https://doi.org/10.1109/ASE56229.2023.00155)

## Authors

José Felipe and Rafael Figueirôa, MSc students at CIn/UFPE.
