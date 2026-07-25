"""Human-review policy -- `docs/gate-operations.md` §2 as executable rules.

The governing rule (§1): false accepts are fatal, false rejects only cost
margin. Every ambiguous call resolves toward reject-and-escalate, never toward
accept.

That is why a DISPUTED oracle case is never silently dropped. Dropping removes
the input from testing altogether, so a bug living there sails through -- which
trades a false reject for a false accept, exactly the wrong direction. Disputed
cases are excluded from the pass/fail battery but recorded, and they make the
verdict PROVISIONAL until a human resolves them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .telemetry import record


@dataclass
class Review:
    """Why a human is needed, and what they must decide."""
    required: bool
    reasons: list[str] = field(default_factory=list)
    provisional: bool = False        # verdict cannot be trusted as final

    def __bool__(self) -> bool:
        return self.required


def assess(*, vertical: str, is_new_vertical: bool = False,
           disputed_cases: list | None = None,
           top_tier_failed: bool = False,
           spec_deviates: bool = False,
           alarms: list[str] | None = None) -> Review:
    """Decide whether this run needs a human, per the ops-doc trigger table."""
    reasons: list[str] = []
    provisional = False

    if is_new_vertical:
        reasons.append(
            "new vertical: its oracle has never been validated against the "
            "spec, and a wrong oracle is indistinguishable from wrong code")

    if disputed_cases:
        provisional = True
        reasons.append(
            f"{len(disputed_cases)} oracle case(s) disputed by the ensemble and "
            f"therefore NOT tested -- a fault at those inputs would pass "
            f"unnoticed; resolve them before treating this verdict as final")

    if top_tier_failed:
        reasons.append(
            "the strongest tier failed the gate: there is nowhere left to "
            "escalate, so this must be rejected to a human, never auto-accepted")

    if spec_deviates:
        reasons.append(
            "spec contradicts a common convention: cheap tiers revert to their "
            "training prior together (53-88% vs 100% strong), so confirm the "
            "deviating rule by hand")

    for a in (alarms or []):
        reasons.append(f"alarm: {a}")

    rev = Review(required=bool(reasons), reasons=reasons, provisional=provisional)
    if rev.required:
        record("review_required", vertical=vertical, reasons=reasons,
               provisional=provisional)
    return rev


def explain(rev: Review) -> str:
    if not rev.required:
        return "no human review required"
    head = "PROVISIONAL - human review required" if rev.provisional \
        else "human review required"
    return head + "\n" + "\n".join(f"  - {r}" for r in rev.reasons)
