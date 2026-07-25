"""Model calls with shared cost accounting and code extraction."""

from __future__ import annotations

import re
from collections import Counter

import anthropic

from .config import PRICING, get_logger, load_api_key

log = get_logger("gate.llm")
_client: anthropic.Anthropic | None = None
_cost: Counter = Counter()


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=load_api_key())
    return _client


def call(model: str, prompt: str, max_tokens: int = 2048,
         system: str | None = None) -> str:
    """One completion. Cost is accumulated per model."""
    kwargs = {"model": model, "max_tokens": max_tokens,
              "messages": [{"role": "user", "content": prompt}]}
    if system:
        kwargs["system"] = system
    resp = client().messages.create(**kwargs)
    ip, op = PRICING.get(model, (0.0, 0.0))
    _cost[model] += (resp.usage.input_tokens / 1e6 * ip
                     + resp.usage.output_tokens / 1e6 * op)
    return "".join(b.text for b in resp.content if b.type == "text")


_FENCE = re.compile(r"```([\w+-]*)[ \t]*\n(.*?)```", re.DOTALL)


def blocks(text: str) -> list[tuple[str, str]]:
    """All fenced blocks as (language, code). Language is '' if untagged."""
    return [(m.group(1).lower(), m.group(2)) for m in _FENCE.finditer(text)]


def extract_block(text: str, lang: str, which: int = 0) -> str | None:
    """The `which`-th block explicitly tagged `lang`, or None.

    Strict on purpose: a lenient pattern with an optional language tag matches
    the *closing* fence of a preceding block, which silently returns garbage.
    """
    aliases = {"js": "javascript", "javascript": "javascript",
               "html": "html", "json": "json"}
    want = aliases.get(lang.lower(), lang.lower())
    hits = [code for tag, code in blocks(text)
            if aliases.get(tag, tag) == want]
    return hits[which] if len(hits) > which else None


def extract_code(text: str, lang: str = "") -> str:
    """First block of `lang` if tagged, else the first block, else raw text."""
    if lang:
        got = extract_block(text, lang)
        if got is not None:
            return got
    all_blocks = blocks(text)
    return all_blocks[0][1] if all_blocks else text


def reset_cost() -> None:
    _cost.clear()


def total_cost() -> float:
    return sum(_cost.values())


def cost_report() -> str:
    if not _cost:
        return "no spend"
    parts = ", ".join(f"{m.split('-')[1]} ${c:.4f}" for m, c in _cost.items())
    return f"{parts}  (total ${total_cost():.4f})"
