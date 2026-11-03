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

- **Data:** merge conflicts from the dataset used in the MergeGen paper (originally from MergeBERT). Java only.
- **Prompt A:** the three versions of the conflict (base, A, B) given as they are.
- **Prompt B:** the same conflict in the MergeGen structured representation.
- **Metric:** exact match with the resolution written by the developer.
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

Notes on the comparison:

- **Equal** means exact match with the developer resolution after collapsing whitespace, as in MergeGen. Answers that are equivalent but written differently (for example, modifiers or imports in another order) count as different.
- **Context:** in `raw_data`, base, A and B carry up to 2 context lines on each side, but the developer resolution is only the conflict region. The course MergeGen model answers context + region, so the same context (`src/conflict_context.py`) is put around the dataset resolution and around Claude's answer before comparing them with MergeGen.
- **Length limits:** MergeGen cuts the input at 500 tokens and generates at most 200, so it cannot give the full resolution of longer conflicts. The comparison is shown for all conflicts and for those within the limits.
- **Claude settings:** adaptive thinking with effort `medium`; no `temperature`, `top_p` or `top_k` is sent, since the current Claude models reject them (per the Anthropic API docs).
- MergeGen CPU time and Claude API latency are not directly comparable.

## Data and model weights

The dataset and the MergeGen weights are not stored in this repository. See [`data/README.md`](data/README.md) for where to get them.

## Reference

Jinhao Dong, Qihao Zhu, Zeyu Sun, Yiling Lou, Dan Hao.
*Merge Conflict Resolution: Classification or Generation?*
38th IEEE/ACM International Conference on Automated Software Engineering (ASE), 2023.
DOI: [10.1109/ASE56229.2023.00155](https://doi.org/10.1109/ASE56229.2023.00155)

## Authors

José Felipe and Rafael Figueirôa, MSc students at CIn/UFPE.
