# Where Claude and MergeGen disagree

Numbers from `summary.md` (Claude Opus 5.5, 3 runs, majority vote; MergeGen course model `best_model.pt`).
Only public conflicts are quoted here; the private dataset appears in aggregate only.

## Kind of developer resolution

Each developer resolution was classified by comparing it (whitespace collapsed) with the conflict
region of each side: kept side A, kept side B, empty, or a combination of both sides / new code.
Accuracy per kind (Opus = mean of the 3 runs):

| Dataset | Kind | Conflicts | MergeGen | Claude Opus |
|---|---|---|---|---|
| MergeBERT (400) | kept A | 98 (24%) | 50.0% | 69.7% |
| | kept B | 73 (18%) | 68.5% | 79.5% |
| | empty | 4 (1%) | 25.0% | 75.0% |
| | combination / new | 225 (56%) | 40.0% | 72.9% |
| Java, last 2 months (509) | kept A | 159 (31%) | 42.1% | 75.5% |
| | kept B | 84 (17%) | 39.3% | 70.2% |
| | empty | 10 (2%) | 50.0% | 93.3% |
| | combination / new | 256 (50%) | 36.3% | 85.7% |
| Private JS/TS (337) | kept A | 174 (52%) | 33.3% | 47.1% |
| | kept B | 84 (25%) | 32.1% | 63.9% |
| | combination / new | 79 (23%) | 20.3% | 48.1% |

Observations:

- Claude is ahead in every kind and every dataset.
- **Combinations** are where the gap is largest on new data (Java, last 2 months: 85.7% vs 36.3%).
  Generating a resolution that is neither side is what MergeGen was designed for, yet it is its weakest kind.
- **MergeGen's drop from MergeBERT to new Java merges is concentrated in "kept B"** (68.5% to 39.3%):
  on data it was trained on, it often knew which side the developer kept. This matches the temporal
  leakage concern (random train/test split of commits from the same projects).
- Claude's weak spot is the opposite case: when the developer simply **kept one side**, Claude sometimes
  combines both sides instead.

## Only MergeGen right (16 of 509 recent Java conflicts)

In almost all of them the developer **kept one side** and Claude **combined both**. Examples:

- `rumble@4ac708d95647:src/main/java/org/rumbledb/compiler/ModuleImportLoader.java`: side A imports
  `ArrayList`, `IdentityHashMap`, `LinkedHashMap`; side B imports `HashMap`. The developer kept A;
  Claude kept all four imports. Both would probably compile; only an unused import differs.
- `rumble@2334475db02f:.../InsertBeforeFunctionIterator.java` and `.../RemoveFunctionIterator.java`:
  side B deleted the helper `evaluatePosition`; the developer deleted it; Claude kept it.
- `accumulo@853433bd1103:.../RecoveryLogsIterator.java`: the developer kept side A (log message and
  type); Claude took side B's log message together with side A's type change.

So most of these are cases where Claude's answer is a plausible merge that differs from the
developer's choice, not a broken one; the exact-match metric counts them as wrong.

## Only Claude right (227 of 509)

Mostly **combinations**, where each side changed a different part of the region. Examples:

- `accumulo@df6d3e901c50:core/src/main/java/org/apache/accumulo/core/iterators/Combiner.java`: side A
  moved the cache to `Caches.getInstance().createNewBuilder(...)`, side B replaced
  `expireAfterWrite(1, HOURS)` with `Duration.ofHours(1)`. The developer and Claude kept both changes.
- `stroom@d15ef9cbb975:.../AiServiceImpl.java`: side A added new constants, side B added a comment
  above the timeout. The developer and Claude kept both.
- `sis@91b3d93094c6:.../ShapefileStore.java`: the developer rewrote three methods to call the new
  `rewrite(...)` of side B with the signatures of side A; Claude produced the same code.

MergeGen also fails when the conflict is longer than its limits (500 input / 200 output tokens):
53 of the 509 recent Java conflicts.

## Limitations

- Exact match counts equivalent resolutions (import order, an extra unused import) as wrong; a
  structural comparison (AST) and build/test checks are planned for the next iteration.
- 3 runs per Claude model; the runs differed by 1.3 percentage points on average and at most 2.1.
- The private dataset is JavaScript/TypeScript, so its drop mixes language and project effects;
  TypeScript was not evaluated in the MergeGen paper.
