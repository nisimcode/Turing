"""Model calls with shared cost accounting and code extraction."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path

import anthropic

from .config import PRICING, get_logger, load_api_key

log = get_logger("gate.llm")
_client: anthropic.Anthropic | None = None
_cost: Counter = Counter()
_cache_tokens: Counter = Counter()
_paid_calls = 0
_last_response_cost = 0.0


class LLMCallBlocked(RuntimeError):
    """A model request refused locally before any network call was made."""


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=load_api_key())
    return _client


def call(model: str, prompt: str, max_tokens: int = 2048,
         system: str | None = None, cache_variant: str | None = None,
         cache_system: bool = False, cache_ttl: str = "5m") -> str:
    """One completion. Cost is accumulated per model.

    Set GATE_LLM_CACHE_DIR to checkpoint successful responses by exact request.
    Cache hits make interrupted research runs resumable without another paid
    call; changing any prompt, model, system message, token limit or explicit
    cache variant produces a different key. Use cache_variant for intentionally
    independent samples of an otherwise identical request.

    `cache_system=True` adds an Anthropic prompt-cache breakpoint to the system
    block. It is deliberately opt-in: use it only when a large, identical
    system prefix will be reused. It does not replace the local response cache;
    a server-side prompt-cache hit still makes a paid request and generates new
    output. Automatic caching is intentionally not enabled because most gate
    calls end in a per-request prompt, which would cause writes without reuse.
    """
    global _last_response_cost
    _last_response_cost = 0.0

    if cache_system and not system:
        raise ValueError("cache_system requires a non-empty system prompt")
    if cache_ttl not in {"5m", "1h"}:
        raise ValueError("cache_ttl must be '5m' or '1h'")

    kwargs = {"model": model, "max_tokens": max_tokens,
              "messages": [{"role": "user", "content": prompt}]}
    if system:
        if cache_system:
            cache_control = {"type": "ephemeral"}
            if cache_ttl == "1h":
                cache_control["ttl"] = "1h"
            kwargs["system"] = [{
                "type": "text",
                "text": system,
                "cache_control": cache_control,
            }]
        else:
            kwargs["system"] = system

    cache_path = None
    cache_dir = os.environ.get("GATE_LLM_CACHE_DIR")
    if cache_dir:
        request = json.dumps(
            {
                "model": model,
                "prompt": prompt,
                "max_tokens": max_tokens,
                "system": system,
                "cache_variant": cache_variant,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        digest = hashlib.sha256(request.encode("utf-8")).hexdigest()
        cache_path = Path(cache_dir) / f"{digest}.json"
        if cache_path.exists():
            try:
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                if cached.get("request") == request:
                    _last_response_cost = float(cached.get("cost", 0.0))
                    log.info("cache hit: %s %s", model, digest[:10])
                    return cached["text"]
            except (OSError, KeyError, json.JSONDecodeError):
                log.warning("ignoring unreadable LLM cache entry %s", cache_path)

    if os.environ.get("GATE_LLM_CACHE_ONLY", "").lower() in {
        "1", "true", "yes"
    }:
        raise LLMCallBlocked(
            "cache-only mode refused an uncached model request; no API call made"
        )

    global _paid_calls
    paid_limit_raw = os.environ.get("GATE_LLM_MAX_PAID_CALLS")
    if paid_limit_raw:
        try:
            paid_limit = int(paid_limit_raw)
        except ValueError as exc:
            raise RuntimeError(
                "GATE_LLM_MAX_PAID_CALLS must be an integer"
            ) from exc
        if cache_dir:
            completed = sum(1 for _ in Path(cache_dir).glob("*.json"))
        else:
            completed = _paid_calls
        if completed >= paid_limit:
            raise LLMCallBlocked(
                f"paid-call budget exhausted ({completed}/{paid_limit}); "
                "cached calls remain available, but a new request was refused"
            )

    _paid_calls += 1
    resp = client().messages.create(**kwargs)
    ip, op = PRICING.get(model, (0.0, 0.0))
    usage = resp.usage
    uncached = getattr(usage, "input_tokens", 0) or 0
    output = getattr(usage, "output_tokens", 0) or 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_created = getattr(
        usage, "cache_creation_input_tokens", 0
    ) or 0
    creation = getattr(usage, "cache_creation", None)
    created_5m = (
        getattr(creation, "ephemeral_5m_input_tokens", 0) or 0
        if creation is not None else 0
    )
    created_1h = (
        getattr(creation, "ephemeral_1h_input_tokens", 0) or 0
        if creation is not None else 0
    )
    # Older SDK response objects may expose only the aggregate creation count.
    # A request made by this helper has one TTL, so that is a safe fallback.
    if cache_created and not (created_5m or created_1h):
        if cache_ttl == "1h":
            created_1h = cache_created
        else:
            created_5m = cache_created

    call_cost = (
        uncached * ip
        + cache_read * ip * 0.10
        + created_5m * ip * 1.25
        + created_1h * ip * 2.00
        + output * op
    ) / 1e6
    _cost[model] += call_cost
    _last_response_cost = call_cost
    _cache_tokens[(model, "read")] += cache_read
    _cache_tokens[(model, "write_5m")] += created_5m
    _cache_tokens[(model, "write_1h")] += created_1h
    if cache_system:
        if cache_read or cache_created:
            log.info(
                "prompt cache: %s read=%d write=%d",
                model,
                cache_read,
                cache_created,
            )
        else:
            log.info(
                "prompt cache unused for %s (prefix may be below the model's "
                "minimum cacheable length)",
                model,
            )
    text = "".join(b.text for b in resp.content if b.type == "text")
    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        pending = cache_path.with_suffix(".tmp")
        pending.write_text(
            json.dumps(
                {"request": request, "text": text, "cost": call_cost},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        pending.replace(cache_path)
        log.info("cache write: %s %s", model, cache_path.stem[:10])
    return text


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
    global _paid_calls, _last_response_cost
    _cost.clear()
    _cache_tokens.clear()
    _paid_calls = 0
    _last_response_cost = 0.0


def total_cost() -> float:
    return sum(_cost.values())


def last_response_cost() -> float:
    """Price of the just-returned response, including a replayed cache entry.

    Unlike :func:`total_cost`, this preserves the original price stored in the
    local response cache. That lets resumable experiments compare policy costs
    without charging cached responses to the current run.
    """
    return _last_response_cost


def cost_report() -> str:
    if not _cost:
        return "no spend"
    parts = ", ".join(f"{m.split('-')[1]} ${c:.4f}" for m, c in _cost.items())
    cache = cache_report()
    suffix = f"; {cache}" if cache else ""
    return f"{parts}  (total ${total_cost():.4f}{suffix})"


def cache_report() -> str:
    """Compact server-side prompt-cache token totals for the current run."""
    reads = sum(
        tokens for (model, kind), tokens in _cache_tokens.items()
        if kind == "read"
    )
    writes_5m = sum(
        tokens for (model, kind), tokens in _cache_tokens.items()
        if kind == "write_5m"
    )
    writes_1h = sum(
        tokens for (model, kind), tokens in _cache_tokens.items()
        if kind == "write_1h"
    )
    if not (reads or writes_5m or writes_1h):
        return ""
    return (
        f"prompt cache read {reads}, "
        f"write5m {writes_5m}, write1h {writes_1h} tokens"
    )
