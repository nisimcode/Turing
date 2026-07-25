"""Oracle construction and verification.

Implements the design validated in `stress_consensus.py` / `stress_unanimous.py`:

  * a battery is DRAFTED by the strong tier (it chooses good test inputs), but
  * the expected VALUES are then recomputed independently by a tier-diverse
    ensemble on pinned inputs -- a narrow task every tier does well (measured
    97-100%), unlike free-form battery writing where errors appear;
  * disagreement is a TRIPWIRE, not a vote: a disputed case is dropped rather
    than guessed, because a wrong expectation rejects correct code and is
    indistinguishable from a real bug (Q21).

Dropping is deliberate: a smaller correct oracle beats a larger wrong one.
"""

from __future__ import annotations

import json
from collections import Counter

from .config import ORACLE_ENSEMBLE, ORACLE_MODEL, get_logger
from .llm import call, extract_block

log = get_logger("gate.oracle")

DRAFT_PROMPT = """Produce a TEST ORACLE for this function.

  Signature: {signature}
  Behaviour: {behaviour}
  Domain (use ONLY inputs inside this set): {domain}

Output JSON only in one ```json block:
{{"tests": [{{"args": [...], "expected": ...}}, ...]}}
{n} cases. Include the edge cases a subtly-wrong implementation would fail.
Every input must lie inside the stated domain."""

RECOMPUTE_PROMPT = """Compute the exact correct return value for each input.

  Signature: {signature}
  Behaviour: {behaviour}

Work carefully -- arithmetic and edge cases matter more than speed. A wrong
value here makes a test suite reject correct code.

Output JSON only in one ```json block:
  {{"expected": [v1, v2, ...]}}
with exactly {n} values, in the SAME ORDER as the inputs.

Inputs:
{inputs}"""


def _key(v) -> str:
    return json.dumps(v, sort_keys=True, default=str)


def draft_battery(signature: str, behaviour: str, domain: str,
                  n: int = 12) -> list[dict]:
    raw = call(ORACLE_MODEL, DRAFT_PROMPT.format(
        signature=signature, behaviour=behaviour, domain=domain, n=n),
        max_tokens=2000)
    block = extract_block(raw, "json")
    if not block:
        return []
    try:
        tests = json.loads(block).get("tests", [])
    except json.JSONDecodeError:
        return []
    return [t for t in tests
            if isinstance(t, dict) and "args" in t and "expected" in t]


def verify_battery(signature: str, behaviour: str, battery: list[dict],
                   ensemble=ORACLE_ENSEMBLE) -> tuple[list[dict], list[dict]]:
    """Recompute expectations with a tier-diverse ensemble.

    Returns (agreed, disputed). A case is kept only when every voter agrees on
    the value; the agreed value replaces the draft's, so a drafting slip is
    corrected rather than trusted.
    """
    if not battery:
        return [], []
    inputs = [t["args"] for t in battery]
    listing = "\n".join(f"  {i+1}. {json.dumps(a)}" for i, a in enumerate(inputs))
    prompt = RECOMPUTE_PROMPT.format(signature=signature, behaviour=behaviour,
                                     n=len(inputs), inputs=listing)

    votes = []
    for model in ensemble:
        block = extract_block(call(model, prompt, max_tokens=2000), "json")
        try:
            vals = json.loads(block).get("expected", []) if block else []
        except json.JSONDecodeError:
            vals = []
        vals = (vals + [None] * len(inputs))[:len(inputs)]
        votes.append(vals)

    agreed, disputed = [], []
    for i, case in enumerate(battery):
        tally = Counter(_key(v[i]) for v in votes)
        top, count = tally.most_common(1)[0]
        unanimous = count == len(votes)
        if unanimous:
            value = votes[0][i]
            if _key(value) != _key(case["expected"]):
                log.info("draft corrected on %s: %r -> %r",
                         case["args"], case["expected"], value)
            agreed.append({"args": case["args"], "expected": value})
        else:
            disputed.append({"args": case["args"],
                             "values": [v[i] for v in votes]})

    if disputed:
        log.warning("dropped %d/%d disputed case(s) -- oracle uncertain",
                    len(disputed), len(battery))
    return agreed, disputed


FOCUSED_PROMPT = """Compute ONE return value. Take your time and reason it out.

  Signature: {signature}
  Behaviour: {behaviour}

  Input: {args}

Independent voters disagreed on this case, so it is subtle -- work through it
step by step, then give the answer.

Output JSON only in one ```json block: {{"expected": <value>}}"""


def resolve_disputed(signature: str, behaviour: str, disputed: list[dict],
                     ensemble=ORACLE_ENSEMBLE) -> tuple[list[dict], list[dict]]:
    """Second pass over disputed cases, one case at a time (Q23).

    Excluding a disputed case leaves that input untested, which is where a fault
    hides -- so coverage must be *restored*, not merely made safe. A single
    pinned case is a much narrower task than drafting a whole battery, and
    narrow tasks are done far more accurately (measured 97-100% across tiers),
    so re-asking per case recovers most of them.

    Returns (recovered, still_disputed). Anything still disputed is genuinely
    ambiguous -- almost always a gap in the spec, not a hard sum -- and goes to
    a human via policy.assess().
    """
    recovered, unresolved = [], []
    for case in disputed:
        prompt = FOCUSED_PROMPT.format(signature=signature, behaviour=behaviour,
                                       args=json.dumps(case["args"]))
        votes = []
        for model in ensemble:
            block = extract_block(call(model, prompt, max_tokens=1200), "json")
            try:
                votes.append(json.loads(block)["expected"] if block else None)
            except (json.JSONDecodeError, KeyError):
                votes.append(None)
        tally = Counter(_key(v) for v in votes)
        _, count = tally.most_common(1)[0]
        if count == len(votes):
            recovered.append({"args": case["args"], "expected": votes[0]})
            log.info("recovered disputed case %s -> %r", case["args"], votes[0])
        else:
            case["focused_votes"] = votes
            unresolved.append(case)
            log.warning("case %s still disputed after focused pass: %s",
                        case["args"], votes)
    return recovered, unresolved


def build_oracle(signature: str, behaviour: str, domain: str, n: int = 12,
                 resolve: bool = True) -> tuple[list[dict], list[dict]]:
    """Draft a battery, ensemble-verify it, then try to recover disputes.

    Returns (battery, still_disputed).
    """
    draft = draft_battery(signature, behaviour, domain, n=n)
    agreed, disputed = verify_battery(signature, behaviour, draft)
    if resolve and disputed:
        recovered, disputed = resolve_disputed(signature, behaviour, disputed)
        agreed.extend(recovered)
        log.info("dispute resolution: recovered %d, %d remain",
                 len(recovered), len(disputed))
    return agreed, disputed
