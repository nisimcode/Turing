"""Zero-credit preflight for the Q24 mutation-scoring path.

This deliberately makes no model calls. It proves, with a static miniature
vertical, that browser execution, independent mutation witnesses, mutation
scoring, Unicode-safe output, and paid-call checkpointing all work before the
live auto-vertical experiment is allowed to spend again.

    uv run --with anthropic --with playwright --with pillow python offline_q24_check.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gate.core import verify
from gate.core import llm
from gate.core.mutation import find_divergence, mutation_score

SLOT = "/*__LOGIC_SLOT__*/"

SCAFFOLD = """<!doctype html>
<html><body>
<main><h1>Caesar</h1><label>Text <input></label><label>Shift <input></label>
<button>Convert</button><output>Ready</output></main>
<script>
/*__LOGIC_SLOT__*/
window.__fn = (...args) => caesarShift(...args);
</script></body></html>"""

CORRECT = r"""
function caesarShift(text, shift) {
  const k = ((Math.trunc(shift) % 26) + 26) % 26;
  return Array.from(text).map(ch => {
    const code = ch.charCodeAt(0);
    if (code >= 65 && code <= 90)
      return String.fromCharCode(65 + (code - 65 + k) % 26);
    if (code >= 97 && code <= 122)
      return String.fromCharCode(97 + (code - 97 + k) % 26);
    return ch;
  }).join("");
}
"""

MUTANTS = [
    r"""
function caesarShift(text, shift) {
  const k = ((Math.trunc(shift) % 26) + 26) % 26;
  return Array.from(text).map(ch => /[A-Za-z]/.test(ch)
    ? String.fromCharCode(ch.charCodeAt(0) + k) : ch).join("");
}
""",
    r"""
function caesarShift(text, shift) {
  const k = ((Math.trunc(shift) % 26) + 26) % 26;
  return Array.from(text).map(ch => {
    const code = ch.charCodeAt(0);
    return code >= 97 && code <= 122
      ? String.fromCharCode(97 + (code - 97 + k) % 26) : ch;
  }).join("");
}
""",
    r"""
