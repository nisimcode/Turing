# Project Log — Turing

**Purpose:** the single running record of this project — decisions made, steps
finished, plans set, and open questions (with when they must be answered). Not a
transcript. Updated as work progresses; newest entries at the top of each section.

**How to maintain:** when a decision is made, add a `D#` row. When a step
finishes, add it to Milestones. When a question arises, add a `Q#` with "when
needed"; when answered, mark it ANSWERED and note the answer. **Stamp new entries
with date AND time** (`YYYY-MM-DD HH:MM TZ`). Keep it terse. (Entries before
2026-07-25 17:29 JDT are date-only — exact times weren't recorded.)

---

## Current status (2026-07-26 00:17 JDT)

A point-in-time snapshot — replaced wholesale on each update. The chronological
record lives in *Milestones*; do not append history here.

**What the project is.** An adoption-first, free local **verification gate** for
AI-generated, self-contained HTML/JavaScript tools. The dependable product is a
deterministic manifest + isolated browser verifier, not a model router: it
requires no API key or hosted service. The earlier cascade, oracle, and
auto-vertical work remains measured research, not the public product surface.

**Where the code is.** Public repo `nisimcode/Turing` (branch `main`), licensed
Apache 2.0 with releases `v0.1.0` and `v0.1.1`. `gate/cli.py` exposes the packaged
`turing-gate` command; `gate/core/manifest.py` binds a local artifact, browser
hook, domain schema, and exact cases; `gate/core/verify.py` and `sandbox.py`
provide the fail-closed runtime. The wheel includes only the CLI, core, and
three bundled demonstrations. Model-assisted auto-vertical generation, review
research, Q21-Q26 runners, and historical evidence stay in the source tree but
are excluded from the installed wheel.

**What is proven (with numbers).**

| Claim | Evidence |
|---|---|
| An outside artifact can use the gate without Python changes or an API key | versioned JSON manifest: correct control PASS; directory escape and malformed domain schema rejected; `init` creates validated runtime-only or explicit-case functional starters; bundled Wordle/calculator/exfiltration defects caught 3/3 |
| The public tool is independently installable | `uv build --no-sources` produced sdist + wheel; isolated `uvx --from <wheel> turing-gate demo` passed 3/3 |
| The tagged release is publicly fetchable | refreshed `uvx --from git+https://github.com/nisimcode/Turing@v0.1.0 turing-gate demo` resolved public commit `0c04f61` and caught 3/3 defects |
| The locked public/runtime Python dependency set is clean | experimental `uv audit`: 20 packages checked, no known vulnerabilities or adverse project statuses |
| Setup failures are locally diagnosable | `turing-gate doctor`: 8/8 healthy-environment checks PASS; forced missing-browser path returns not-ready with exact repair command |
| The wheel works in clean hosted environments | first main run `30173582765`: Ubuntu PASS in 36s, Windows PASS in 53s; exact `v0.1.1` tag run `30173641636`: Ubuntu PASS in 38s, Windows PASS in 54s; install → doctor → 3 demos → user example, no retries |
| A clean user can generate rather than hand-write the manifest shell | v0.1.2 candidate run `30175194327`: built-wheel `init` created a functional manifest and its immediate verification passed on Ubuntu and Windows; full jobs passed in 2m37s/2m55s |
| The new tagged CLI is publicly fetchable | refreshed HTTPS `uvx` resolved `v0.1.1` to commit `1b06f3f`; `doctor --json` passed all 8 setup checks |
| The public manifest path is stable across varied logic tools | paired `logic-tools-v1`: 6 domains / 12 subjects, 12/12 decisions, 0 false accepts/rejects, 6/6 diagnostics locally and in hosted run `30173955145`; local median/p95 1.453s/1.484s, Ubuntu 1.491s/2.069s, Windows 1.569s/1.908s |
| The paired cases resist separately generated faults | six-domain mechanical challenge: initial 22/27 killed (81%); five survivors exposed missing email-anchor and bottom-row cases; distinct scored values raised the result to 27/27 (100%) while 22 validation probes remain exact-disjoint; hosted run `30174711088` reproduced 27/27 on Ubuntu and Windows |
| The gate catches faults nobody here thought of | mutation score **100%**, 15/15 execution-validated mutants killed |
| Auto-generated batteries have measured fault coverage | Caesar auto-battery mutation score **100%**, 5/5 execution-validated mutants killed over 498 independent probes |
| Undefined inputs do not become false rejects | Q21 regression withheld 2/2 out-of-domain Luhn cases; correct implementation PASS, 0 false rejects |
| False accepts are eliminated for realistic bugs | **0/15** with coverage-aware gating (enumerate small domains, fuzz large) |
| Bad oracles are detectable without ground truth | **55/55** oracle errors flagged by tier-diverse disagreement; 0 unanimous-wrong in 83 adversarial inputs |
| The gated cascade saves money without losing measured correctness | Q26: **21/21** correct vs always-strong 21/21, 0 false accepts/rejects, 14.3% escalation, **65.7% lower modeled cost** |
| The cheap tier suffices behind the gate | pass@1 **30/30** across wordle, game2048, billsplit (Wilson 95% CI [72%, 100%]) |
| The recipe generalizes | 4 hand-built verticals + auto-generated verticals accepting correct code 3/3 |
| Untrusted code is contained | exfiltration probe blocked 4/4 (fetch, pixel, beacon, XHR) |

**Scope boundary.** Strong guarantees only where the critical logic is a
checkable pure function (games, calculators, validators). Content/UI is
**floor-only**: objective checks caught 5/5 structural defects but 2/2 subjective
ones passed. Sell those as *working, accessible, complete* — never as *good*.

**Adoption-release engineering ≈ 99%; adoption evidence = 0/20 developers,
0/5 user-owned artifacts, 0/3 repeat users.** Apache licensing, local package,
no-API manifest, three demonstrations, isolated-wheel smoke test, unified
zero-credit regression, public repository, and tagged GitHub releases are
complete. `doctor` and clean Windows/Linux wheel CI pass locally and on both
fresh hosted runners. Hosted runners are only a setup proxy: unassisted
onboarding and outside adoption remain unproven. Q25’s
prepared human sample
now applies only to the experimental auto-vertical path and does not block the
deterministic public verifier.

**Standing caveats.** Sample sizes are small throughout (directional, not proof).
The gate is a correctness check, **not a security boundary** — an arbitrary
trigger evades any finite battery. Docker is absent on this host, so isolation
covers browser-executed content only; a container is required before artifacts
gain build steps, servers or native deps (`npm install` runs arbitrary code).
Recurring lesson: the concepts have held up, but **harness bugs are the frequent
failure** — three today (floor `has_dom`, fence-matching regex, mutation hook)
each briefly masqueraded as a real finding. Verify surprising results before
believing them.

**Next action.** Tag and publish the now-hosted-green v0.1.2 artifacts, verify
the public tag, then begin the genuine outside 20/5/3 adoption test. No further
internal benchmark should delay that test.

---

## Decision log

| # | Date/time | Decision |
|---|------|----------|
| D60 | 2026-07-26 00:13 JDT | **Finish pre-adoption engineering by removing manifest boilerplate without guessing correctness.** `turing-gate init` creates a version-1 manifest beside an existing confined HTML artifact. Functional mode requires an explicit hook and JSON cases; otherwise the result is prominently runtime-only. Validate through the production loader before atomic publication, refuse overwrite unless `--force`, and leave no partial file on invalid JSON/schema/path. The public regression covers runtime-only and functional success plus overwrite, malformed-constant and path-escape failures. The independently validated mutation benchmark now also self-tests missing markers, missing probe domains and probe/scored-case contamination before browser execution. Ship this bounded onboarding/harness improvement as v0.1.2, then stop substituting internal work for adoption evidence. |
| D59 | 2026-07-25 23:59 JDT | **A zero-API path must not import optional model dependencies.** The first hosted mechanical-benchmark run (`30174575349`) passed wheel setup and the paired benchmark on both OSes, then failed before mutation execution because `core.mutation` eagerly imported `core.llm` and therefore `anthropic`. Move that import inside `validated_mutants()`, the only paid generation path. A forced-SDK-unavailable import, Q24, and the 27/27 mechanical challenge pass locally; corrected hosted run `30174711088` then reproduced 27/27 on both OSes. |
| D58 | 2026-07-25 23:55 JDT | **Challenge hand-authored cases with separately generated, execution-validated faults.** Each correct benchmark implementation has a marked mutation surface. Generic one-site mutations count only if they produce a wrong result on versioned domain-valid probes whose exact inputs are absent from the scored manifests; survivors are reported, never silently discarded. The first run killed 22/27 (81%): unanchored email regexes and damaged bottom-row indices survived. Adding different email-whitespace and bottom-row values to the scored cases raised the bounded result to 27/27 (100%). Require that score in the unified checkpoint and Windows/Linux CI, while stating plainly that six toy domains and a fixed mutation operator set do not estimate unknown-fault or production reliability. |
| D57 | 2026-07-25 23:36 JDT | **Benchmark the public gate with paired controls and explicit failure semantics.** `logic-tools-v1` fixes one artifact and case set per domain, then invokes correct and deliberately broken hooks separately. Report false accepts, false rejects, diagnostic hits, total/median/p95 runtime, and category rollups; fail unless every correct control is accepted, every broken control rejected, and every rejection identifies the intended edge label. The initial corpus spans shipping, duration, email, slug, CSV and tic-tac-toe (12 subjects). Because faults and cases were hand-authored together, treat 12/12 as regression coverage only—not an unknown-fault rate, production reliability estimate, or adoption evidence. |
| D56 | 2026-07-25 23:25 JDT | **Defer the difficult human-adoption step without pretending automation replaces it.** Use fresh Windows/Linux GitHub-hosted runners as the reproducible cold-environment proxy, and add a zero-API `turing-gate doctor` that checks Python/package identity, local-state writes, loopback binding, Playwright, Chromium presence, and a real browser launch. CI must build and install the wheel, diagnose setup, catch 3/3 demos, and accept the user example. These runs improve distribution confidence but count as 0 developers, 0 own artifacts, and 0 repeat users in the 20/5/3 test. |
| D55 | 2026-07-25 23:05 JDT | **Pivot from proprietary research prototype to an Apache-2.0, adoption-first local developer tool.** The dependable product surface is `turing-gate verify turing.json`: a versioned deterministic manifest, directory-confined self-contained HTML artifact, dotted browser hook, optional domain schema, and exact cases. It needs no model/API key; writes only local `.turing/telemetry.jsonl`; and returns distinct pass/reject/setup exit codes. The wheel excludes auto-vertical and experiment runners. Three bundled known-bad demos catch Wordle duplicates, negative division, and four-vector exfiltration. Success is now 20 outside verifications / 5 own artifacts / 3 repeat users in 30 days, not more internal research. Supersedes D29’s proprietary licence and makes Q25 non-blocking for the public path. |
| D54 | 2026-07-25 22:39 JDT | **Ignore rules must protect machine state without hiding legitimate project artifacts.** Reorganized `.gitignore` into secrets, Python, Node, workspace/tool caches, generated model/runtime output, browser artifacts, editor/OS state, and Repomix bundles. Added local agent directories, Python analysis/coverage/build caches, package-manager logs, and generic workspace caches; generalized `.llm-cache/` to every location. Replaced broad `*.zip` with Playwright-specific `trace.zip` so a legitimate archive remains trackable. Verified all generated paths are ignored while `.env.example`, `.repomixignore`, `package.json`, and `pnpm-lock.yaml` remain trackable. |
| D53 | 2026-07-25 22:37 JDT | **Repository snapshots use a pinned, local Repomix with explicit secret/context exclusions.** Added private Node tooling with Repomix 1.17.0 pinned in `package.json`/`pnpm-lock.yaml`; `.repomixignore` excludes `.env`, machine-local state, dependencies/caches, generated review/runtime/Q26 data, the concluded archive, bundles, and lockfile noise while retaining `.env.example` and active source. Default sensitive-data scanning stays on. A real pack included 45 intended files and excluded every protected class. `pnpm audit` reports 0 high/critical and one moderate transitive Windows `serve-static` advisory in `@hono/node-server` via the optional MCP SDK; no compatible 1.x patch exists and the pack-only workflow does not start that server. |
| D52 | 2026-07-25 22:35 JDT | **Keep only operational documents and reachable symbols on the active path.** Moved the completed implementation plan and two superseded strategy documents to `archive/plans/`; removed three unreferenced constants, five regenerated bytecode directories, and one stale HTML queue export. Preserved response caches, Q25 dossiers/queue, Q26 checkpoint, telemetry, and all empirical evidence because they still support free replay, pending review, or audit. Static import/symbol/reference checks and the full zero-credit checkpoint pass. |
| D51 | 2026-07-25 22:25 JDT | **Q25’s human sample contains only exact-revision packets that cleared every automated prerequisite.** Schema-derived disjoint probes replace a paid probe call; one model-proposed mutant plus generic local source mutations are execution-validated, and a killed mutant becomes the dossier control. Fourteen generated requests yielded 10 eligible dossiers (50/50 mutants killed), 2 provisional domain mismatches, 1 no-oracle failure, and 1 mutation-score failure; blocked/provisional records remain auditable but are excluded from `list --eligible`. Human outcomes and timing are structured and summarized by `q25-report`. |
| D50 | 2026-07-25 21:51 JDT | **The measured cheap-first cascade preserves correctness while materially reducing cost on the fixed Q26 workload.** Across 7 tasks × 3 paired trials, always-cheap delivered 18/21 correct, always-Opus 21/21 at $0.16421, and the gated cascade 21/21 at $0.05636: 65.7% modeled savings and $0.00268/correct vs $0.00782. The gate recorded 39 true accepts, 3 true rejects, 0 false accepts, 0 false rejects; all 3 cheap failures escalated and recovered (14.3%). Treat n=21 as directional, not a commercial reliability bound. |
| D49 | 2026-07-25 21:38 JDT | **Keep the active gate operationally small; archive research evidence instead of deleting it.** Moved 29 concluded runners/docs/fixtures from `gate/` to `archive/gate-experiments/` with explicit archival markers. Removed unreachable `ORACLE_PROMPT`, legacy `build_oracle()`, unused sandbox `evaluate()`, three unused config constants, and one unused import. Active reference/import scans are clean; active + archived syntax and the full zero-credit checkpoint pass. |
| D48 | 2026-07-25 21:30 JDT | **Human testing begins only after one unified zero-credit checkpoint passes.** `offline_all_check.py` composes review/lifecycle failure paths, Q21, Q24, correct/broken functional controls, and the exfiltration control. A review packet must independently show all seven release checks passing. The human then judges only spec intent, oracle meaning, domain/UI alignment, and usability using `docs/human-testing.md`. |
| D47 | 2026-07-25 21:30 JDT | **Approval is exact-revision, evidence-bound, and fail-closed.** SHA-256 binds the scaffold, implementation, buggy control, sharpened spec, and oracle battery. Only `approved` releases that revision; any changed revision, pending/clarified/rejected state, failed/missing automated check, provisional case, top-tier failure, empty note, corrupt history, or material/hash mismatch is blocked. `verify_cli --require-approved` enforces it. |
| D46 | 2026-07-25 21:22 JDT | **Prompt caching is explicit and opt-in, never blanket automatic.** The local exact-response cache remains primary because a hit makes no request; Anthropic prompt caching still pays for generation and is allowed only on a large stable system prefix via `call(cache_system=True)`. Billing now includes uncached input, 5m/1h writes, reads, and output from the API usage fields. Fake-client regression proves request shape and arithmetic without an API call. |
| D45 | 2026-07-25 21:22 JDT | **Human review is an append-only, deduplicated workflow with stable IDs.** `policy.assess()` opens a local queue item; repeated identical pending triggers reuse it; resolution appends `approved`/`clarified`/`rejected` plus a required note; escaped HTML is read-only. Review-only commands must not import Playwright. Applying the disposition to persistent vertical state remains the next step. |
| D44 | 2026-07-25 21:13 JDT | **A prose domain is not enforceable; every auto-vertical needs a machine-readable argument schema.** Filter draft oracle cases against it before ensemble voting or execution. Out-of-domain cases and missing schemas trigger spec clarification and make the vertical provisional; they never fail the implementation. Offline Luhn regression withheld `""` and `"0"` from a 2–19 digit domain while correct code passed (0 false rejects). |
| D43 | 2026-07-25 21:10 JDT | **Q24 answered; combine model-proposed and standard mechanical mutants.** Model generation produced only 1 real fault from 4 cached attempts; deterministic source mutation supplied four more at $0. Every mutant still counts only after independent execution demonstrates a divergence. The auto-generated Caesar battery killed **5/5**, with 0 survivors over 498 disjoint probes. One disputed oracle case was restored with an independent Python reference (14/14 battery, zero unresolved). |
| D42 | 2026-07-25 21:03 JDT | **Do not close Q24 on a flattering n=1.** The first live auto-battery score is 100% (1/1), but the acceptance target is ≥5 independently validated mutants and zero unresolved oracle cases. A paid-call cap must return a partial score instead of crashing; partial evidence is reported as PARTIAL, never promoted to a headline claim. |
| D41 | 2026-07-25 20:53 JDT | **Paid experiments must be resumable and locally preflighted.** `core.llm.call()` can checkpoint successful responses by exact request and enforce a persistent paid-response cap; cache hits are free and do not consume the cap. Q24 runs one selected vertical at a time only after `offline_q24_check.py` passes the complete browser/mutation path at $0. |
| D40 | 2026-07-25 20:33 JDT | **An auto-battery's mutation witnesses must be independent of that battery.** Validating mutants on the cases being scored makes 100% tautological. Q24 generates a second, domain-constrained input pool, removes every battery input and every case the baseline cannot execute, execution-validates mutants only on that disjoint pool, then measures whether the original battery kills them. |
| D39 | 2026-07-25 19:56 JDT | **Mutation score is the gate's headline quality metric.** "Catches the bugs we injected" only proves it catches faults we thought of. A mutant counts only once EXECUTION shows a behavioural divergence (models predicted non-existent bugs 2/3 of the time); score = validated mutants killed / validated mutants. Production batteries score **100% (15/15)**. |
| D38 | 2026-07-25 19:56 JDT | **Disputed oracle cases get a focused second pass** (`resolve_disputed`) before being escalated to a human: one pinned case at a time is a far narrower task than drafting a battery, and narrow tasks are done accurately (97-100%). Restores coverage instead of permanently excluding the input; anything still disputed is a spec gap, not arithmetic, and goes to review. |
| D37 | 2026-07-25 19:45 JDT | **Ops doc is now code**: `core/telemetry.py` (durable JSONL of every verdict + flag-rate/pass-rate alarms with the measured 3%/50% baselines) and `core/policy.py` (`assess()` implements the §2 trigger table, returning reasons + a `provisional` flag). `verify()` records every run. |
| D36 | 2026-07-25 19:45 JDT | **Disputed oracle cases must NOT be silently dropped.** Dropping removes that input from testing entirely, so a fault there passes — trading a false reject for a false *accept*, the opposite of the founding rule (D8). Disputed cases are excluded from the battery but recorded, and they make the verdict **PROVISIONAL** pending human resolution. Corrects my own initial design in `core/oracle.py`. |
| D35 | 2026-07-25 19:45 JDT | **Auto-verticals need spec sharpening + an ensemble-verified oracle, together.** Sharpening alone failed (it *widened* the domain to "any JavaScript value" and invented semantics); the fix is a sharpening pass constrained to a NARROW domain, plus recomputing expected values with a tier-diverse ensemble on pinned inputs. Result: correct code accepted 1/3 → **3/3**. |
| D34 | 2026-07-25 19:24 JDT | **Auto-scaffolding is viable; the weak link is SPEC PRECISION, not scaffold generation.** 3/3 auto-generated scaffolds were structurally sound (slot + hook + floor pass); the failures came from underspecified `behaviour` text letting oracle and implementation diverge on edge cases. Fix belongs in the spec step (enumerate edge-case handling, or restrict the oracle's domain to what the spec defines) — same root cause as Q21. |
| D33 | 2026-07-25 19:24 JDT | **All untrusted artifacts execute sandboxed** (`gate/core/sandbox.py`): ephemeral 127.0.0.1 origin rooted in a temp dir (no `file://` host access), every non-artifact request aborted, fresh browser context per run, dialogs/downloads refused, hard timeouts. Outbound attempts are also *reported* — `no_outbound_requests` is a floor check, so code that phones home fails the gate. Docker unavailable on this host; scope limited to single-file HTML/JS, containers still required for build steps/servers/native deps. |
| D32 | 2026-07-25 19:24 JDT | **Consolidated into a `gate.core` package** with one entry point `verify(artifact, functional=...) -> Verdict`, shared config/tiers/pricing, cost accounting and logging — replacing ~12 scripts that each carried their own key loader and browser setup. Verification deliberately does **not** import the Anthropic SDK (lazy), so gating runs in a minimal environment. |
| D31 | 2026-07-25 18:57 JDT | **Gate operations spec written** (`docs/gate-operations.md`) — answers Q18. Humans review at *creation* (each new vertical's oracle) and on *anomaly* (deviating spec, top-tier failure, flag-rate excursion, ambiguous edge); everything else runs unattended. Flag rate doubles as a live spec-difficulty alarm — and near-zero on a NEW vertical is suspicious (may mean the ensemble lacks tier diversity), not reassuring. |
| D30 | 2026-07-25 18:57 JDT | **Content/UI verticals are FLOOR-ONLY.** Objective checks guarantee *working, accessible, complete*; they cannot judge *good*. Sell those verticals on the floor, not on quality — and lead commercially with logic-verifiable verticals where the oracle decides correctness outright. |
| D29 | 2026-07-25 18:53 JDT | **SUPERSEDED by D55.** Initial licence was proprietary / all rights reserved. |
| D28 | 2026-07-25 18:53 JDT | **Coverage-aware gating is the production design** (`gate/coverage_gate.py`): the strong tier declares the input domain; enumerate exhaustively when finite and ≤100k cases, otherwise differential-fuzz. Removes arbitrary-point false accepts entirely (0/15). Accept the resulting rise in spec-ambiguity false rejects — trading fatal errors for margin cost. |
| D27 | 2026-07-25 18:41 JDT | **Gate strategy by domain size: enumerate exhaustively when the input domain is small and finite (e.g. int 1..3999); random differential fuzzing otherwise.** Fuzz coverage is only as good as the generator's distribution — the one L5 miss was an unreachable-in-practice value under a skewed generator, which exhaustive enumeration removes entirely. |
| D26 | 2026-07-25 18:35 JDT | **The gate is a correctness check, NOT a security boundary.** An arbitrary trigger (magic value / rare substring) reliably evades a finite battery, so the gate cannot be relied on to stop deliberately hidden behaviour. Fine for verifying honest generation; do not market it as a safety guarantee against malicious code. |
| D25 | 2026-07-25 18:35 JDT | **Move from fixed batteries to differential/property testing where the slot is a pure function.** Have the strong tier emit a REFERENCE IMPLEMENTATION as well as cases, then fuzz the cheap model's slot against it over random inputs. Converts finite coverage into probabilistic coverage of the whole input space — the only way to close the L5 gap. |
| D24 | 2026-07-25 18:24 JDT | **The flag rate self-adjusts to spec difficulty** — 3% flagged on canonical specs, 50% on prior-fighting ones. The system automatically spends more verification effort where the spec is unusual. This is the adaptive behaviour originally wanted from a "boss", achieved by *verification* rather than *prediction*. |
| D23 | 2026-07-25 18:24 JDT | **The STRONG tier is the oracle authority; the cheap ensemble is a cost-saving pre-filter that decides when to consult it.** Across both stress tests Sonnet/Opus were 100% correct and a strong tier was right on 100% of inputs; safety rests on that, not on voting. Cheap models only decide *when* to ask. |
| D22 | 2026-07-25 18:18 JDT | **Ensemble DIVERSITY beats ensemble size.** 3 samples of the same cheap model are highly correlated — they failed together. The disagreement signal only existed because tiers differed (Haiku vs Sonnet/Opus). Always build the oracle ensemble across model *tiers*, never as N samples of one model. |
| D21 | 2026-07-25 18:18 JDT | **Use disagreement as a TRIPWIRE, not a vote.** Never majority-vote oracle values: on adversarial specs the 3 cheap voters were wrong together and the majority was confidently wrong (45/51 vs Opus 51/51). Correct design: cheap ensemble → if unanimous, accept; if ANY disagreement, escalate that case to the strongest model (or a human). Opus was right on 100% of flagged cases. |
| D20 | 2026-07-25 18:18 JDT | **QUALIFIES D19 / partly restores D18.** Cheap-ensemble oracles are only sufficient on canonical tasks. When the spec CONTRADICTS a famous convention (real custom business rules), cheap models revert to the prior and fail together: Haiku 84–88% vs Sonnet 100% / Opus 100%. Strong models earn their price on instruction-following against a trained prior. |
| D19 | 2026-07-25 18:09 JDT | **REVISES D18. Decompose the oracle task, then ensemble cheap models.** Split oracle generation into (1) choose test inputs and (2) compute expected values for pinned inputs. Step 2 is narrow: 3× Haiku majority scored 30/30 at $0.023 vs 1× Opus 29/30 at $0.045 — cheaper AND more accurate. Don't buy a big model for the oracle; buy decomposition + redundancy. (D18 held only for one free-form "write the whole battery" ask.) |
| D18 | 2026-07-25 18:03 JDT | **Tier by ROLE, not by task difficulty:** cheap model *generates code*, strong model *generates the oracle/gate*. Evidence: auto-oracle wrong 2/3 (Haiku) vs 0/3 (Opus) — the first measured case in the whole project where the strong model outperformed. Spend on the verifier, not the builder. |
| D17 | 2026-07-25 17:29 JDT | Standardize the **vertical recipe**: scaffold we own + narrow logic slot + Python oracle + gate + buggy control. Adding a game = new scaffold + spec + prompt (no gate changes). Proven on a 2nd game (2048). |
| D16 | 2026-07-25 | **Constrained generation (Q12a):** own a fixed playable scaffold per game type; the model fills only a narrow logic slot (`computeFeedback`). Conformance + working UI guaranteed by construction. This is the gate/generation approach for the game vertical. |
| D15 | 2026-07-25 | Adopt a **generation contract** (`window.__wordle.{setAnswer,guess}`) so functional gating generalizes across implementations (see `gate/contract.md`). Answers Q9. |
| D14 | 2026-07-25 | **The gate IS the product**; cascade/routing/dial are thin wrappers. Organize effort and planning around the gate as the spine, built in layers (runtime floor → functional → acceptance criteria → judge), not one phase. |
| D13 | 2026-07-25 | First vertical = **single-file (no-build) browser games** (Wordle-like). Answers Q1 and Q4. |
| D12 | 2026-07-25 | Adopt the gate-first phased plan now archived at `archive/plans/implementation-plan.md`. |
| D11 | 2026-07-25 | Start narrow: small self-contained, browser-testable apps (Wordle-like) first — not IGN-scale sites. |
| D10 | 2026-07-25 | Objective checks are the primary gate; LLM judge is secondary — may withhold (escalate) but never approve past an objective failure. |
| D9  | 2026-07-25 | Route/decide on pass@k (rates), never single runs. |
| D8  | 2026-07-25 | Tune the gate conservative: prefer false-rejects to false-accepts — but only up to the point where the cascade still beats always-strong. |
| D7  | 2026-07-25 | Correctness is a non-negotiable floor. The user-facing dial governs effort/polish/budget *above* "it works" — framed as such, never as a reliability knob. |
| D6  | 2026-07-25 | The gate is the backbone; build and *validate* it before any cascade. Do-or-die. |
| D5  | 2026-07-25 | Product target = model cascade for commercial "build me X" web apps (e.g. IGN-like sites, Wordle-like games). |
| D4  | 2026-07-25 | Tiers: Haiku 4.5 (cheap) → Sonnet 5 (mid) → Opus 4.8 (strong) → Fable 5 (optional, deferred: pricier, access/retention constraints). |
| D3  | 2026-07-25 | Tooling: run Python via `uv`; API key read from `E:\Turing\.env` (`CLAUDE_API_KEY`). |
| D2  | 2026-07-25 | Validate empirically with cheap dry runs before building anything. |
| D1  | 2026-07-25 | Pivot from the original "AI Boardroom (Turing)" concept toward escalation/routing (now `archive/plans/plan.md`), then refined to a model cascade. |

---

## Milestones completed

- **2026-07-26 00:13 JDT** — **v0.1.2 onboarding candidate completed
  locally.** Added `turing-gate init` with explicit functional cases, honest
  runtime-only fallback, path confinement, pre-publication production-schema
  validation, atomic output, and opt-in overwrite. Public-path regression
  proves both modes and the failure paths. Added three no-browser mutation
  configuration guards. The full zero-credit checkpoint passed in 195.9s:
  paired 12/12, diagnostics 6/6, mechanical 27/27, and all Q21-Q26 controls.
  Built the wheel/sdist, found no known vulnerabilities in 20 dependencies,
  then used an isolated wheel to generate and successfully verify a functional
  shipping manifest. Hosted run `30175194327` then passed the exact built-wheel
  flow on both systems, including manifest generation and immediate functional
  verification: Ubuntu 2m37s, Windows 2m55s. Release publication remains.
  → D60.
- **2026-07-26 00:03 JDT** — **Independent-fault challenge reproduced in
  clean hosted environments.** Corrected run `30174711088` passed every step:
  Ubuntu in 2m36s and Windows in 2m50s. Both used 22 exact-disjoint probes and
  killed 27/27 validated mutants with zero survivors; mutation execution took
  90.316s on Ubuntu and 99.466s on Windows. The earlier symmetric
  missing-`anthropic` failure remains recorded in D59 rather than hidden. This
  completes the useful internal zero-credit work before outside adoption
  testing. → D58, D59.
- **2026-07-25 23:55 JDT** — **Independent mechanical-fault checkpoint added.**
  Added exact-disjoint probes and generic source mutation across all six paired
  domains. The initial honest score was 22/27 (81%): two email-anchor and three
  bottom-row mutants survived. Distinct scored examples closed those gaps;
  final local result is 27/27 killed (100%), with 22 independent probes and
  zero API spend. The paired result remains 12/12 decisions, 0 false
  accepts/rejects and 6/6 diagnostics. Integrated the perfect-score requirement
  into the unified checkpoint and clean-room workflow. Hosted reproduction is
  now complete. The first hosted attempt passed every earlier step on both OSes
  but exposed an eager optional-SDK import before mutation execution; the
  dependency was made lazy and verified with Anthropic imports forcibly blocked.
  → D58, D59.
- **2026-07-25 23:36 JDT** — **Paired logic-tool benchmark established.**
  Added six domains / twelve subjects with shared cases for each correct/broken
  pair: shipping and duration calculators, email validation, slug and CSV
  formatting, and tic-tac-toe rules. Local result: 12/12 decisions, 0 false
  accepts, 0 false rejects, 6/6 intended diagnostic labels, median 1.453s and
  p95 1.484s per subject. The versioned index is directory-confined and its
  escape regression passes. Integrated into the unified $0 checkpoint and
  clean-room workflow. Hosted run `30173955145` passed on both systems with the
  same 12/12, 0/0, 6/6 profile: Ubuntu median/p95 1.491s/2.069s and Windows
  1.569s/1.908s. → D57.
- **2026-07-25 23:27 JDT** — **v0.1.1 distribution hardening validated.**
  Added `turing-gate doctor` with human/JSON output and setup exit
  code `2`; healthy Windows checks pass 8/8 and a forced missing Chromium path
  fails with the repair command. Added a no-cache Windows/Linux hosted-runner
  workflow that builds the wheel, installs Chromium (plus Linux system deps),
  runs doctor, catches 3/3 demos, and accepts the shipping example. The exact
  wheel and full zero-credit regression pass locally; 20 Python dependencies
  audit clean. First hosted matrix run `30173582765` passed without retries:
  Ubuntu in 36s and Windows in 53s. The exact `v0.1.1` tag run also passed:
  Ubuntu in 38s and Windows in 54s; refreshed public HTTPS install resolved
  commit `1b06f3f` and passed doctor 8/8. → D56.
- **2026-07-25 23:16 JDT** — **Public v0.1 release published.** Published the
  Apache-2.0 repository and GitHub release, attached the validated wheel and
  sdist, and pinned the no-clone README flow to immutable tag `v0.1.0`.
  A refreshed public HTTPS `uvx` fetch resolved commit `0c04f61` and caught all
  3 demo defects. The only unproven release step is cold onboarding outside
  this workstation.
- **2026-07-25 23:11 JDT** — **Adoption-first v0.1 package completed.**
  Replaced the proprietary licence with exact Apache 2.0 terms + NOTICE. Added
  `pyproject.toml`, reproducible `uv.lock`, `turing-gate` entry point, strict
  version-1 JSON manifest, deep/tolerant result comparison, domain enforcement,
  directory confinement, local-only CLI telemetry, setup/reject/pass exit
  codes, and browser installation command. Bundled known-bad Wordle,
  calculator, and exfiltration demos; all 3 are caught. Added a passing
  shipping example/user-manifest control, escape-path rejection, and strict
  malformed-domain-schema rejection. The wheel contains only core, CLI, and
  demos; research runners are absent.
  `uv build --no-sources`, isolated-wheel `uvx` demo, full unified regression
  pass at $0, and Python dependency audit pass (20 packages; no known
  vulnerabilities or adverse statuses). → D55.
- **2026-07-25 22:39 JDT** — **Git ignore policy hardened.** Added the
  repository’s actual Python, Node, agent/tool, build, coverage, cache, browser,
  runtime, and Repomix outputs; generalized the response-cache rule; and removed
  the over-broad ZIP exclusion. `git check-ignore` confirms every protected
  class, intended manifests/configuration remain visible to Git, and diff
  hygiene passes. → D54.
- **2026-07-25 22:37 JDT** — **Repomix added and safety-validated.** Added a
  minimal private Node manifest, deterministic pnpm lockfile, Repomix 1.17.0,
  the `pnpm repomix` command, output gitignore, and `.repomixignore`. Installed
  with lifecycle scripts disabled. A real XML smoke pack contained 45 intended
  files (306,785 bytes): active source, package metadata, and `.env.example`
  were present; `.env`, `archive/`, `node_modules/`, caches, Q25 handoff,
  runtime queue, Q26 results, and lockfile were absent. Default secret scanning
  passed. Frozen reinstall passed; audit has 0 high/critical and one
  pack-workflow-inert moderate transitive advisory documented in D53.
- **2026-07-25 22:35 JDT** — **Second active-tree cleanup completed.**
  Audited every active Python import, top-level symbol, constant, file
  reference, generated artifact, and exact duplicate. No production functions
  or imports were dead. Removed three truly unreferenced constants (`TIERS` and
  two unused telemetry baselines), five regenerated `__pycache__` directories,
  and one stale `review-queue.html` export. Moved three completed/superseded
  planning documents from active `docs/` to `archive/plans/` and updated every
  reference. No exact duplicate files existed. Preserved replay caches, Q25
  handoff/queue, Q26 checkpoint, telemetry, and the research archive. Active +
  archive syntax, reference hygiene, diff hygiene, and the unified zero-credit
  checkpoint pass. → D52.
- **2026-07-25 22:30 JDT** — **Q25 ten-dossier human handoff prepared.**
  Fourteen new-vertical requests produced 10 exact-revision eligible packets;
  every packet passed all seven automated release checks and killed 5/5
  execution-validated mutants (50/50 aggregate). Two additional attempts were
  provisional domain mismatches, one produced no oracle, and one killed only
  4/5 mutants; they remain auditable but are excluded from the eligible sample.
  Added schema-derived disjoint probes, structured reviewer timing/finding
  fields, eligible-only queue views, `q25-handoff`, and `q25-report`. The local
  cache contains 140 unique responses with $2.241077 recorded cost. Actual
  provider spend may be slightly higher because three briefly overlapping
  orphan workers could duplicate concurrent cache misses before their process
  trees were stopped. The final unified zero-credit checkpoint passes. Human
  dispositions are still pending. → D51, Q25.
- **2026-07-25 21:51 JDT** — **Q26 controlled economics completed.** Added
  `q26_economics.py`: seven fixed canonical/prior-fighting tasks, paired
  cheap/strong samples, disjoint visible/hidden case sets, atomic checkpoints,
  replayable original response prices, and an exact paid-call cap. Added
  `offline_q26_check.py`: 7/7 correct controls accepted, 7/7 known-bad controls
  rejected, and a deliberately gate-overfit Roman control caught only by the
  holdout. Full zero-credit checkpoint PASS. Live 3-trial result: always-cheap
  18/21, always-Opus 21/21, cascade 21/21; 0 false accepts/rejects, 3/21
  escalations, 65.7% modeled savings. Total sampling spend $0.19651; strict
  cache-only replay reproduced the report at $0. → D50, Q26.
- **2026-07-25 21:38 JDT** — **Active-tree cleanup completed.** Reference and
  import audit separated production code from concluded research. Archived 29
  standalone experiment/diagnostic files and one-off fixtures under
  `archive/gate-experiments/` rather than deleting the evidence behind project
  claims. Removed unreachable prompt/wrapper/sandbox/config code and a stale
  import; corrected outdated oracle comments and all current docs/paths. Active
  gate now contains only the reusable core, three CLIs, four specs/scaffolds,
  controlled fixtures, and zero-credit regressions. `compileall` passes for
  active and archive trees; `offline_all_check.py` PASS in 23s, $0; diff
  hygiene clean. → D49.
- **2026-07-25 21:30 JDT** — **Deterministic pre-human productization
  completed.** Added `core/identity.py` + `core/lifecycle.py`: approvals bind to
  immutable review material and only an exact approved revision can release.
  Added `review_cli show/status` and `verify_cli --require-approved`. Approval
  refuses missing/failed seven-check evidence, provisional findings, top-tier
  failures, empty notes, stale/tampered/corrupt history, and mismatched
  revisions. `offline_lifecycle_check.py` covers every state/failure path.
  Added `offline_all_check.py`, which composes all deterministic regressions and
  controlled bad artifacts; final full run PASS in 31s, $0. Added the exact human
  protocol in `docs/human-testing.md`. Strict replay of the pre-Q21 Caesar cache
  correctly found a changed sharpening prompt and now exits cleanly as a
  skipped result (exit 1, no traceback/call/spend) instead of failing noisily.
  → D47, D48, Q25.
- **2026-07-25 21:22 JDT** — **Minimal human-review queue/UI completed.**
  Added `core/review.py` and `review_cli.py`: policy triggers open stable,
  deduplicated IDs; resolutions are append-only audit events; CLI supports
  list/resolve/export; HTML output escapes untrusted names/reasons. Moved the
  Playwright import into artifact execution so review-only commands run with
  plain `uv run python`. `offline_review_check.py` passes end-to-end, and Q21's
  regression now isolates its queue in a temp directory. → D45.
- **2026-07-25 21:22 JDT** — **Selective prompt-cache support completed without
  spending credits.** `core.llm.call(cache_system=True)` marks only an explicit
  stable system block; automatic caching remains off. Cost accounting now uses
  cache creation/read fields and correct 5m/1h multipliers; `cache_report()`
  exposes activity. `offline_q24_check.py` verifies request structure, billing,
  local response caching, independent samples, paid-call cap, and cache-only
  refusal with a fake client. Full offline regressions pass. → D46.
- **2026-07-25 21:13 JDT** — **Q21 answered: domain ambiguity cannot
  false-reject code.** Added `core/domain.py`, a small machine-checkable schema
  for function arguments (string/integer/number/boolean/array, bounds, regex,
  enum). `build_oracle_detailed()` filters draft cases before ensemble voting;
  withheld cases route through `policy.assess()` as `spec clarification
  required`, never as code failures. `offline_q21_check.py` reproduces the known
  Luhn ambiguity: `""` and `"0"` are outside the declared 2–19 digit domain,
  both withheld; four valid cases execute; correct implementation PASS; **0
  false rejects**, $0. Missing schemas also require clarification. → D44.
- **2026-07-25 21:10 JDT** — **Q24 answered: auto-generated battery mutation
  score 100% (5/5).** Replayed the checkpointed Caesar vertical in strict
  cache-only mode. A deterministic boundary grid expanded mutation witnesses to
  **498 independent in-domain inputs**. The cached model mutants yielded one
  real fault; standard local source-mutation operators supplied four more, all
  execution-validated before counting. The generated 14-case battery killed all
  five, 0 survivors. The one ensemble-disputed case (`"Shift-100 test", -100`)
  was resolved as `"Wlmjx-100 xiwx"` by an independent Python reference derived
  directly from the sharpened domain/spec, restoring 14/14 cases and zero
  unresolved. Final closure runs: **no API calls, $0 spend**. The one-time
  new-vertical human review required by D31 still applies before unattended use.
  → D43.
- **2026-07-25 21:03 JDT** — **Q24 live bounded run completed: partial
  evidence.** One checkpointed Caesar vertical ran to the persistent 25-response
  cap. Correct implementation PASS; 13/14 oracle cases agreed; one remained
  disputed after focused re-voting, so policy marked the verdict PROVISIONAL.
  Of four proposed mutants, execution discarded three as non-divergent and
  validated one on an independent input; the generated battery killed it:
  **1/1 (100%), 0 survivors**. This is valid but insufficient evidence, so Q24
  remains PARTIAL (D42). The final capped resume reported $0.0889 incremental
  spend; cumulative spend across interrupted attempts was not recorded. Local
  regression after the run: offline Q24 preflight PASS, known-good Wordle PASS,
  known-broken Wordle FAIL on logic as expected, compilation/diff checks PASS.
- **2026-07-25 20:53 JDT** — **Q24 made safe to resume without repeat spend.**
  Added exact-request response checkpointing, a persistent paid-response cap,
  and one-vertical selection. Added `offline_q24_check.py`: baseline gate PASS,
  independent mutants validated 3/3, mutation score 3/3, cache hit confirmed,
  cap refusal confirmed, **API spend $0**. The earlier live attempts exposed and
  locally fixed UTF-8 output, truncated large drafts, malformed-voter retry and
  mutant-witness issues; live scoring remains intentionally paused. → D41.
- **2026-07-25 20:33 JDT** — **Q24 harness implemented; live measurement
  blocked by API credit.** `auto_vertical.py --mutation-score` now generates a
  separate 40-case, in-domain probe pool, removes inputs present in the battery
  or unexecutable by the passing baseline, execution-validates up to five mutants
  against that disjoint pool, and scores the generated battery against them.
  Compilation, CLI, probe-independence and undefined-return mutation smokes pass.
  The live run reached its first Anthropic call and stopped with `credit balance
  is too low`; Q24 remains open. → D40.
- **2026-07-25 19:56 JDT** — **Q22 answered: mutation testing**
  (`gate/core/mutation.py`, `gate/mutation_check.py`). Mutants are proposed by
  the strong tier but accepted **only when execution demonstrates a divergence**
  — which is the fix for the unreliable buggy-control generator (it *predicted*
  differences instead of showing them). Result on the production batteries:
  **wordle 5/5, game2048 5/5, billsplit 5/5 — mutation score 100%, 0
  survivors**, cost $0.09. First evidence the gate catches faults nobody here
  thought of, rather than only the ones we injected.
  *Harness bug found and fixed en route (the third of its kind today): the
  mutation module hardcoded `window.__fn` while the production scaffolds expose
  `__wordle`/`__game2048`/`__tool`, so every call threw identically for original
  and mutant and all 30 candidates were silently discarded as "no divergence".
  `find_divergence` now aborts loudly when the original throws on every probe.*
  → D39.
- **2026-07-25 19:56 JDT** — **Q23 answered: dispute resolution**
  (`resolve_disputed` in `core/oracle.py`). Disputed cases now get a focused
  per-case second pass across the ensemble before exclusion; recovered cases
  rejoin the battery, so coverage is restored rather than merely made safe.
  Anything still disputed after focused voting is a spec gap and routes to human
  review via `policy.assess()`. → D38.
- **2026-07-25 19:45 JDT** — **Volume validation (Q5 answered)**
  (`gate/volume_check.py`). 10 generations × 3 verticals through the real
  pipeline: **wordle 10/10, game2048 10/10, billsplit 10/10** — pass@1 100%,
  Wilson 95% CI **[72%, 100%]** (n=10 cannot prove better than 72%; reported
  honestly rather than as "100% reliable"). Cost $0.037. Confirms the standing
  conclusion: behind a gate, the cheap tier clears these verticals, so
  escalation is insurance that rarely fires.
- **2026-07-25 19:45 JDT** — **`docs/gate-operations.md` implemented**
  (`core/telemetry.py`, `core/policy.py`). Every `verify()` is recorded to
  JSONL; `alarms()` fires on flag-rate excursions in *both* directions
  (>60% = spec fighting the models; <0.5% on a new vertical = ensemble probably
  lacks tier diversity) and on sustained low pass rate; `assess()` returns the
  §2 human-review triggers with a `provisional` flag. Smoke-tested. → D36, D37.
- **2026-07-25 19:45 JDT** — **Spec precision + ensemble oracle (Q22)**.
  Sharpening alone made things *worse* (it widened the domain to "any JavaScript
  value"); constraining it to a narrow domain AND recomputing expectations with
  a tier-diverse ensemble fixed it: **correct code accepted 1/3 → 3/3**. The
  ensemble automatically caught and corrected a real oracle error
  (`draft corrected on [123, 1]: '234' -> '123'` — the strong tier had
  miscomputed a Caesar shift), which is the validated design working unattended.
  Two harness bugs fixed en route: NaN never compares equal (false rejects), and
  the buggy-control generator still produces non-bugs in 2/3 cases (Q22 open).
  → D35.
- **2026-07-25 19:24 JDT** — **Auto-generated VERTICALS tested**
  (`gate/auto_vertical.py`). From a plain request the pipeline generates
  scaffold → oracle → implementation → buggy control, then gates it via
  `gate.core`. Result **1/3 fully working** (anagram checker: correct code
  accepted, injected bug caught, control confirmed genuine).
  The other two did **not** fail on scaffolding — all 3 scaffolds were
  structurally sound (slot + hook + floor pass) and all 3 oracles generated.
  They failed on **spec ambiguity**: the temperature converter's oracle wanted
  `None` for empty input while the impl returned `32` (false reject — the same
  `""` class as Q21); the Caesar cipher's "buggy" control did not actually
  differ from the correct code, so its result is inconclusive rather than a
  false accept. Cost $0.24. → D34.
- **2026-07-25 19:24 JDT** — **Sandboxed execution shipped** (`gate/core/sandbox.py`)
  — closes the standing security gap (generated JS had been running on the host
  via `file://`). Verified with `gate/fixtures/exfiltrate.html`, a benign-looking
  page that phones home four ways: **all 4 blocked** (fetch, image pixel,
  sendBeacon, XHR) and the artifact **failed** the gate on
  `no_outbound_requests`. Docker is not installed on this host, so isolation is
  built from browser-level controls; honest scope limits documented in the module.
- **2026-07-25 19:24 JDT** — **Research scripts consolidated into `gate.core`**
  — `config` / `llm` / `sandbox` / `checks` / `verify` plus a `verify_cli.py`
  entry point. Re-verified through the new module: `wordle_correct` PASS,
  `wordle_broken` FAIL on `wordle_logic` — correctness detection survives the
  refactor. Fixed a real bug found en route: `extract_code`'s optional language
  tag matched a *closing* fence and silently returned garbage (it broke all 3
  auto-verticals on the first run); replaced with strict `extract_block`. → D32.
- **2026-07-25 18:57 JDT** — **Q18 answered: gate operations spec**
  (`docs/gate-operations.md`). Codifies who watches the three known blind spots:
  human review at vertical *creation* + on anomaly; flag-rate monitoring as a
  spec-difficulty alarm; escalate-never-vote; top-tier failure ⇒ reject to human,
  never auto-accept; ambiguous-edge disagreements route to spec clarification
  rather than auto-fail. Every rule cites the measurement it came from. → D31.
- **2026-07-25 18:57 JDT** — **Q13b answered: the objective boundary for
  content/UI** (`gate/content_spec.py`, `gate/run_content_gate.py`, 8 landing-page
  fixtures). Defect ladder result: **objectively-checkable defects caught 5/5**
  (blank render, missing section, mobile overflow at 375px, WCAG contrast
  failure, element collision); **subjective defects passed 2/2** (garish but
  fully accessible design; contentless marketing copy); **false rejects 0/1**.
  Conclusion: for content/UI the gate is a **floor** (works / usable / complete),
  not a **quality bar** — the inverse of the tool & game verticals where the
  oracle decides correctness outright. → D30.
  *Two fixture/check artifacts were found and fixed mid-run: `required_sections`
  matched nav-link text rather than headings, and the "ugly but valid" fixture
  accidentally violated contrast (so it wasn't isolating pure taste).*
- **2026-07-25 18:53 JDT** — **Coverage-aware gating closes the false-accept gap**
  (`gate/coverage_gate.py`) — answers Q20. The strong tier now also declares the
  domain via `enumerateDomain()`; roman was correctly identified as enumerable
  (3999 cases) and checked exhaustively, catching `n===1847`.
  **L5 arbitrary-point: battery 0/3 → fuzz 2/3 → coverage-aware 3/3. Total false
  accepts 3/15 → 1/15 → 0/15.**
  Trade-off surfaced: **false rejects rose 0/3 → 1/3.** The luhn reference
  disagrees with the hand-verified correct impl on `""` — an input the spec never
  addresses, where both made different reasonable choices. (Caveat: luhn's L5 was
  therefore flagged at `""`, not at the injected `"77"` fault; the earlier fuzz
  run independently confirmed that fault *is* caught.) Broader coverage removes
  fatal false accepts but exposes spec-ambiguity false rejects → D28, Q21.
- **2026-07-25 18:41 JDT** — **Differential fuzzing built and measured**
  (`gate/fuzz_gate.py`) — answers Q19. Strong tier emits `referenceImpl` +
  `randomInput`; candidate is compared against the reference over 20,000 random
  inputs in-page. Versus the fixed battery on the identical ladder:
  **L5 arbitrary-point 2/3 caught (was 0/3); total false accepts 1/15 (was
  3/15); false rejects 0/3.** It caught the `"77"` substring and `length===9`
  faults. The single miss (`n===1847`) is a generator-distribution artifact —
  uniform sampling over 1..3999 should hit it ~5× in 20k — hence D27: enumerate
  exhaustively for small finite domains. Reference-generation cost $0.06.
  Note: no false rejects means the auto-generated references were correct.
- **2026-07-25 18:35 JDT** — **Bug-subtlety ladder / kill-check done properly**
  (`gate/subtlety_ladder.py`) — answers Q14 and the substance of Q2/Q3.
  3 tasks × 6 hand-verified implementations, gated by Opus-generated oracles.
  Catch rate: **L1 obvious 3/3, L2 systematic 3/3, L3 class-conditional 3/3,
  L4 canonical-edge (empty/singleton/max) 3/3, L5 arbitrary-point 0/3.**
  **False accepts 3/15, all at L5; false rejects 0/3.** The boundary is exactly
  canonical-vs-arbitrary: auto-oracles reliably probe boundaries, empty,
  singleton and max — where real bugs cluster — but a finite battery is blind to
  a fault placed at an arbitrary input (`n===1847`, substring `"77"`,
  `length===9`). Note the first pass (L1–L4 only) scored 0/12 false accepts and
  was misleading: those L4 bugs sat on canonical edges the oracle probes by
  habit. → D25 (differential/fuzz testing), D26 (not a security boundary).
- **2026-07-25 18:24 JDT** — **Q17 unanimity blind-spot test**
  (`gate/stress_unanimous.py`). Hardest test yet: maximum-prior-pull specs
  (swapped FizzBuzz; `sortDesc` that sorts *ascending*; zero treated as odd;
  `e` not a vowel; reverse-all-but-first), each deviation stated **plainly once**
  (no capitals/emphasis, unlike Q16) to maximise reversion. 32 inputs.
  Result: **0 unanimous-wrong again**; 34 wrong values, **all 34 flagged** by
  disagreement; a strong tier was correct on **32/32** inputs.
  Tier split is now stark: Haiku 53–75%, Sonnet 100%, Opus 100%.
  Cumulative across Q16+Q17: **83 inputs, 55 oracle errors, 0 unanimous-wrong,
  100% flagged.** Also observed: haiku#3 missed all 5 FizzBuzz cases while
  haiku#1/#2 passed (sampling variance gives some in-tier signal), yet all 3
  Haikus failed `sortDesc` together (correlated) — both effects are real. → D23, D24.
- **2026-07-25 18:18 JDT** — **Q16 adversarial consensus stress test**
  (`gate/stress_consensus.py`). 5 specs deliberately contradicting famous
  conventions (additive Roman `IIII`; Luhn doubling from the LEFT; MODIFIED
  competition ranking 1,3,3,4; leap years with no 100/400 exception; banker's
  rounding), 51 pinned inputs, same 5 oracles. Three findings:
  (1) **0 unanimous-wrong** — all 21 wrong values landed on inputs where oracles
  disagreed, so disagreement-flagging caught 100% (now on n=21 errors, far
  stronger than the earlier n=1);
  (2) **majority vote FAILED** — all three Haiku voters reverted to the canonical
  convention *together*, so the 5-oracle majority scored 45/51 while Opus alone
  scored 51/51. Correlated failure among same-model samples is real;
  (3) accuracy split cleanly by tier: Haiku 84–88%, Sonnet 100%, Opus 100% — the
  failures were exactly the "override the prior" cases (1994/3999 additive Roman,
  every ranking tie, 16-digit Luhn-left). Leap-year and banker's rounding: no
  errors from anyone. → D20, D21, D22.
- **2026-07-25 18:09 JDT** — **Q15 (detecting bad oracles without ground truth)
  — first cut** (`gate/oracle_consensus.py`). 5 independent oracles (3× Haiku,
  1× Sonnet, 1× Opus) computed expected values for 30 pinned inputs across the
  3 tasks; Python held real ground truth. Results: **only 1 wrong value out of
  150** — and it was **Opus** (called the valid Luhn number `4532015112830366`
  invalid; hand-verified sum 50). Every Haiku run was 30/30. Detection: the one
  error coincided with cross-oracle disagreement (1/1 flagged); **0
  unanimous-wrong** cases. Economics: 3× Haiku majority 30/30 @ $0.023 beat
  1× Opus 29/30 @ $0.045. Two conclusions: disagreement-flagging looks viable as
  a no-ground-truth defense, and **decomposing the oracle (pinned inputs →
  compute values) makes cheap models sufficient** — revising D18 into D19.
  CAVEAT: only 1 error occurred, so the 100% detection figure is near-meaningless
  statistically; and canonical tasks understate correlated-error risk.
- **2026-07-25 18:03 JDT** — **Auto-generated gates tested** (`gate/auto_gate.py`).
  Can the system produce its own oracle for an unanticipated request? 3 novel
  tasks (Luhn validation, tie-aware competition ranking, Roman numerals) ×
  2 oracle-generator models, each auto-gate run against hand-verified CORRECT and
  subtly-BUGGY implementations. Results: **false accepts 0/6** (every injected bug
  caught — missing Luhn −9, dense-vs-competition ranking, non-subtractive Roman);
  **wrong oracles 2/6, all from Haiku** (Opus 0/3): Haiku claimed
  `luhnValid("10")===true` and mis-ranked `[100,90,80,90,100,80]` — both verified
  wrong by hand. Cost $0.07. **First measured case where the strong model beats
  the cheap one → oracle generation is where you pay (D18).** Caveats: n=6,
  semi-canonical tasks, clear-cut injected bugs. Also fixed a harness artifact
  (minimal test scaffold failed the floor's `has_dom>=5`, initially mimicking
  "wrong oracles" 6/6).
- **2026-07-25 17:53 JDT** — Thin cascade wired ON TOP of the gate
  (`gate/run_cascade_calc.py`, `gate/scaffold/tool_calc_scaffold.html`,
  `gate/calc_spec.py`) on a harder slot (integer expr eval, div truncates toward
  zero). Over 6 trials: always-Haiku 6/6 $0.0211, always-Opus 6/6 $0.1106,
  **CASCADE 6/6 $0.0211 — 81% cheaper than always-Opus at equal gate-verified
  quality.** Escalation fired 0/6 (Haiku aced it — prompt over-specified the
  trap). Finding: the cascade's proven value is **"cheap-first behind the gate"**;
  the multi-tier escalation is rarely-fired insurance. The gate is what makes
  defaulting to cheap SAFE — that's the savings. (Original "boss routing between
  models" ≈ "one cheap model + a great verifier".)
- **2026-07-25 17:44 JDT** — Recipe extends to a NON-GAME tool (Q13a answered:
  yes). Bill splitter with tip + exact-cent rounding: `splitBill(subtotalCents,
  tipPercent, people)`. `gate/scaffold/tool_billsplit_scaffold.html`,
  `gate/billsplit_spec.py`, `gate/constrained_gen_billsplit.py`. Contract 5/5,
  logic 5/5, buggy control (drops remainder cents) correctly FAILED. Three
  verticals now (Wordle, 2048, bill-splitter) — the recipe is not games-specific;
  it fits any app whose critical logic is a checkable pure function.
- **2026-07-25 17:29 JDT** — Approach GENERALIZES to a 2nd vertical (2048).
  `gate/scaffold/game2048_scaffold.html`, `gate/game2048_spec.py`,
  `gate/constrained_gen2048.py` — different logic (array transform + merge-once,
  not string matching). Same pattern, no gate changes: contract **5/5**, logic
  **5/5**, buggy control (merge-until-stable) **correctly FAILED**. The
  scaffold+slot+oracle+gate recipe is repeatable, not Wordle-specific.
- **2026-07-25** — Constrained generation VALIDATED (`gate/constrained_gen.py`,
  `gate/scaffold/wordle_scaffold.html`). Model fills only `computeFeedback`;
  injected into a scaffold we own. Results: contract conformance **5/5** (vs 3/6
  free-form), logic correct **5/5**, and a known-buggy control **correctly
  FAILED** — so the gate still catches wrong logic. Also closes the earlier
  coverage-gap false-accept (scaffold guarantees a working, playable UI). This is
  a validated core loop for the Wordle vertical: gen logic → inject → gate.
- **2026-07-25** — Conformance repair attempt (`gate/repair_conformance.py`) —
  FAILED to lift conformance (3/6 → 3/6), $0.15 wasted. Root causes diagnosed:
  (a) cheap model ignored the "add hook" instruction in 2/3 repairs (no
  `__wordle` at all); (b) the 3rd regenerated the FULL HTML and **truncated** at
  the 8192-token cap → hook code present in source but script broken → runtime
  `window.__wordle` undefined. **The gate correctly rejected the runtime-broken
  build (gate is trustworthy — verified via `gate/probe_hook.py`).** Lesson:
  full-file regeneration is the wrong repair mechanism (truncation + cost); and
  voluntary contract conformance is unreliable at the cheap tier. (Also fixed a
  `str.format` brace bug in the repair prompt.)
- **2026-07-25** — Phase 2 kill check, first cut (`gate/kill_check.py`, N=6 real
  Haiku builds with the contract). Findings: **contract conformance 3/6** (half
  ignored the `window.__wordle` hook despite the prompt → false-reject driver,
  conflating "bad game" with "didn't follow protocol"); **coloring 3/3 correct
  among conformant** (cheap tier reliable when it conforms); **coverage-gap false
  accept CONFIRMED** — the sneaky `wordle_hook_only.html` (correct hook, dead UI)
  PASSes because the gate checks hook+floor, not that the game actually plays.
  Gate is not yet at "false-accept≈0 / tolerable false-reject" — work needed in
  both directions (conformance/repair + acceptance-criteria coverage + UI driving).
- **2026-07-25** — Gate Layer 1 (functional) built and PROVEN to see correctness:
  `gate/wordle_spec.py` drives the `window.__wordle` contract over a
  duplicate-letter battery vs a Python oracle. On controlled fixtures, correct
  Wordle PASSes and a logically-broken one FAILs on `wordle_logic` — even though
  BOTH pass the runtime floor. First demonstrated catch of a floor-level
  false-accept. Files: `gate/contract.md`, `gate/wordle_spec.py`,
  `gate/fixtures/wordle_{correct,broken}.html`, `gate/run_wordle_gate.py`.
- **2026-07-25** — Gate Layer 0 (runtime floor) skeleton built and running:
  `gate/browser_gate.py` (Playwright headless Chromium). Checks loads / no page
  errors / no console errors / has DOM / non-blank / interactive. Both real
  Wordle builds (`eval/artifacts/`) PASS the floor. Note: floor cannot see
  correctness (a pretty-but-broken game would also pass) — functional layer next.
- **2026-07-25** — Wrote gate-first implementation plan (now
  `archive/plans/implementation-plan.md`).
- **2026-07-25** — Ran full empirical investigation (~$2.70 total). Built eval
  harness and 8 experiment scripts under `eval/`. Key results captured in
  Findings below.
- **2026-07-25** — Critiqued original plan; wrote what is now
  `archive/plans/plan-revised.md`.
- **2026-07-25** — Established project direction through Q&A: cascade for "build
  me X", gate as backbone.

---

## Plans set

- **Implementation plan:** `archive/plans/implementation-plan.md` (gate-first, Phases 0–7,
  with a Phase-2 kill criterion).
- **Revised strategy critique:** `archive/plans/plan-revised.md`.
- **Original concept:** `archive/plans/plan.md` (superseded).

---

## Open questions

| # | Question | When needed | Status |
|---|----------|-------------|--------|
| Q26 | On a fixed varied workload with independent ground truth, does the current gated cascade reduce cost versus always-strong while preserving correct decisions? | Before making the current savings claim commercially | ANSWERED DIRECTIONALLY (2026-07-25 21:51 JDT): yes on 7 tasks × 3 paired trials. Always-cheap 18/21 correct at $0.03230; always-Opus 21/21 at $0.16421; cascade 21/21 at $0.05636 (65.7% savings). Gate: 39 true accepts, 3 true rejects, 0 false accepts/rejects; escalation 3/21. n=21 is not a production reliability bound. |
| Q25 | Does the revision-bound human workflow catch any spec/oracle/UI issue that passed all deterministic checks, and what are approval/clarification/rejection rates? | Before unattended auto-vertical use | PARKED/NON-BLOCKING (2026-07-25 23:05 JDT): 10 exact-revision eligible dossiers remain prepared, but the adoption v0.1 excludes auto-vertical generation and consumes user-authored deterministic cases. Resume Q25 only before exposing unattended auto-verticals. |
| Q1 | Which exact first vertical (specific app type + example requests)? | Now (Phase 0) | ANSWERED (2026-07-25): single-file browser games. |
| Q2 | Can the gate reach false-accept ≈ 0 with tolerable false-reject on that vertical? | Phase 2 — **kill check** | LARGELY ANSWERED (2026-07-25 18:35 JDT): yes for the realistic bug distribution — false-accepts 0/12 on obvious→canonical-edge bugs, false-rejects 0/3. Residual false-accepts only for arbitrary-point faults (3/3) → D25/Q19. |
| Q3 | What false-reject rate / cost budget is acceptable (the tuning target)? | Before Phase 2 tuning | OPEN |
| Q4 | Build vs no-build apps for the first gate (recommend no-build/single-file first)? | Phase 1 | ANSWERED (2026-07-25): no-build/single-file first (D13). |
| Q5 | Cheap tier's real pass@k per vertical (decides if the cascade pays). | — | ANSWERED (2026-07-25 19:45 JDT): 10/10 on each of wordle, game2048, billsplit via constrained generation — pass@1 100%, Wilson 95% CI [72%, 100%]. Escalation is rarely-fired insurance for these verticals. |
| Q6 | Can an LLM judge reliably score the *subjective* residual for real builds? | Phase 4 (fundamentally limited) | OPEN |
| Q7 | Does the API key have access to Sonnet 5 and Fable 5 (Fable needs 30-day retention)? | Before Phase 6 | PARTIAL (2026-07-25 20:02 JDT): **Sonnet 5 confirmed working** — used throughout the oracle ensemble, both stress tests and volume validation. **Fable 5 never attempted**; it is pricier and needs 30-day retention, and nothing so far has needed a tier above Opus. |
| Q18 | Human spot-check + flag-rate monitoring for the residual unanimous-wrong risk. | Before unsupervised production use | ANSWERED (2026-07-25 18:57 JDT): spec written — `docs/gate-operations.md` (D31). Residual risk itself remains irreducible; mitigated by one-time human review per new vertical. |
| Q17 | Does "unanimous ⇒ correct" hold when even the STRONG models revert? | Before auto-gates go live unsupervised | ANSWERED (2026-07-25 18:24 JDT): unanimity did NOT break — 0 unanimous-wrong across 32 hardest-yet inputs (83 cumulative), all 34 errors flagged, strong tier 100%. Safety rests on the strong tier being reliable (D23) → residual risk moved to Q18. |
| Q16 | Correlated (unanimous-wrong) oracle failure — the residual fatal risk. | Before auto-gates go live | LARGELY ANSWERED (2026-07-25 18:18 JDT): adversarial specs produced 21 errors, **0 unanimous-wrong**; disagreement flagged 100%. BUT correlated failure IS real *within* a tier (3× Haiku wrong together) → don't vote, escalate (D21); diversify tiers (D22). Residual risk → Q17. |
| Q15 | A wrong oracle is INVISIBLE in production (looks identical to bad code). Detect it without a hand-verified reference? | Before auto-generated gates go live | PARTIAL (2026-07-25 18:09 JDT): cross-oracle disagreement flagged the only error (1/1), 0 unanimous-wrong, and a 3× cheap ensemble beat 1× Opus on both accuracy and cost. But only 1 error occurred → weak evidence; see Q16. |
| Q24 | Mutation score is measured on HAND-WRITTEN batteries. Auto-generated batteries (the ones that would serve unanticipated requests) are still unscored — run `mutation_check` against an auto-vertical's battery to close the loop. | Before auto-verticals run unattended | ANSWERED (2026-07-25 21:10 JDT): Caesar auto-battery killed 5/5 execution-validated mutants over 498 independent probes, 0 survivors. Hybrid: 1 cached model mutant + 4 standard mechanical mutants. Independent Python reference resolved the sole disputed oracle input, restoring 14/14 cases and zero unresolved. Closure runs were strict cache-only, $0 (D43). |
| Q23 | Disputed cases were excluded, losing coverage. | — | ANSWERED (2026-07-25 19:56 JDT): `resolve_disputed()` re-votes per pinned case; recovered cases rejoin the battery, unresolved ones route to human review (D38). |
| Q22 | Auto-verticals need spec precision + a real buggy-control generator. | — | ANSWERED (2026-07-25 19:56 JDT): precision via narrow-domain sharpening + ensemble oracle (accept 1/3 → 3/3, D35); controls via execution-validated mutants — production batteries score 100% (15/15), D39. |
| Q21 | Spec-ambiguity false rejects: broad coverage hits inputs the spec never addresses (e.g. `""` for a card number), where the reference's arbitrary choice becomes "truth" and correct code fails. Handle by constraining the declared domain to spec-defined inputs, and/or routing ambiguous-edge disagreements to spec clarification instead of auto-failing. | Before productizing the gate | ANSWERED (2026-07-25 21:13 JDT): mandatory machine-readable argument schema filters cases before voting/execution; outside-domain cases and missing schemas route to spec clarification, never code failure. Offline Luhn regression withheld 2/2 undefined inputs, correct implementation PASS, 0 false rejects (D44). |
| Q20 | Generator coverage bottleneck; should enumeration be automatic when the domain is enumerable? | — | ANSWERED (2026-07-25 18:53 JDT): yes — declare the domain, enumerate ≤100k exhaustively, fuzz otherwise. False accepts 0/15 (D28). Cost: more spec-ambiguity false rejects → Q21. |
| Q19 | Does differential fuzzing close the L5 gap? | — | ANSWERED (2026-07-25 18:41 JDT): largely — L5 2/3 (was 0/3), false accepts 1/15 (was 3/15), false rejects 0/3. Residual miss is a generator-distribution artifact → D27, Q20. |
| Q14 | Does the auto-gate hold on subtler bugs? | — | ANSWERED (2026-07-25 18:35 JDT): yes up to canonical-edge bugs (12/12 caught), no for arbitrary-point bugs (0/3 caught). False accepts 3/15, false rejects 0/3. → D25, D26. |
| Q13 | Generalization boundary beyond web games. (a) non-game logic-tools; (b) content/UI-heavy apps like IGN. Strategic implication: gate is strongest for logic-verifiable categories; lead there, defer content sites. | Before committing to "build me any site" scope | FULLY ANSWERED. (a) 2026-07-25 17:44 JDT: YES — bill-splitter tool works (5/5, buggy caught). (b) 2026-07-25 18:57 JDT: **floor-only** — objective defects caught 5/5, subjective passed 2/2 → the gate guarantees working/accessible/complete, not *good* (D30). |
| Q12 | How to GUARANTEE conformance, given voluntary contracts fail at the cheap tier? | — | ANSWERED (2026-07-25): option (a) constrained generation — validated (D16). |
| Q11 | Contract conformance ~50% with free-form gen; full-regen repair failed. | — | ANSWERED (2026-07-25): solved by constrained generation (D16), not repair. |
| Q10 | Hook-vs-UI divergence + coverage gap (sneaky dead-game passed). | Gate coverage | MOSTLY CLOSED (2026-07-25): constrained scaffold owns the working UI, so a dead-game-with-correct-hook can't occur for scaffolded builds. Revisit if generation freedom expands beyond the scaffold. |
| Q9 | Impose a generation *contract* (fixed testable interface / DOM `data-testid`s) so functional gating generalizes across implementations? | Gate Layer 1 (functional) | ANSWERED (2026-07-25): yes — `window.__wordle` contract (D15). |
| Q8 | Was the VSM cascade failure variance or gate design? | — | ANSWERED (2026-07-25): variance. pass@k = Haiku 50%, Opus 67%. |

---

## Empirical findings (dry runs, 2026-07-25, ~$2.70 total)

- **Self-contained coding (23 tasks, easy→contest→a self-modifying VM):** cheap
  model (Haiku) passed effectively all; escalation never fired; Opus added cost,
  not quality. Well-specified coding does not need a cascade.
- **Mental algorithm execution (UPMH-64):** both models hallucinated; escalation
  doubled cost for the same wrong answer; the real lever is **tool use / code
  execution** (a Python oracle solved it instantly).
- **Open-ended engineering ("overhaul"):** no deterministic oracle; both failed a
  completeness floor (Haiku truncated, Opus shipped 2 syntax-broken blocks at
  4.5× cost). This is the **scoring wall** — correctness needs a judge.
- **Judge reliability:** judges were position-invariant; on a controlled
  correct-vs-buggy pair, Opus judge 6/6, Haiku judge 5/6 (never chose buggy). A
  judge *can* be a correctness gate — but consistency ≠ correctness, and a judge
  is only validatable where ground truth exists.
- **Cascade + reliability:** tasks are probabilistic. On the VSM task, pass@k =
  Haiku 50% / Opus 67%. In that partial-pass band, cascade Haiku→Opus ≈ **84%
  success at ~$0.053/task vs always-Opus 67% at $0.077** — wins on cost AND
  quality *because a reliable gate turns cheap failures into a free retry*.
  Over-escalation on hopeless tasks can cost MORE than always-strong (measured
  $0.36 vs $0.27) → need an escalation cap.

---

## Artifact / file index

*(layout as of 2026-07-25 23:36 JDT)*

**`docs/`**
- `PROJECT-LOG.md` — this file; the single record.
- `gate-operations.md` — human review, monitoring, failure handling and API
  cost controls (implemented in `core/telemetry.py`, `policy.py`, `review.py`,
  and `llm.py`).
- `human-testing.md` — preconditions, evidence questions, decision semantics,
  release proof, and first 10-candidate validation protocol.

**`gate/core/`** — *the module.* Start here.
- `doctor.py` — zero-API setup diagnostics for local state, loopback,
  Playwright, Chromium and a real browser launch.
- `starter.py` — validated, atomic v1 manifest creation without inferred
  correctness claims.
- `manifest.py` — versioned user manifest, path/domain validation, hook
  execution, and deep expected-value comparison.
- `verify.py` — the entry point: `verify(artifact, functional=...) -> Verdict`.
- `sandbox.py` — isolated execution (ephemeral loopback origin, all outbound
  requests blocked, fresh context, timeouts).
- `checks.py` — the runtime floor.
- `oracle.py` — draft battery → ensemble-verify on pinned inputs → resolve
  disputes per case → unresolved go to review.
- `domain.py` — machine-readable argument contracts; outside-domain cases route
  to clarification before they can affect a verdict.
- `mutation.py` — execution-validated model/mechanical mutants + scoring.
- `telemetry.py` / `policy.py` — JSONL record + alarms; human-review triggers
  return stable queue IDs.
- `review.py` — append-only deduplicated review queue, audited resolutions, and
  escaped HTML rendering.
- `identity.py` / `lifecycle.py` — canonical revision digest and fail-closed
  production eligibility for exact reviewed revisions.
- `config.py` — key loading, tiers, pricing, limits, `Verdict`.
- `llm.py` — model calls, cache-aware cost accounting, local response
  checkpoints, optional stable-system prompt caching, paid-call cap, strict
  cache-only mode, replayable original response prices, fenced-block extraction.

**`gate/`** — current verticals, CLIs, and regressions only.
- `cli.py` — packaged no-API
  `turing-gate` init/verify/demo/doctor/install-browser command.
- `demos/` — bundled Wordle, calculator, and exfiltration demonstrations.
- Per vertical: a scaffold in `scaffold/` + a `*_spec.py` (`wordle`, `game2048`,
  `billsplit`, `calc`).
- `verify_cli.py` — gate artifacts; optional exact-revision release guard.
- `review_cli.py` — list/show/resolve/status/export human review; eligible-only
  Q25 handoff generation and aggregate reporting.
- `auto_vertical.py` — current request → scaffold/spec/oracle/implementation/
  mutation evidence/revision-bound review packet; `--q25-mode` uses
  deterministic disjoint schema probes and a strict paid-call cap.
- `q26_economics.py` — checkpointed paired three-arm cost/correctness benchmark.
- `offline_all_check.py` — unified zero-credit pre-human checkpoint; the
  narrower `offline_q21_check.py`, `offline_q24_check.py`,
  `offline_q25_check.py`, `offline_q26_check.py`,
  `offline_benchmark_check.py`, `offline_benchmark_mutation_check.py`,
  `offline_manifest_check.py`,
  `offline_review_check.py`, and
  `offline_lifecycle_check.py` compose into it.
- `q25-handoff/` — generated eligible-only reviewer UIs and immutable dossiers;
  local runtime output, gitignored.
- `fixtures/` — correct/broken Wordles and the four-vector exfiltration probe.
- `telemetry.jsonl`, `review-queue.jsonl`, `review-queue.html` — local runtime
  records/views; gitignored.

**`archive/`** — concluded evidence trail; see `archive/README.md`.
`archive/eval/` (exploration), `archive/gate-experiments/` (successful gate
research/predecessors), `archive/gate-deadends/` (failed approaches), and
`archive/plans/` (completed/superseded planning documents).

**`.github/workflows/`** — `clean-room.yml` builds and exercises the wheel on
fresh Windows and Linux hosted runners, then runs the paired and independently
validated mechanical-fault benchmarks; setup and regression proxy, not adoption
evidence.

**`benchmarks/`** — versioned `logic-tools-v1` paired corpus, exact-disjoint
`mutation-probes-v1`, per-domain artifacts/manifests, schema/extension
instructions, and interpretation limits.

**Root** — `README.md`, Apache-2.0 `LICENSE` + `NOTICE`, `.gitignore`,
`.env.example`, `.repomixignore`, `pyproject.toml`, `uv.lock`, `package.json`,
and `pnpm-lock.yaml`.
`.env` holds `CLAUDE_API_KEY` and is gitignored — never commit it.

**Public path:** `uv run turing-gate install-browser`, confirm with
`uv run turing-gate doctor`, then
`uv run turing-gate demo` or `uv run turing-gate verify turing.json`.
**Full research regression:** `uv run --extra ai python gate/offline_all_check.py`.
Repository snapshots use `pnpm install --frozen-lockfile --ignore-scripts`
followed by `pnpm repomix`; the generated XML is gitignored.

> Cleanup 2026-07-25 22:35 JDT: archived three concluded plans; removed three
> dead constants, five bytecode caches, and one stale generated HTML export.
> Replay, review, telemetry, and empirical evidence remain intact. → D52.
>
> Cleanup 2026-07-25 21:38 JDT: archived 29 concluded gate experiment,
> diagnostic, document, and fixture files; removed unreachable active code.
> No empirical evidence was discarded. → D49.
>
> Cleanup 2026-07-25 18:45 JDT: deleted 42 `__pycache__` artifacts and 29
> generated HTML outputs (`gate/corpus/`, `eval/artifacts/` — regenerable);
> archived the exploration phase and two dead-end approaches. No project is under
> git, so nothing else was deleted.
