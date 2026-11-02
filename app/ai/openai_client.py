"""Async OpenAI client wrapper.

One place that knows how to talk to OpenAI: creates the client from settings,
lets the SDK retry transient errors (429/5xx), and exposes a JSON-mode helper
so callers get a parsed dict back instead of raw text.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Awaitable, Callable

from openai import AsyncOpenAI

from app.config import settings

DEFAULT_MODEL = "gpt-4o-mini"


@lru_cache(maxsize=1)
def get_openai() -> AsyncOpenAI:
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY must be set in .env")
    # max_retries → SDK retries transient 429/5xx with backoff automatically.
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY, max_retries=3)


async def complete_json(prompt: str, model: str = DEFAULT_MODEL, temperature: float = 0.0) -> dict:
    """Send a single-turn prompt and parse the model's JSON response.

    temperature=0 for deterministic classification; response_format forces the
    model to return valid JSON so we can json.loads() it safely.
    """
    client = get_openai()
    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


async def complete_with_tools(
    system: str,
    user: str,
    tools: list[dict],
    impls: dict[str, Callable[..., Awaitable[dict]]],
    model: str = DEFAULT_MODEL,
    max_rounds: int = 5,
) -> str:
    """Run a tool-calling loop: the model picks tools, we execute their async impls and
    feed results back, until it answers in plain text. `tools` are OpenAI function specs;
    `impls` maps each tool name to an async fn(**args) -> JSON-serializable dict.

    This is how the assistant answers from real data instead of guessing numbers.
    """
    client = get_openai()
    messages: list = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    for _ in range(max_rounds):
        resp = await client.chat.completions.create(
            model=model, messages=messages, tools=tools, tool_choice="auto", temperature=0.2,
        )
        msg = resp.choices[0].message
        if not msg.tool_calls:
            return (msg.content or "").strip()
        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ],
        })
        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            fn = impls.get(name)
            try:
                result = await fn(**args) if fn else {"error": f"unknown tool {name}"}
            except Exception as exc:  # noqa: BLE001 — a bad tool call shouldn't crash the reply
                result = {"error": f"{type(exc).__name__}: {str(exc)[:120]}"}
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result, default=str)})
    # Ran out of tool rounds — force a plain-text answer from what we have.
    resp = await client.chat.completions.create(model=model, messages=messages, temperature=0.2)
    return (resp.choices[0].message.content or "").strip()
