"""ARCHIVED EXPERIMENT: thin cascade economics on a calculator slot.

Task: fill `evaluate(expr)` (integer expression eval, division truncates toward
zero -- the trap). Over M trials, each tier's generation is stochastic, so we get
a real pass rate per tier. The cascade tries Haiku -> Sonnet -> Opus, escalating
only when the GATE fails. We compare cascade vs always-Haiku vs always-Opus on
success rate and cost -- the blended economics, end-to-end through the real gate.

    uv run --with anthropic --with playwright --with pillow python run_cascade_calc.py
"""

import os
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

import anthropic

from browser_gate import gate_html
import calc_spec

M = 6  # trials
TIERS = [("haiku", "claude-haiku-4-5"), ("sonnet", "claude-sonnet-5"),
         ("opus", "claude-opus-4-8")]
PRICING = {"claude-haiku-4-5": (1.0, 5.0), "claude-sonnet-5": (3.0, 15.0),
           "claude-opus-4-8": (5.0, 25.0)}
HERE = Path(__file__).resolve().parent
SCAFFOLD = (HERE / "scaffold" / "tool_calc_scaffold.html").read_text(encoding="utf-8")
SLOT = "/*__LOGIC_SLOT__*/"

PROMPT = (
    "Implement exactly one JavaScript function `function evaluate(expr)` that "
    "evaluates an integer arithmetic expression string. Support non-negative "
    "integer literals, binary + - * /, unary minus, and parentheses. Precedence: "
    "unary minus binds tightest to its operand; * and / are higher than + and -; "
    "+ - and * / are left-associative. Division is INTEGER division that "
    "TRUNCATES TOWARD ZERO (e.g. -7/2 = -3 not -4; 7/-2 = -3; -10/3 = -3). "
    "Whitespace is ignored. Return the integer result. Return ONLY the function "
    "in one code block."
)


def load_api_key() -> str:
    for var in ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY"):
        if os.environ.get(var):
            return os.environ[var]
    for env_path in (HERE / ".env", HERE.parent / ".env"):
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith(("CLAUDE_API_KEY=", "ANTHROPIC_API_KEY=")):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("No API key found (set CLAUDE_API_KEY in E:\\Turing\\.env).")


client = anthropic.Anthropic(api_key=load_api_key())


def gen_and_gate(model):
    """Generate evaluate(), inject, gate. Return (passed, cost)."""
    resp = client.messages.create(
        model=model, max_tokens=1024,
        messages=[{"role": "user", "content": PROMPT}],
    )
    ip, op = PRICING[model]
    cost = resp.usage.input_tokens / 1e6 * ip + resp.usage.output_tokens / 1e6 * op
    text = "".join(b.text for b in resp.content if b.type == "text")
    m = re.search(r"```(?:javascript|js)?\s*\n(.*?)```", text, re.DOTALL)
    code = m.group(1) if m else text
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False,
                                     encoding="utf-8") as f:
        path = f.name
        f.write(SCAFFOLD.replace(SLOT, code))
    try:
        v = gate_html(path, functional=calc_spec.functional_checks)
        return v["passed"], cost
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def main():
    ah = {"p": 0, "c": 0.0}   # always haiku
    ao = {"p": 0, "c": 0.0}   # always opus
    cas = {"p": 0, "c": 0.0}  # cascade
    settle = Counter()

    print(f"{'trial':6} {'haiku':6} {'sonnet':7} {'opus':6} {'cascade->':12} cost")
    print("-" * 55)
    for t in range(M):
        ph, ch = gen_and_gate("claude-haiku-4-5")
        po, co = gen_and_gate("claude-opus-4-8")  # baseline + cascade tier-3 reuse
        ah["p"] += ph; ah["c"] += ch
        ao["p"] += po; ao["c"] += co

        sonnet_mark = "-"
        if ph:
            tier, cost, ok = "haiku", ch, True
        else:
            ps, cs = gen_and_gate("claude-sonnet-5")
            sonnet_mark = "P" if ps else "F"
            if ps:
                tier, cost, ok = "sonnet", ch + cs, True
            else:
                tier, cost, ok = ("opus" if po else "FAIL"), ch + cs + co, po
        cas["p"] += 1 if ok else 0
        cas["c"] += cost
        settle[tier] += 1
        print(f"{t:<6} {'P' if ph else 'F':6} {sonnet_mark:7} {'P' if po else 'F':6} "
              f"{tier:12} ${cost:.4f}")

    print(f"\n=== over {M} trials ===")
    print(f"  always Haiku:  {ah['p']}/{M} passed   ${ah['c']:.4f}")
    print(f"  always Opus:   {ao['p']}/{M} passed   ${ao['c']:.4f}")
    print(f"  CASCADE:       {cas['p']}/{M} passed   ${cas['c']:.4f}")
    print(f"  settled where: {dict(settle)}")
    if ao["c"]:
        print(f"  cascade vs always-Opus: {100*(ao['c']-cas['c'])/ao['c']:+.0f}% cost, "
              f"{cas['p']-ao['p']:+d} passes")
    esc = M - settle.get("haiku", 0)
    print(f"  escalations fired: {esc}/{M}"
          + ("  <-- cascade actually did its job" if esc else
             "  (cheap tier aced it; no escalation -- cascade == cheap)"))


if __name__ == "__main__":
    main()
