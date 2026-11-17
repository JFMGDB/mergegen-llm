"""Context lines around a conflict.

In RAW_DATA/raw_data, base, A and B carry up to CONTEXT_LINES lines of context on each side,
but the developer resolution is only the conflict region. Claude gets the context apart and
answers only the region; the course MergeGen model answers context + region. To compare them
with the dataset on equal terms, the same context is put around the resolution.
"""

CONTEXT_LINES = 2  # context lines kept on each side by prepare_mergebert.py and mine_conflicts.py


def split_context(base: str, a: str, b: str, n: int = CONTEXT_LINES):
    """Return (before, after): lines equal in the three versions, at most n on each side.
    run_claude.py uses it to give Claude the context apart from the conflict."""
    versions = [v.splitlines(keepends=True) for v in (base, a, b)]
    shortest = min(len(v) for v in versions)
    n_before = 0
    while n_before < min(n, shortest) and versions[0][n_before] == versions[1][n_before] == versions[2][n_before]:
        n_before += 1
    n_after = 0
    while (n_after < min(n, shortest - n_before)
           and versions[0][-1 - n_after] == versions[1][-1 - n_after] == versions[2][-1 - n_after]):
        n_after += 1
    before = "".join(versions[0][:n_before])
    after = "".join(versions[0][len(versions[0]) - n_after:])
    return before, after


def with_context(before: str, region: str, after: str) -> str:
    """Region with its context around it (newlines keep the last and first tokens apart)."""
    return "\n".join(part for part in (before, region, after) if part)
