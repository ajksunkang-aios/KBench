"""
KBench agent loop — drives a tool-using agent through the Anthropic-compatible
endpoint (GLM-5.x via ANTHROPIC_BASE_URL in this env) and instruments the run.

Instruments per run: tokens (in/out/cache), tool-call counts by name, wall time,
turn count, and the final answer text. Stop conditions: end_turn, max_turns, or
a tool error loop.
"""
from __future__ import annotations

import os
import time
from typing import Any, Callable

# Tool-neutral system prompt. The fenced answer block makes scoring objective.
SYSTEM_PROMPT = """\
You are a precise code-retrieval agent working over a Linux kernel source tree.
Answer the user's question using ONLY the provided tools (do not guess from memory).

When you have the answer, end your response with a fenced block exactly in this
format (one item per line, `name|file`, file relative to the repo root):

```kbench
<symbol-or-function-name>|<repo/relative/path>
<symbol-or-function-name>|<repo/relative/path>
```

Rules:
- If the answer is a single definition/ location, emit one line.
- If the answer is a set (callers, references, implementations), emit one line per item.
- Use the real function/symbol names and the file paths the tools returned.
- If you cannot determine the answer, emit an empty ```kbench block.
"""


def make_client():
    """Build the Anthropic client from env (auth_token or api_key + base_url)."""
    import anthropic
    kwargs: dict[str, Any] = {}
    if os.environ.get("ANTHROPIC_BASE_URL"):
        kwargs["base_url"] = os.environ["ANTHROPIC_BASE_URL"]
    tok = os.environ.get("ANTHROPIC_AUTH_TOKEN")
    key = os.environ.get("ANTHROPIC_API_KEY")
    if tok:
        kwargs["auth_token"] = tok
    elif key:
        kwargs["api_key"] = key
    return anthropic.Anthropic(**kwargs)


def run_agent(client, model: str, prompt: str,
              tools: list[dict], dispatch: Callable[[str, dict], str],
              max_turns: int = 12, max_tokens: int = 2048) -> dict:
    """Run one agent episode. Returns metrics + final answer text."""
    messages = [{"role": "user", "content": prompt}]
    tokens_in = tokens_out = tokens_cache = 0
    tool_calls: dict[str, int] = {}
    turns = 0
    answer = ""
    t0 = time.time()

    while turns < max_turns:
        resp = client.messages.create(
            model=model, max_tokens=max_tokens,
            system=SYSTEM_PROMPT, messages=messages, tools=tools,
        )
        turns += 1
        u = resp.usage
        tokens_in += getattr(u, "input_tokens", 0) or 0
        tokens_out += getattr(u, "output_tokens", 0) or 0
        tokens_cache += (getattr(u, "cache_read_input_tokens", 0) or 0) \
            + (getattr(u, "cache_creation_input_tokens", 0) or 0)
        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason != "tool_use":
            answer = "".join(getattr(b, "text", "") for b in resp.content
                             if getattr(b, "type", None) == "text")
            break

        # execute every tool_use block this turn
        results = []
        for b in resp.content:
            if getattr(b, "type", None) != "tool_use":
                continue
            tool_calls[b.name] = tool_calls.get(b.name, 0) + 1
            out = dispatch(b.name, dict(b.input))
            results.append({"type": "tool_result",
                            "tool_use_id": b.id, "content": out})
        messages.append({"role": "user", "content": results})

    wall = time.time() - t0
    return {
        "answer": answer,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "tokens_cache": tokens_cache,
        "tool_calls": tool_calls,
        "wall_seconds": round(wall, 2),
        "turns": turns,
    }
