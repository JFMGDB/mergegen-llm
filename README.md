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

Setup and run instructions will be added as the pipeline is implemented.

Configuration is done with environment variables. Copy the example file and fill it in:

```bash
cp .env.example .env
```

Never commit your `.env` file or any API key.

## Data and model weights

The dataset and the MergeGen weights are not stored in this repository. See [`data/README.md`](data/README.md) for where to get them.

## Reference

Jinhao Dong, Qihao Zhu, Zeyu Sun, Yiling Lou, Dan Hao.
*Merge Conflict Resolution: Classification or Generation?*
38th IEEE/ACM International Conference on Automated Software Engineering (ASE), 2023.
DOI: [10.1109/ASE56229.2023.00155](https://doi.org/10.1109/ASE56229.2023.00155)

## Authors

José Felipe and Rafael, MSc students at CIn/UFPE.
