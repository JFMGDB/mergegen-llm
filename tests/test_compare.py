import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from compare import mcnemar_exact, wilson  # noqa: E402


def test_mcnemar_known_values():
    assert mcnemar_exact(0, 0) == 1.0
    assert abs(mcnemar_exact(5, 5) - 1.0) < 1e-12
    assert abs(mcnemar_exact(0, 5) - 0.0625) < 1e-12   # 2 * (1/32)
    assert abs(mcnemar_exact(1, 9) - 0.021484375) < 1e-9


def test_wilson_bounds():
    lo, hi = wilson(50, 100)
    assert 0.40 < lo < 0.41 and 0.59 < hi < 0.60
    assert wilson(0, 0) == (0.0, 0.0)


def _fake_run(tmp: Path):
    (tmp / "RAW_DATA").mkdir()
    (tmp / "OUTPUT/claude/m/test").mkdir(parents=True)
    json.dump([["b0", "b1", "b2"], ["a0", "a1", "a2"], ["x0", "x1", "x2"], ["r0", "r1  r1", "r2"]],
              open(tmp / "RAW_DATA/raw_data", "w"))
    rows = [{"index": 0, "output": "r0", "input_tokens": 10, "output_tokens": 2, "time_s": 1.0, "model": "m", "parse_error": False, "stop_reason": "end_turn"},
            {"index": 1, "output": "r1 r1", "input_tokens": 10, "output_tokens": 2, "time_s": 2.0, "model": "m", "parse_error": False, "stop_reason": "end_turn"},
            {"index": 2, "output": "wrong", "input_tokens": 10, "output_tokens": 2, "time_s": 3.0, "model": "m", "parse_error": False, "stop_reason": "end_turn"}]
    (tmp / "OUTPUT/claude/m/test/results.jsonl").write_text("\n".join(map(json.dumps, rows)) + "\n")
    mg = [{"index": 0, "output": "r0", "time_s": 0.5, "error": ""},
          {"index": 1, "output": "bad", "time_s": 0.5, "error": ""},
          {"index": 2, "output": "", "time_s": 0.1, "error": "boom"}]  # failed: must be left out
    (tmp / "mg.jsonl").write_text("\n".join(map(json.dumps, mg)) + "\n")


def test_compare_end_to_end_ignores_failed_mergegen():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _fake_run(tmp)
        out = subprocess.run(
            [sys.executable, str(ROOT / "src/compare.py"), "--run", str(tmp), "--model", "m",
             "--mergegen-jsonl", str(tmp / "mg.jsonl"), "--out", str(tmp / "o.csv")],
            capture_output=True, text=True, check=True).stdout
        assert "Same 2 conflicts" in out          # the conflict where MergeGen failed is not compared
        assert "Claude   = dataset : 2/3" in out  # whitespace-normalised equality
        assert "only Claude 1 | only MergeGen 0" in out


def test_split_context_takes_equal_lines_on_each_side():
    from conflict_context import split_context, with_context
    base = "c1\nc2\nc3\nold\nd1\nd2\n"
    a = "c1\nc2\nc3\nnew a\nd1\nd2\n"
    b = "c1\nc2\nc3\nnew b\nd1\nd2\n"
    before, after = split_context(base, a, b)
    assert before == "c1\nc2\n" and after == "d1\nd2\n"   # at most 2 lines each side
    assert split_context(base, a, b, 0) == ("", "")
    assert with_context("x;", "y;", "") == "x;\ny;"        # tokens never glued together


def test_compare_puts_context_around_reference_for_mergegen():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        (tmp / "RAW_DATA").mkdir()
        (tmp / "OUTPUT/claude/m/test").mkdir(parents=True)
        json.dump([["c1\nold\nd1\n"], ["c1\nnew a\nd1\n"], ["c1\nnew b\nd1\n"], ["new a\n"]],
                  open(tmp / "RAW_DATA/raw_data", "w"))
        row = {"index": 0, "output": "new a", "input_tokens": 1, "output_tokens": 1, "time_s": 1.0,
               "model": "m", "parse_error": False, "stop_reason": "end_turn"}
        (tmp / "OUTPUT/claude/m/test/results.jsonl").write_text(json.dumps(row) + "\n")
        (tmp / "mg.jsonl").write_text(json.dumps({"index": 0, "output": "c1 new a d1", "time_s": 0.1, "error": ""}) + "\n")
        (tmp / "lim.jsonl").write_text(json.dumps({"index": 0, "conflict_tokens": 9, "reference_tokens": 5,
                                                    "within_limits": True}) + "\n")
        out = subprocess.run(
            [sys.executable, str(ROOT / "src/compare.py"), "--run", str(tmp), "--model", "m",
             "--mergegen-jsonl", str(tmp / "mg.jsonl"), "--mergegen-limits", str(tmp / "lim.jsonl"),
             "--out", str(tmp / "o.csv")],
            capture_output=True, text=True, check=True).stdout
        assert "MergeGen = dataset : 1/1" in out
        assert "Claude   = MergeGen: 1/1" in out
        assert "Only the 1 of them within the MergeGen limits" in out


def test_demo_counts_who_gets_each_conflict_right():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _fake_run(tmp)
        out = subprocess.run(
            [sys.executable, str(ROOT / "src/demo.py"), "--run", str(tmp), "--name", "t", "--models", "m",
             "--mergegen-jsonl", str(tmp / "mg.jsonl"), "--examples", "1"],
            capture_output=True, text=True, check=True, cwd=tmp).stdout
        assert "=== Who gets each conflict right (2 conflicts) ===" in out
        assert out.count("right             right") == 1   # conflict 0: both right
        assert out.count("right             wrong") == 1   # conflict 1: only Claude right
        assert "--- conflict 1: m right, MergeGen wrong ---" in out
