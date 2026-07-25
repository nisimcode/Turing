"""ARCHIVED EXPERIMENT: constrained generation for the 2048 vertical.

Model fills only `function slideRow(row)`; injected into a scaffold we own. Proves
the approach generalizes to a second, different game. Includes a buggy control
(merge-until-stable -> over-merges) that the gate must catch.

    uv run --with anthropic --with playwright --with pillow python constrained_gen2048.py
"""

import os
import re
import sys
from pathlib import Path

import anthropic

from browser_gate import gate_html
import game2048_spec

N = 5
MODEL = "claude-haiku-4-5"
HERE = Path(__file__).resolve().parent
CORPUS = HERE / "corpus"
SCAFFOLD = (HERE / "scaffold" / "game2048_scaffold.html").read_text(encoding="utf-8")
SLOT = "/*__LOGIC_SLOT__*/"

PROMPT = (
    "Implement exactly one JavaScript function `function slideRow(row)` for the "
    "game 2048. `row` is an array of 4 integers (0 means empty). Slide all "
    "non-zero values to the LEFT, then merge: when two adjacent equal values meet "
    "(after sliding), combine them into one tile of double the value. Each tile "
    "may merge at most ONCE per call -- a tile formed by a merge must NOT merge "
    "again in the same call. Return a NEW array of length 4, left-aligned, with "
    "zeros filling the remaining positions. Return ONLY the function in one code "
    "block."
)

BUGGY = """
function slideRow(row) {
  // BUG: merges repeatedly until stable -> over-merges [2,2,2,2] to [8].
  let nums = row.filter(x => x !== 0);
  let merged = true;
  while (merged) {
    merged = false;
    for (let i = 0; i < nums.length - 1; i++) {
      if (nums[i] === nums[i + 1]) { nums[i] *= 2; nums.splice(i + 1, 1); merged = true; break; }
    }
  }
  while (nums.length < 4) nums.push(0);
  return nums;
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
    print(f"Constrained generation (2048): {N} logic slots from {MODEL} + 1 buggy\n")
    print(f"{'build':18} {'contract':9} {'logic':6} overall")
    print("-" * 42)

    conformant = logic_ok = 0
    for i in range(N):
        p = CORPUS / f"g2048_{i}.html"
        p.write_text(SCAFFOLD.replace(SLOT, gen_logic()), encoding="utf-8")
        v = gate_html(p, functional=game2048_spec.functional_checks)
        conformant += check(v, "contract")
        logic_ok += check(v, "game2048_logic")
        print(f"g2048_{i:<11} "
              f"{('ok' if check(v,'contract') else 'MISSING'):9} "
              f"{('ok' if check(v,'game2048_logic') else 'FAIL'):6} "
              f"{'PASS' if v['passed'] else 'FAIL'}")

    pc = CORPUS / "g2048_BUGGY.html"
    pc.write_text(SCAFFOLD.replace(SLOT, BUGGY), encoding="utf-8")
    vb = gate_html(pc, functional=game2048_spec.functional_checks)
    print(f"{'g2048_BUGGY':18} "
          f"{('ok' if check(vb,'contract') else 'MISSING'):9} "
          f"{('ok' if check(vb,'game2048_logic') else 'FAIL'):6} "
          f"{'PASS' if vb['passed'] else 'FAIL'}")

    print(f"\n=== results (N={N}) ===")
    print(f"  contract conformance: {conformant}/{N}")
    print(f"  logic correct:        {logic_ok}/{N}")
    print(f"  buggy control:        {'correctly FAILED' if not vb['passed'] else 'WRONGLY PASSED'}")
    if conformant == N and not vb["passed"]:
        print("  => Same pattern works on a 2nd, different game. Approach generalizes.")


if __name__ == "__main__":
    main()
