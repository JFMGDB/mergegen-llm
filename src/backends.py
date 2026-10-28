"""LLM backends. All return the same dict so the pipeline does not care which one is used.

Return keys: text, input_tokens, output_tokens, cost_usd, raw
"""
import json
import os
import subprocess
import tempfile

SYSTEM_PROMPT = "You are a code merge assistant. Follow the user's output rules exactly."


def claude_cli(prompt: str, model: str, timeout: int = 300) -> dict:
    """Claude Code in non-interactive mode, using the logged-in account.

    Runs in an empty temp dir, with no tools, so the model only sees the prompt.
    """
    cmd = [
        "claude", "-p",
        "--output-format", "json",
        "--model", model,
        "--tools", "",
        "--system-prompt", SYSTEM_PROMPT,
        "--no-session-persistence",
        "--disable-slash-commands",
    ]
    with tempfile.TemporaryDirectory() as empty_dir:
        proc = subprocess.run(
            cmd, input=prompt, capture_output=True, text=True,
            timeout=timeout, cwd=empty_dir,
        )
    if proc.returncode != 0:
        raise RuntimeError(f"claude exited {proc.returncode}: {proc.stderr.strip()[:500]}")
    data = json.loads(proc.stdout)
    if data.get("is_error"):
        raise RuntimeError(f"claude returned an error: {str(data.get('result'))[:500]}")
    usage = data.get("usage", {}) or {}
    # cached tokens are counted as input too, so the total is comparable across runs
    input_tokens = (
        usage.get("input_tokens", 0)
        + usage.get("cache_creation_input_tokens", 0)
        + usage.get("cache_read_input_tokens", 0)
    )
    return {
        "text": data.get("result", ""),
        "input_tokens": input_tokens,
        "output_tokens": usage.get("output_tokens", 0),
        "cost_usd": data.get("total_cost_usd"),
        "raw": data,
    }


def anthropic_api(prompt: str, model: str, timeout: int = 300) -> dict:
    """Anthropic API (needs `pip install anthropic` and LLM_API_KEY in .env)."""
    import anthropic  # imported lazily so the CLI backend works without it

    client = anthropic.Anthropic(api_key=os.environ["LLM_API_KEY"], timeout=timeout)
    msg = client.messages.create(
        model=model, max_tokens=1024, temperature=0, system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in msg.content if block.type == "text")
    return {
        "text": text,
        "input_tokens": msg.usage.input_tokens,
        "output_tokens": msg.usage.output_tokens,
        "cost_usd": None,  # compute from the price table if needed
        "raw": msg.model_dump(),
    }


def mock(prompt: str, model: str, timeout: int = 0) -> dict:
    """Offline fake used to test the pipeline without spending anything."""
    return {"text": "mock resolution", "input_tokens": len(prompt.split()),
            "output_tokens": 2, "cost_usd": 0.0, "raw": {"mock": True}}


BACKENDS = {"cli": claude_cli, "api": anthropic_api, "mock": mock}
