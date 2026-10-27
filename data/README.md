# Data

This folder holds the conflict samples used in the experiments.

## What is versioned

- Small samples and the list of sampled conflict IDs (for example `toys.json`).

## What is NOT versioned

- The raw dataset.
- MergeGen model weights.

Both are ignored by `.gitignore` because of their size and license terms.

## Where to get the raw dataset

The MergeGen paper uses the dataset from MergeBERT, available on Zenodo:
<https://zenodo.org/record/6366908>

Download it and place it in `data/raw/` (this path is git-ignored).
