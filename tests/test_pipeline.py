import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from prompts import build_prompt, structured  # noqa: E402
from run_experiment import clean  # noqa: E402

TOY = {"base": "x", "a": "y", "b": "z"}


def test_prompt_a_has_three_sides():
    p = build_prompt("A", TOY)
    assert "### BASE\nx" in p and "### A\ny" in p and "### B\nz" in p


def test_prompt_b_uses_mergegen_markers():
    assert structured("x", "y", "z") == "<bos> <boc> y <soc> x <soc> z <eoc> <eos>"
    assert "<boc> y <soc> x <soc> z <eoc>" in build_prompt("B", TOY)


def test_clean_removes_fences_only():
    assert clean("```java\nint a;\n```") == "int a;"
    assert clean("int a;") == "int a;"


def test_toys_are_valid():
    toys = json.loads((Path(__file__).resolve().parent.parent / "data" / "toys.json").read_text())
    assert all({"id", "base", "a", "b", "resolution", "difficulty"} <= t.keys() for t in toys)
