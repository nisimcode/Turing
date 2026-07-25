# Turing Gate

[![Clean-room package](https://github.com/nisimcode/Turing/actions/workflows/clean-room.yml/badge.svg)](https://github.com/nisimcode/Turing/actions/workflows/clean-room.yml)

> **AI agents:** Before analyzing, planning, or changing this repository, read
> [`docs/PROJECT-LOG.md`](docs/PROJECT-LOG.md) in full. It is the source of truth
> for current status, decisions, completed work, open questions, and the exact
> resume point. Update it after completing work; do not rely on chat history.

Turing Gate is a local, fail-closed verifier for AI-generated,
self-contained HTML/JavaScript tools. Give it an artifact plus deterministic
examples of the critical function’s behavior. It loads the artifact in an
isolated browser, blocks outbound requests, checks the runtime floor, invokes
the browser hook, and rejects any mismatch.

The dependable verifier requires no model, API key, account, or hosted service.
Experimental model-assisted oracle and auto-vertical research remains in this
repository, but it is not part of the installed public CLI.

## Try it in under five minutes

Requirements: Python 3.12+ and
[`uv`](https://docs.astral.sh/uv/getting-started/installation/).

From a clone:

```bash
uv run turing-gate install-browser
uv run turing-gate doctor
uv run turing-gate demo
```

On Linux, if `doctor` reports missing browser system libraries, run
`uv run turing-gate install-browser --with-deps`.

The bundled demonstration runs three plausible failures:

- Wordle code that mishandles repeated letters.
- A calculator that floors negative division instead of truncating toward zero.
- A harmless-looking notes widget that attempts four outbound requests.

All three artifacts should be rejected, and the demo command succeeds only when
the intended defect is caught.

Run the tagged release without cloning:

```bash
uvx --from git+https://github.com/nisimcode/Turing@v0.1.1 turing-gate install-browser
uvx --from git+https://github.com/nisimcode/Turing@v0.1.1 turing-gate doctor
uvx --from git+https://github.com/nisimcode/Turing@v0.1.1 turing-gate demo
```

## Verify your own artifact

The artifact must be self-contained HTML/JavaScript. Expose the critical
function through a browser hook:

```html
<script>
  function calculateShipping(total) {
    return total >= 100 ? 0 : 8;
  }
  window.__turing = { calculateShipping };
</script>
```

Place a `turing.json` next to the HTML:

```json
{
  "schema_version": 1,
  "name": "shipping-calculator",
  "artifact": "shipping.html",
  "hook": "window.__turing.calculateShipping",
  "domain_schema": {
    "args": [
      {"type": "number", "minimum": 0}
    ]
  },
  "cases": [
    {"label": "below threshold", "args": [99], "expected": 8},
    {"label": "at threshold", "args": [100], "expected": 0},
    {"label": "above threshold", "args": [250], "expected": 0}
  ]
}
```

Then run:

```bash
uv run turing-gate verify turing.json
```

The repository includes this exact passing example:

```bash
uv run turing-gate verify examples/shipping/turing.json
```

Use `--json` for machine-readable results. Exit codes are:

- `0`: every runtime and functional check passed.
- `1`: the artifact was successfully checked and rejected.
- `2`: configuration or local browser setup is incomplete, including a
  not-ready `doctor` result.

The manifest is deliberately narrow:

- `schema_version` must be `1`.
- `artifact` must be an HTML file inside the manifest directory.
- `hook` is a dotted browser function such as `window.__tool.evaluate`.
- Every functional case supplies JSON-compatible `args` and `expected`.
- `domain_schema` is optional but recommended; it prevents undefined inputs
  from becoming false failures.
- `number_tolerance` optionally permits an absolute floating-point tolerance.

A manifest without `hook` and `cases` runs only the runtime and containment
floor. The CLI warns that this does not establish functional correctness.

## What the gate checks

Every artifact is copied into a temporary directory and served from an
ephemeral loopback origin in a fresh Playwright browser context.

The runtime floor checks:

- Page load and JavaScript/console errors.
- Non-trivial DOM and visible content.
- At least one interactive affordance.
- Any attempted request outside the temporary artifact origin.

The functional layer checks:

- The declared hook exists and is callable.
- Every case returns the expected JSON value.
- Nested arrays and objects compare deeply.
- Numeric comparisons respect the optional absolute tolerance.
- Inputs comply with the declared machine-readable domain.

The manifest and artifact paths are validated before the browser starts; a
manifest cannot escape its own directory.

## Honest scope

Turing Gate is strongest where important behavior is an objectively testable
pure function: calculators, validators, game rules, formatters, and similar
small tools.

It does **not** guarantee:

- Subjective UI or copy quality.
- Correct behavior that was never represented by a test, property, or oracle.
- Safety against deliberately hidden behavior or a browser-engine escape.
- Isolation for build scripts, servers, native dependencies, or arbitrary
  repositories. Those require a container and a wider threat model.

The blocked-request check demonstrates browser containment; it is not a claim
that Turing is a universal security scanner.

## Stable product path versus research

The built wheel contains only:

- `gate/cli.py` — the `turing-gate` command.
- `gate/core/` — deterministic verification, manifest, sandbox, and supporting
  lifecycle modules.
- `gate/demos/` — the three known-bad public demonstrations.

It excludes auto-vertical generation, paid experiment runners, historical
fixtures, and research scripts. Those remain in the source repository as
evidence and future experimental work.

The public verifier writes a local audit trail to
`.turing/telemetry.jsonl` in the current project. Nothing is transmitted.

## Development

Install the project and optional model-assisted research dependency:

```bash
uv sync --extra ai
```

Run every deterministic regression, including the public manifest, the three
demos, Q21–Q26 controls, correct/broken Wordle, and exfiltration:

```bash
uv run --extra ai python gate/offline_all_check.py
uv audit
```

These checks make no API requests. The release candidate currently audits with
no known Python dependency vulnerabilities.

Build and validate the distributable package:

```bash
uv build --no-sources
uvx --from dist/turing_gate-0.1.1-py3-none-any.whl turing-gate doctor
uvx --from dist/turing_gate-0.1.1-py3-none-any.whl turing-gate demo
```

The `Clean-room package` GitHub Actions workflow repeats the wheel-based flow on
fresh Windows and Linux runners: install Chromium, run `doctor`, catch all three
bundled defects, and accept the shipping example. This is a reproducible setup
proxy, not evidence that an outside developer wants or understands the tool.

Create a repository context snapshot:

```bash
pnpm install --frozen-lockfile --ignore-scripts
pnpm repomix
```

`.repomixignore` keeps secrets, generated state, archived research, and local
review data out of the bundle.

## Why this exists

The project began as research into cheap-first model routing. The measured
conclusion was that the valuable component is the verifier, not the router:
defaulting to a cheaper model is safe only when acceptance is based on reliable
evidence.

On the fixed Q26 workload, the gated cascade matched always-strong correctness
(21/21), recorded zero false accepts/rejects, escalated 3/21 tasks, and reduced
modeled model cost by 65.7%. That sample is directional evidence, not a
production reliability bound—and the absolute savings were small. The current
goal is therefore adoption: determine whether outside developers repeatedly use
the verifier on their own generated code.

The 30-day validation target is:

- 20 outside developers complete a verification.
- At least 5 verify their own artifact.
- At least 3 return and verify another artifact.

## Repository layout

| Path | Purpose |
|---|---|
| `gate/cli.py` | Public `turing-gate` CLI |
| `gate/core/manifest.py` | Versioned user manifest validation and execution |
| `gate/core/verify.py` | Runtime + functional verification entry point |
| `gate/core/sandbox.py` | Temporary-origin, outbound-blocking browser context |
| `gate/demos/` | Wordle, calculator, and exfiltration demonstrations |
| `examples/shipping/` | Minimal passing artifact + manifest to copy |
| `gate/offline_manifest_check.py` | Zero-credit public-path regression |
| `gate/offline_all_check.py` | Unified zero-credit regression checkpoint |
| `gate/auto_vertical.py` | Experimental model-assisted vertical generation |
| `docs/PROJECT-LOG.md` | Decisions, evidence, current status, and resume point |
| `docs/gate-operations.md` | Operational safeguards and failure handling |
| `archive/` | Concluded plans, experiments, dead ends, and evidence |
| `pyproject.toml`, `uv.lock` | Python package and reproducible dependency lock |
| `.repomixignore` | Safe active-code repository snapshot exclusions |

## Licence

Copyright 2026 Nisim Levi.

Licensed under the [Apache License 2.0](LICENSE).