function caesarShift(text, shift) {
  const k = ((Math.trunc(shift) % 26) + 26) % 26;
  return Array.from(text).map(ch => {
    const code = ch.charCodeAt(0);
    if (code >= 65 && code <= 90)
      return String.fromCharCode(65 + (code - 65 + k) % 26);
    if (code >= 97 && code <= 122)
      return String.fromCharCode(97 + (code - 97 + k) % 26);
    return String.fromCharCode(code + k);
  }).join("");
}
""",
]

BATTERY = [
    {"args": ["z", 1], "expected": "a"},
    {"args": ["Z", 1], "expected": "A"},
    {"args": ["a!", 1], "expected": "b!"},
    {"args": ["abc", -1], "expected": "zab"},
    {"args": ["", 9], "expected": ""},
]

PROBES = [["yz", 2], ["Y", 2], ["b?", 2]]


def build(root: Path, impl: str) -> Path:
    artifact = root / "caesar.html"
    artifact.write_text(SCAFFOLD.replace(SLOT, impl), encoding="utf-8")
    return artifact


def functional(page):
    checks = [{"name": "hook", "ok": page.evaluate(
        "typeof window.__fn === 'function'"), "detail": "window.__fn"}]
    mismatches = []
    for case in BATTERY:
        got = page.evaluate("(a) => window.__fn(...a)", case["args"])
        if got != case["expected"]:
            mismatches.append((case["args"], got, case["expected"]))
    checks.append({
        "name": "oracle",
        "ok": not mismatches,
        "detail": "all cases agree" if not mismatches else repr(mismatches[0]),
    })
    return checks


def cache_smoke() -> None:
    calls = {"count": 0}
    requests = []

    class FakeMessages:
        def create(self, **kwargs):
            calls["count"] += 1
            requests.append(kwargs)
            if isinstance(kwargs.get("system"), list):
                usage = SimpleNamespace(
                    input_tokens=10,
                    output_tokens=5,
                    cache_read_input_tokens=50,
                    cache_creation_input_tokens=100,
                    cache_creation=SimpleNamespace(
                        ephemeral_5m_input_tokens=80,
                        ephemeral_1h_input_tokens=20,
                    ),
                )
            else:
                usage = SimpleNamespace(input_tokens=10, output_tokens=5)
            return SimpleNamespace(
                usage=usage,
                content=[SimpleNamespace(type="text", text="checkpointed")],
            )

    previous_client = llm._client
    previous_cache = os.environ.get("GATE_LLM_CACHE_DIR")
    previous_limit = os.environ.get("GATE_LLM_MAX_PAID_CALLS")
    previous_cache_only = os.environ.get("GATE_LLM_CACHE_ONLY")
    try:
        with tempfile.TemporaryDirectory(prefix="gate-cache-smoke-") as cache:
            os.environ["GATE_LLM_CACHE_DIR"] = cache
            os.environ["GATE_LLM_MAX_PAID_CALLS"] = "3"
            llm._client = SimpleNamespace(messages=FakeMessages())
            llm.reset_cost()
            first = llm.call("claude-haiku-4-5", "offline cache smoke", 32)
            first_price = llm.last_response_cost()
            second = llm.call("claude-haiku-4-5", "offline cache smoke", 32)
            assert first == second == "checkpointed"
            assert first_price == llm.last_response_cost() == 0.000035
            assert llm.total_cost() == first_price
            assert calls["count"] == 1, "second identical call was not cached"
            independent = llm.call(
                "claude-haiku-4-5",
                "offline cache smoke",
                32,
                cache_variant="independent-sample-1",
            )
            assert independent == "checkpointed"
            assert calls["count"] == 2, "independent sample reused the cache"

            cached_prefix = llm.call(
                "claude-haiku-4-5",
                "per-request suffix",
                32,
                system="large stable prefix",
                cache_system=True,
            )
            assert cached_prefix == "checkpointed"
            assert calls["count"] == 3
            system = requests[-1]["system"]
            assert system == [{
                "type": "text",
                "text": "large stable prefix",
                "cache_control": {"type": "ephemeral"},
            }]
            assert (
                llm.cache_report()
                == "prompt cache read 50, write5m 80, write1h 20 tokens"
            )
            # Haiku pricing: 10 uncached + 50 read*0.1 + 80 write*1.25
            # + 20 write*2 + 5 output*5 = 180 micro-dollars for this call,
            # plus 35 micro-dollars for each of the two ordinary calls.
            assert abs(llm.total_cost() - 0.00025) < 1e-12

            try:
                llm.call("claude-haiku-4-5", "uncached request", 32)
            except RuntimeError as exc:
                assert "budget exhausted" in str(exc)
            else:
                raise AssertionError("paid-call cap allowed a second request")

            os.environ["GATE_LLM_MAX_PAID_CALLS"] = "99"
            os.environ["GATE_LLM_CACHE_ONLY"] = "1"
            assert llm.call(
                "claude-haiku-4-5", "offline cache smoke", 32
            ) == "checkpointed"
            try:
                llm.call("claude-haiku-4-5", "cache-only miss", 32)
            except RuntimeError as exc:
                assert "cache-only mode refused" in str(exc)
            else:
                raise AssertionError("cache-only mode made an API request")
    finally:
        llm._client = previous_client
        if previous_cache is None:
            os.environ.pop("GATE_LLM_CACHE_DIR", None)
        else:
            os.environ["GATE_LLM_CACHE_DIR"] = previous_cache
        if previous_limit is None:
            os.environ.pop("GATE_LLM_MAX_PAID_CALLS", None)
        else:
            os.environ["GATE_LLM_MAX_PAID_CALLS"] = previous_limit
        if previous_cache_only is None:
            os.environ.pop("GATE_LLM_CACHE_ONLY", None)
        else:
            os.environ["GATE_LLM_CACHE_ONLY"] = previous_cache_only


def main() -> int:
    cache_smoke()
    with tempfile.TemporaryDirectory(prefix="gate-q24-offline-") as tmp:
        root = Path(tmp)
        verdict = verify(
            build(root, CORRECT),
            functional=functional,
            vertical="offline_q24",
        )
        assert verdict.passed, verdict.summary()

        validated = []
        for mutant, probe in zip(MUTANTS, PROBES):
            divergence = find_divergence(
                SCAFFOLD, SLOT, CORRECT, mutant, [probe]
            )
            assert divergence is not None, f"mutant did not diverge on {probe}"
            index, original, changed = divergence
            validated.append({
                "code": mutant,
                "diverges_on": [probe][index],
                "original": original,
                "mutant": changed,
            })

        result = mutation_score(
            BATTERY,
            SCAFFOLD,
            SLOT,
            validated,
            lambda actual, expected: actual == expected,
        )
        assert result["mutants"] == 3
        assert result["killed"] == 3
        assert result["score"] == 1.0

    print("OFFLINE Q24 PREFLIGHT: PASS")
    print("  baseline gate: PASS")
    print("  independent mutants validated: 3/3")
    print("  battery mutation score: 100% (3/3)")
    print("  response checkpoint cache: PASS (second call made no request)")
    print("  independent-voter cache isolation: PASS")
    print("  opt-in prompt-cache request + billing telemetry: PASS")
    print("  persistent paid-call cap: PASS (new request refused at limit)")
    print("  strict cache-only mode: PASS (cache miss refused)")
    print("  API spend: $0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
