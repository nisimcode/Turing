"""Constrained generation for the bill-splitter vertical (NON-GAME, Q13a).

Same pattern as the game verticals: model fills only `splitBill`, injected into a
scaffold we own. Buggy control drops the remainder (shares don't sum to total) --
the gate must catch it.

    uv run --with anthropic --with playwright --with pillow python constrained_gen_billsplit.py
"""

import os
import re
import sys
from pathlib import Path

import anthropic

from browser_gate import gate_html
import billsplit_spec

N = 5
MODEL = "claude-haiku-4-5"
HERE = Path(__file__).resolve().parent
CORPUS = HERE / "corpus"
SCAFFOLD = (HERE / "scaffold" / "tool_billsplit_scaffold.html").read_text(encoding="utf-8")
SLOT = "/*__LOGIC_SLOT__*/"

PROMPT = (
    "Implement exactly one JavaScript function "
    "`function splitBill(subtotalCents, tipPercent, people)`. All three arguments "
    "are non-negative integers (people >= 1). Rules, follow EXACTLY:\n"
    "1. tip (in cents) = Math.floor((subtotalCents * tipPercent + 50) / 100)  "
    "(round half up).\n"
    "2. total = subtotalCents + tip.\n"
    "3. Split total into `people` integer-cent shares that sum EXACTLY to total: "
    "base = Math.floor(total / people); the FIRST (total - base*people) shares are "
    "base + 1, the rest are base.\n"
    "Return an array of `people` integers. Return ONLY the function in one code block."
)

BUGGY = """
function splitBill(subtotalCents, tipPercent, people) {
  // BUG: drops the remainder -> shares don't sum to total.
  const tip = Math.round(subtotalCents * tipPercent / 100);
  const total = subtotalCents + tip;
  const each = Math.floor(total / people);
  return Array(people).fill(each);
}
"""


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


def gen_logic():
    resp = client.messages.create(
        model=MODEL, max_tokens=1024,
        messages=[{"role": "user", "content": PROMPT}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    m = re.search(r"```(?:javascript|js)?\s*\n(.*?)```", text, re.DOTALL)
    return m.group(1) if m else text


def check(v, name):
    c = next((c for c in v["checks"] if c["name"] == name), None)
    return bool(c and c["ok"])


def main():
    CORPUS.mkdir(exist_ok=True)
    print(f"Constrained generation (bill-splitter): {N} logic slots + 1 buggy\n")
    print(f"{'build':18} {'contract':9} {'logic':6} overall")
    print("-" * 42)

    conformant = logic_ok = 0
    for i in range(N):
        p = CORPUS / f"billsplit_{i}.html"
        p.write_text(SCAFFOLD.replace(SLOT, gen_logic()), encoding="utf-8")
        v = gate_html(p, functional=billsplit_spec.functional_checks)
        conformant += check(v, "contract")
        logic_ok += check(v, "billsplit_logic")
        print(f"billsplit_{i:<8} "
              f"{('ok' if check(v,'contract') else 'MISSING'):9} "
              f"{('ok' if check(v,'billsplit_logic') else 'FAIL'):6} "
              f"{'PASS' if v['passed'] else 'FAIL'}")

    pc = CORPUS / "billsplit_BUGGY.html"
    pc.write_text(SCAFFOLD.replace(SLOT, BUGGY), encoding="utf-8")
    vb = gate_html(pc, functional=billsplit_spec.functional_checks)
    print(f"{'billsplit_BUGGY':18} "
          f"{('ok' if check(vb,'contract') else 'MISSING'):9} "
          f"{('ok' if check(vb,'billsplit_logic') else 'FAIL'):6} "
          f"{'PASS' if vb['passed'] else 'FAIL'}")

    print(f"\n=== results (N={N}) ===")
    print(f"  contract conformance: {conformant}/{N}")
    print(f"  logic correct:        {logic_ok}/{N}")
    print(f"  buggy control:        {'correctly FAILED' if not vb['passed'] else 'WRONGLY PASSED'}")
    if conformant == N and not vb["passed"]:
        print("  => Recipe works on a NON-GAME tool. Generalizes beyond games (Q13a).")


if __name__ == "__main__":
    main()
