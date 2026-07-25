# Gate operations — human review, monitoring, and failure handling

Answers Q18. Every rule here is grounded in a measured result; the source is
cited so the rule can be re-derived (or overturned) when the evidence changes.

The gate is trustworthy in aggregate but has three known blind spots. This
document says who watches them and when.

---

## 1. The one rule that governs everything

**False accepts are fatal; false rejects only cost margin.** Ship broken work and
you lose the customer; escalate unnecessarily and you lose a few cents. Every
ambiguous call resolves toward *reject and escalate*, never toward *accept*.

Corollary: **correctness is a floor, never a user-facing dial.** The user may
tune effort, polish, and budget *above* "it works" — never below it.

---

## 2. Where humans are required

Automation covers the steady state. Humans cover creation and anomalies.

| Trigger | Why | Action |
|---|---|---|
| **A new vertical is created** | The oracle has never been validated for this spec. A wrong oracle is invisible: it looks exactly like wrong code. | Human reviews the generated oracle/reference against the spec once, before the vertical serves traffic. One-time cost per vertical. |
| **The spec deviates from a common convention** | Cheap tiers revert to their training prior and fail *together*: 53–88% vs 100% for strong tiers (`stress_unanimous.py`). | Flag at authoring time. Require strong-tier oracle + human confirmation of the deviating rule. |
| **The strongest tier fails the gate** | There is nowhere left to escalate. The lazy failure mode is to accept anyway "because it's the best we have" — that is the fatal error. | Reject. Route to a human. Never auto-accept a top-tier failure. |
| **Flag rate leaves its normal band** | Disagreement rate is a live difficulty signal (§3). | Investigate the spec before it silently burns budget. |
| **Ambiguous-edge disagreement** (Q21) | Broad coverage hits inputs the spec never addressed (e.g. `""` as a card number); the reference's arbitrary choice becomes "truth" and correct code fails. | Do not auto-fail. Surface as *spec clarification needed* — the fix is a better spec, not a different implementation. |

Everything else runs unattended.

---

## 3. Flag-rate monitoring

Oracle disagreement is measured per case and **self-adjusts to spec difficulty**
(D24) — the system spends more verification effort exactly where the work is
unusual:

| Spec type | Observed flag rate | Source |
|---|---|---|
| Canonical / conventional | ~3% | `oracle_consensus.py` (1/30) |
| Prior-fighting / non-standard | ~50% | `stress_consensus.py` (16/32) |

Use it as an alarm, not just a cost line:

- **Flag rate spikes on a stable vertical** → the spec changed, the model
  changed, or an input distribution shifted. Investigate before it costs money.
- **Flag rate near zero on a *new* vertical** → suspicious, not reassuring. It
  may mean the oracle ensemble lacks tier diversity (D22: three samples of one
  cheap model are one opinion, not three) and cannot disagree.
- **Sustained high flag rate** → the spec is fighting the models. Rewrite the
  spec, or pin the vertical to the strong tier and stop paying for the pre-filter.

---

## 4. Resolution rules

**Oracle disagreement → escalate, never vote** (D21). Majority voting is unsafe:
correlated cheap-tier failure produced a confidently wrong majority (45/51) while
the strong tier was perfect (51/51). Unanimity ⇒ accept; any disagreement ⇒ the
strong tier decides that case.

**Coverage by domain size** (D28). Enumerate exhaustively when the input domain is
finite and ≤100k cases; differential-fuzz otherwise. This removed arbitrary-point
false accepts entirely (3/15 → 1/15 → 0/15 across battery → fuzz → coverage-aware).

**Content/UI verticals are floor-only** (Q13b). Objective checks catch crash,
missing sections, mobile overflow, contrast failures, and collisions (5/5), but
taste and copy quality pass everything (2/2). Sell those verticals as *guaranteed
working, accessible, complete* — never as *guaranteed good*.

---

## 5. Standing limitations — do not design these away

- **The gate is not a security boundary** (D26). A fault behind an arbitrary
  trigger evades any finite battery. It catches honest mistakes, not deliberately
  hidden behaviour. Do not let this be marketed as a safety guarantee.
- **Unanimous-wrong is possible in principle** (Q18/Q17 residual). Not observed in
  83 adversarial inputs, but the defense rests on at least one strong tier
  resisting the prior. A spec strange enough to flip every tier would pass
  silently. The one-time human review of each new vertical exists for this.
- **Sample sizes are small.** Every figure above is directional evidence, not
  proof. Re-measure as volume grows.
