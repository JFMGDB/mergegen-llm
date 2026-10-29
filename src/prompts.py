"""Build prompts A (three raw sides) and B (MergeGen structured representation)."""
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _template(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def structured(base: str, a: str, b: str) -> str:
    """MergeGen-style conflict string (snippet level)."""
    return f"<bos> <boc> {a} <soc> {base} <soc> {b} <eoc> <eos>"


def build_prompt(variant: str, toy: dict) -> str:
    if variant == "A":
        return _template("prompt_a.txt").format(base=toy["base"], a=toy["a"], b=toy["b"])
    if variant == "B":
        return _template("prompt_b.txt").format(
            structured=structured(toy["base"], toy["a"], toy["b"])
        )
    raise ValueError(f"unknown prompt variant: {variant}")
