"""Measure each conflict against the MergeGen length limits (500 input / 200 output BPE tokens).

MergeGen cuts the input at 500 tokens and generates at most 200, so on a conflict above
either limit it cannot give the full developer resolution. The paper (Threats to validity)
says the parts above the limit are discarded and that the limit covers 95% of its data.

Run it with the MergeGen environment (it needs the CodeT5 tokenizer, not the model weights):
    python3 ../mergegen-llm/src/mergegen_limits.py --run . --mergegen-dir ../mergegen --limit 100

Output: <run>/OUTPUT/mergegen_course/limits.jsonl, one line per conflict
({index, conflict_tokens, reference_tokens, within_limits}); compare.py reads it with
--mergegen-limits.
"""
import argparse
import json
import os
import sys
from pathlib import Path

from conflict_context import split_context, with_context


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", default=".", help="folder with RAW_DATA/raw_data")
    p.add_argument("--mergegen-dir", required=True, help="folder with mergegen_inference.py and codet5-small-local/")
    p.add_argument("--limit", type=int)
    p.add_argument("--out", help="limits.jsonl path")
    args = p.parse_args()

    run = Path(args.run).resolve()
    bases, a_s, b_s, refs = json.loads((run / "RAW_DATA/raw_data").read_text(encoding="utf-8"))
    indexes = list(range(len(bases)))[: args.limit]
    out = Path(args.out).resolve() if args.out else run / "OUTPUT/mergegen_course/limits.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)

    os.chdir(Path(args.mergegen_dir).resolve())  # the course code uses relative paths
    sys.path.insert(0, os.getcwd())
    from mergegen_inference import MergeInference
    from transformers import RobertaTokenizer

    # only the tokenizer and the merge representation are needed: skip loading the weights
    tool = MergeInference.__new__(MergeInference)
    tool.tokenizer = RobertaTokenizer.from_pretrained("./codet5-small-local")
    tool.tokenizer.add_tokens(["<lbra>", "<mbra>", "<rbra>"])
    tool.lbra_token, tool.rbra_token = "<lbra>", "<rbra>"
    max_in, max_out = 500, 200

    def tokens(s):
        return tool.tokenizer.tokenize(" ".join(s.split()))

    within = 0
    with out.open("w", encoding="utf-8") as f:
        for i in indexes:
            conflict = len(tool._git_merge_single(tokens(bases[i]), tokens(a_s[i]), tokens(b_s[i])))
            before, after = split_context(bases[i], a_s[i], b_s[i])
            reference = len(tokens(with_context(before, refs[i], after))) + 2  # + <s> and </s>
            ok = conflict <= max_in and reference <= max_out
            within += ok
            f.write(json.dumps({"index": i, "conflict_tokens": conflict, "reference_tokens": reference,
                                "within_limits": ok}) + "\n")
    print(f"{within}/{len(indexes)} conflicts within the MergeGen limits ({max_in} in / {max_out} out)")
    print(f"saved {out}")


if __name__ == "__main__":
    main()
