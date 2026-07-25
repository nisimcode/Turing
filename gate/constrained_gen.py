"""Constrained generation (Q12 option a): guarantee conformance by construction.

Instead of asking the model for a full app that *might* expose a hook, we own a
fixed, playable Wordle scaffold and ask the model to fill only a narrow logic
slot: `function computeFeedback(guess, answer)`. We inject it into the scaffold.
The hook + working UI are guaranteed; the only variable is the model's logic,
which the gate tests.

Also injects a known-BUGGY logic to confirm the gate still catches wrong logic
under this approach (constrained gen must not blind the gate).

    uv run --with anthropic --with playwright --with pillow python constrained_gen.py
"""

import os
import re
import sys
from pathlib import Path

import anthropic

from browser_gate import gate_html
import wordle_spec

N = 5
MODEL = "claude-haiku-4-5"
HERE = Path(__file__).resolve().parent
CORPUS = HERE / "corpus"
SCAFFOLD = (HERE / "scaffold" / "wordle_scaffold.html").read_text(encoding="utf-8")
SLOT = "/*__LOGIC_SLOT__*/"

PROMPT = (
    "Implement exactly one JavaScript function with this signature:\n"
    "  function computeFeedback(guess, answer) { ... }\n"
    "Both `guess` and `answer` are uppercase 5-letter strings. Return a "
    "5-character string; for each position i: 'G' if guess[i] === answer[i]; "
    "'Y' if the letter is in answer but in the wrong spot, correctly limited by "
    "the number of remaining copies after greens are accounted for (proper "
    "duplicate-letter handling); 'B' otherwise. Return ONLY the function in a "
    "single code block."
)

BUGGY = """
function computeFeedback(guess, answer) {
  let r = '';
  for (let i = 0; i < 5; i++) {
    if (guess[i] === answer[i]) r += 'G';
    else if (answer.includes(guess[i])) r += 'Y';
    else r += 'B';
  }
  return r;
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


def inject(logic):
    return SCAFFOLD.replace(SLOT, logic)


def check(v, name):
    c = next((c for c in v["checks"] if c["name"] == name), None)
    return bool(c and c["ok"])


def main():
    CORPUS.mkdir(exist_ok=True)
    print(f"Constrained generation: {N} logic slots from {MODEL} + 1 buggy control\n")
    print(f"{'build':16} {'contract':9} {'logic':6} overall")
    print("-" * 40)

    conformant = logic_ok = 0
    for i in range(N):
        p = CORPUS / f"scaffold_{i}.html"
        p.write_text(inject(gen_logic()), encoding="utf-8")
        v = gate_html(p, functional=wordle_spec.functional_checks)
        conformant += check(v, "contract")
        logic_ok += check(v, "wordle_logic")
        print(f"scaffold_{i:<7} "
              f"{('ok' if check(v,'contract') else 'MISSING'):9} "
              f"{('ok' if check(v,'wordle_logic') else 'FAIL'):6} "
              f"{'PASS' if v['passed'] else 'FAIL'}")

    # control: inject known-buggy logic; the gate MUST fail it
    pc = CORPUS / "scaffold_BUGGY.html"
    pc.write_text(inject(BUGGY), encoding="utf-8")
    vb = gate_html(pc, functional=wordle_spec.functional_checks)
    print(f"{'scaffold_BUGGY':16} "
          f"{('ok' if check(vb,'contract') else 'MISSING'):9} "
          f"{('ok' if check(vb,'wordle_logic') else 'FAIL'):6} "
          f"{'PASS' if vb['passed'] else 'FAIL'}")

    print(f"\n=== results (N={N}) ===")
    print(f"  contract conformance: {conformant}/{N}   (was 3/6 with free-form gen)")
    print(f"  logic correct:        {logic_ok}/{N}")
    print(f"  buggy control:        {'correctly FAILED' if not vb['passed'] else 'WRONGLY PASSED'}")
    if conformant == N and not vb["passed"]:
        print("  => Constrained gen GUARANTEES conformance AND the gate still")
        print("     catches wrong logic. Option (a) validated.")


if __name__ == "__main__":
    main()
