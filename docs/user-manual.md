# Turing Gate user manual

This manual covers Turing Gate v0.2.0, a local verifier for generated,
self-contained HTML/JavaScript tools.

Turing Gate answers a narrow question:

> Does this artifact load safely enough for inspection and does its critical
> function return the expected result for every case I declared?

It does not generate applications, invent expected behavior, or judge visual
quality. It requires no model, API key, account, or hosted service.

## Contents

1. [How the gate works](#how-the-gate-works)
2. [Installation](#installation)
3. [Native desktop GUI](#native-desktop-gui)
4. [Five-minute first run](#five-minute-first-run)
5. [Verify your own artifact](#verify-your-own-artifact)
6. [Create a manifest with `init`](#create-a-manifest-with-init)
7. [Manifest reference](#manifest-reference)
8. [Writing effective cases](#writing-effective-cases)
9. [Understanding results](#understanding-results)
10. [Automation and CI](#automation-and-ci)
11. [Troubleshooting](#troubleshooting)
12. [Privacy, security, and limits](#privacy-security-and-limits)
13. [Command reference](#command-reference)

## How the gate works

Turing Gate uses three inputs:

- A self-contained HTML/JavaScript artifact.
- A browser-visible function such as `window.__tool.calculate`.
- Explicit argument and expected-result cases in `turing.json`.

For every verification, it:

1. Validates the manifest and confines the artifact path to its directory.
2. Copies the artifact into a temporary directory.
3. Serves it from an ephemeral loopback address.
4. Starts a fresh Playwright Chromium context.
5. Blocks and reports outbound requests.
6. Checks the runtime and visible-page floor.
7. Resolves the declared browser hook.
8. Invokes the hook with every case and compares the result.
9. Returns a pass, rejection, or setup/configuration exit code.

The gate is fail-closed: a missing hook, thrown exception, wrong result, page
error, or attempted external request cannot produce an acceptance.

## Installation

### Requirements

- Python 3.12 or newer.
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/).
- Chromium installed through the command below.

### From a repository clone

To install the native GUI as a command you can use from any folder:

```bash
git clone https://github.com/nisimcode/Turing.git
cd Turing
uv tool install ".[gui]"
turing-gate install-browser
turing-gate doctor
```

On Linux, install Chromium and its operating-system libraries together:

```bash
turing-gate install-browser --with-deps
```

On Debian or Ubuntu, install the native Qt runtime libraries as well:

```bash
sudo apt-get install libegl1 libxcb-cursor0 libxkbcommon-x11-0
```

The core CLI does not require PySide6. For source development without the GUI,
use `uv run turing-gate COMMAND` from the clone.

### Use the tagged release without cloning

```bash
uv tool install "turing-gate[gui] @ git+https://github.com/nisimcode/Turing@v0.2.0"
turing-gate install-browser
turing-gate doctor
```

Use `--with-deps` on the `install-browser` command when required on Linux.
For one-off CLI use without installing the GUI:

```bash
uvx --from git+https://github.com/nisimcode/Turing@v0.2.0 turing-gate doctor
```

### Confirm the installed version

```bash
turing-gate --version
```

Expected output:

```text
0.2.0
```

## Native desktop GUI

Start the installed interface from the folder containing your project:

```bash
turing-gate ui
```

Or give it the project folder explicitly:

```bash
turing-gate ui path/to/project
```

The interface is one owner workflow:

1. Choose a project folder.
2. Select a discovered `.html` or `.htm` artifact.
3. Enter a name, optional description, and dotted browser hook.
4. Optionally enter the argument-domain schema and numeric tolerance.
5. Add ordinary and boundary cases. Arguments must be a JSON array; the
   expected result may be any JSON value.
6. Select **Save and verify**.
7. Accept only an `ACCEPTED` result with every listed check passing.

The GUI creates `turing.json` beside the selected artifact. If a valid sibling
manifest already points to that artifact, the GUI loads it. Replacing an
existing manifest requires confirmation.

**Check page only** runs loading, visible-page, interaction, error, and
containment checks without saving a functional contract. A pass there does not
mean the calculations, validators, formatters, or game rules are correct.

The GUI never invents a hook or expected value and never calls a model API. It
runs the same manifest loader and Chromium verifier as the CLI, in a background
worker so the window remains responsive. Hidden directories and common
generated trees such as `.git`, `.venv`, `node_modules`, `build`, and `dist`
are skipped during artifact discovery.

To diagnose only the optional dependency and folder scan without opening a
window:

```bash
turing-gate ui --check .
```

Automation should continue to use `turing-gate verify ... --json`; the GUI is
an owner convenience layer, not a second verification engine.

## Five-minute first run

Run the environment diagnosis:

```bash
uv run turing-gate doctor
```

`READY: verification can run.` means Python, local state, loopback networking,
Playwright, Chromium, and a real browser launch all succeeded.

Then run the bundled demonstrations:

```bash
uv run turing-gate demo
```

The demonstration contains three deliberately defective artifacts:

- Wordle logic that mishandles repeated letters.
- Calculator logic that rounds negative division incorrectly.
- A notes widget that attempts four outbound requests.

The command succeeds only when all three defects are rejected. This proves the
gate is running; it does not test your own artifact.

To run one demonstration:

```bash
uv run turing-gate demo wordle
uv run turing-gate demo calculator
uv run turing-gate demo exfiltration
```

The repository also includes a passing shipping calculator:

```bash
uv run turing-gate verify examples/shipping/turing.json
```

## Verify your own artifact

### 1. Keep the artifact self-contained

The supported public path is one self-contained HTML file with inline
JavaScript and CSS. Companion files are not copied into the sandbox. External
scripts, fonts, images, APIs, analytics, and other remote requests are blocked.

The page should have meaningful visible content and at least one interactive
affordance such as a button, input, select, textarea, or link.

### 2. Expose the critical function

Suppose the application contains this logic:

```html
<script>
  function calculateShipping(total) {
    return total >= 100 ? 0 : 8;
  }

  window.__turing = { calculateShipping };
</script>
```

The browser hook is:

```text
window.__turing.calculateShipping
```

Hooks must be dotted browser identifiers. Bracket expressions and arbitrary
JavaScript are not accepted. Synchronous and asynchronous functions are
supported.

### 3. Declare expected behavior

Create `turing.json` beside the HTML file:

```json
{
  "schema_version": 1,
  "name": "shipping-calculator",
  "description": "Shipping is free at or above $100.",
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

### 4. Run verification

```bash
uv run turing-gate verify turing.json
```

Accept the artifact only when the command exits `0` and every check passes.

For machine-readable output:

```bash
uv run turing-gate verify turing.json --json
```

## Create a manifest with `init`

`init` removes outer JSON boilerplate but never guesses the expected behavior.

### Functional starter

This Bash command creates a complete functional manifest:

```bash
uv run turing-gate init shipping.html \
  --hook window.__turing.calculateShipping \
  --domain-schema '{"args":[{"type":"number","minimum":0}]}' \
  --case '{"label":"below threshold","args":[99],"expected":8}' \
  --case '{"label":"at threshold","args":[100],"expected":0}' \
  --case '{"label":"above threshold","args":[250],"expected":0}'
```

Each `--case` value is one JSON object. Repeat the option for additional cases.
The default output is `turing.json` beside the artifact.

The PowerShell equivalent uses backticks for line continuation:

```powershell
uv run turing-gate init shipping.html `
  --hook window.__turing.calculateShipping `
  --domain-schema '{"args":[{"type":"number","minimum":0}]}' `
  --case '{"label":"below threshold","args":[99],"expected":8}' `
  --case '{"label":"at threshold","args":[100],"expected":0}' `
  --case '{"label":"above threshold","args":[250],"expected":0}'
```

Windows Command Prompt has different quoting rules; use PowerShell or edit the
generated JSON file directly.

Optional initialization arguments:

```text
--output PATH
--name NAME
--description TEXT
--number-tolerance NUMBER
--force
--json
```

`init` validates the finished manifest through the production manifest loader
before publishing it. It refuses:

- A missing or non-HTML artifact.
- An artifact outside the output manifest directory.
- Cases or a domain schema without a hook.
- A hook without at least one case.
- Malformed JSON or unsupported schema fields.
- Non-finite JSON numbers such as `NaN` and `Infinity`.
- Accidental overwrite of an existing output.

Use `--force` only when replacing the output is intentional.

### Runtime-only starter

This command creates a minimal manifest:

```bash
uv run turing-gate init tool.html
```

It checks page execution, visible structure, interaction, and containment, but
not functional correctness. The command and later verification both identify
this limitation.

Runtime-only verification is useful for diagnosing an artifact before its
functional contract exists. It is not sufficient evidence that the tool works
correctly.

## Manifest reference

Turing Gate supports manifest schema version `1`.

### `schema_version`

Required. Must be:

```json
"schema_version": 1
```

### `name`

Required non-empty string used in reports.

```json
"name": "shipping-calculator"
```

### `description`

Optional human-readable string displayed before a normal verification report.

### `artifact`

Required relative path to an `.html` or `.htm` file.

```json
"artifact": "shipping.html"
```

Absolute paths and `..` paths that escape the manifest directory are rejected.
Symlinks cannot be used to escape this confinement.

### `hook`

Required for functional verification. It identifies the browser function:

```json
"hook": "window.__turing.calculateShipping"
```

`globalThis.__turing.calculateShipping` is also valid. A missing hook produces
a `manifest_contract` rejection.

### `cases`

Required and non-empty when `hook` is present. At most 1,000 cases are allowed.

```json
{
  "label": "at threshold",
  "args": [100],
  "expected": 0
}
```

- `label` is optional but strongly recommended.
- `args` must be a JSON array containing the positional function arguments.
- `expected` must be a JSON-compatible value.
- Returned arrays and objects are compared recursively.
- Object keys and values must match.
- Types matter: `1`, `"1"`, and `true` are different values.

### `domain_schema`

Optional but recommended. It prevents undefined or unsupported inputs from
silently becoming test cases.

This is a deliberately small schema subset, not general JSON Schema:

```json
{
  "args": [
    {"type": "number", "minimum": 0},
    {"type": "string", "minLength": 1, "maxLength": 50}
  ]
}
```

Supported types:

- `string`
- `integer`
- `number`
- `boolean`
- `array`
- `null`

A `type` may also be an array of supported type names.

Supported constraints:

- Every type: `enum`
- Strings: `minLength`, `maxLength`, `pattern`
- Numbers: `minimum`, `maximum`
- Arrays: `minItems`, `maxItems`, `items`, `uniqueItems`

The `pattern` value uses a Python-compatible regular expression and must match
the complete string.

Every case must contain exactly the number of arguments declared by
`domain_schema.args`.

### `number_tolerance`

Optional non-negative finite number. Default: `0`.

```json
"number_tolerance": 1e-9
```

It permits that absolute difference when comparing numeric values, including
numbers nested inside arrays or objects. Use it only when floating-point
rounding is expected.

## Writing effective cases

The gate can only enforce behavior you explicitly declare. Case quality matters
more than case count.

For each critical rule, include:

- One ordinary successful case.
- Values immediately below, at, and above every threshold.
- Empty and smallest valid values when defined.
- Maximum or large valid values when relevant.
- Negative, zero, fractional, duplicate, or Unicode values when the domain
  allows them.
- Inputs that distinguish similar but incorrect implementations.
- Previously observed failures as permanent regressions.

For a `$100` free-shipping boundary, testing only `$20` and `$200` is weak.
Testing `$99`, `$100`, and `$101` catches the common `>` versus `>=` error.

Do not add a case until its expected value is known from the actual
specification. If the expected behavior is ambiguous, clarify the specification
instead of letting an implementation or model invent the answer.

Keep cases inside the declared domain. An out-of-domain disagreement does not
show the implementation is wrong.

### Recommended AI-generation workflow

1. Write the critical behavioral rules.
2. Choose representative and boundary cases.
3. Record their expected values independently of the generated implementation.
4. Ask the generator to expose the critical function through a stable hook.
5. Generate the artifact.
6. Run Turing Gate.
7. Reject or revise on any failed check.
8. Add every discovered bug as a new permanent case.

Do not ask the same unverified implementation to define its own expected
results. That makes the test repeat the implementation’s mistake.

## Understanding results

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Every declared runtime and functional check passed. |
| `1` | Verification ran and rejected the artifact. |
| `2` | Configuration or browser setup is incomplete. |
| `130` | The command was interrupted. |

Use the exit code in scripts and CI. Do not search console text for the word
“PASS”.

### Verification checks

| Check | Meaning |
|---|---|
| `loads` | Chromium loaded the artifact. |
| `no_page_errors` | No uncaught page JavaScript errors occurred. |
| `no_console_err` | The page emitted no console errors. |
| `has_dom` | The page contains a non-trivial DOM. |
| `non_blank` | The page has visible content. |
| `interactive` | The page exposes at least one interaction affordance. |
| `no_outbound_requests` | No request escaped the temporary artifact origin. |
| `manifest_contract` | The declared hook exists and is callable. |
| `manifest_cases` | Every call returned its expected result. |

The runtime floor proves the page is loadable, visible, interactive, and
contained. Only `manifest_contract` plus meaningful `manifest_cases` establish
the declared functional behavior.

### JSON output

```bash
uv run turing-gate verify turing.json --json
```

The output includes:

- Manifest and artifact paths.
- Whether the manifest is runtime-only.
- Overall `passed` status.
- Every named check, Boolean result, and diagnostic detail.

Environment diagnostics are also available as JSON:

```bash
uv run turing-gate doctor --json
```

## Automation and CI

A minimal CI sequence is:

```bash
uv run turing-gate install-browser
uv run turing-gate doctor --json
uv run turing-gate verify path/to/turing.json --json
```

On a Linux runner without Playwright system libraries:

```bash
uv run turing-gate install-browser --with-deps
```

The verification command’s exit code should fail the job automatically.

Commit the artifact and `turing.json` together. A manifest is revision-sensitive
evidence: when behavior changes, update its cases in the same review.

Do not use `--force` during routine CI initialization. Prefer committing a
reviewed manifest so an existing contract cannot be silently replaced.

## Troubleshooting

### `GUI support is not installed`

The base package intentionally excludes the large Qt dependency. From a clone,
install or refresh the optional GUI tool once:

```bash
uv tool install --force ".[gui]"
```

Then run `turing-gate ui --check .` before opening the window.

### `Browser missing`

Run:

```bash
uv run turing-gate install-browser
```

On Linux:

```bash
uv run turing-gate install-browser --with-deps
```

Then confirm:

```bash
uv run turing-gate doctor
```

### `CONFIG ERROR: artifact not found`

Paths are resolved relative to the manifest file for verification. Confirm the
HTML filename and keep it inside the manifest directory.

### `artifact must stay inside the manifest directory`

Move the manifest to the artifact’s directory or place the artifact beneath
the manifest directory. Absolute paths and parent-directory escapes are not
allowed.

### `output already exists`

`init` will not overwrite an existing file by default. Review the existing
manifest. If replacement is truly intended:

```bash
uv run turing-gate init tool.html --force
```

### `manifest_contract` failed

Open the artifact and verify:

- The hook spelling exactly matches the manifest.
- Every object in the dotted path exists on `window` or `globalThis`.
- The final value is a function.
- The hook is assigned before page loading completes.

Example:

```javascript
window.__turing = { calculateShipping };
```

### `manifest_cases` failed

The diagnostic identifies the first labeled mismatch and may report additional
failures. Check:

- Argument order and types.
- Boundary operators such as `<` versus `<=`.
- Expected JSON types.
- Floating-point tolerance.
- Whether the case is actually inside the declared domain.

Do not change an expected value merely to make generated code pass. Confirm the
specification first.

### `no_outbound_requests` failed

Remove or localize external resources and calls, including:

- CDN scripts and stylesheets.
- Remote fonts and images.
- Analytics.
- `fetch`, `XMLHttpRequest`, `sendBeacon`, WebSocket, and similar calls.

The public gate supports self-contained artifacts.

### `interactive` failed

Add a real interaction affordance such as a button, input, select, textarea, or
link. A static report with no user interaction is outside the current product
focus.

### Page or console errors

Run the artifact directly in a browser and inspect its console. Fix uncaught
exceptions, missing local resources, and explicit `console.error` calls before
rerunning the gate.

## Privacy, security, and limits

### Local operation

The public verifier makes no model API calls and needs no API key.

Verification telemetry is written locally to:

```text
.turing/telemetry.jsonl
```

Nothing in the public CLI transmits this telemetry.

### Browser containment

Artifacts execute from a temporary loopback origin in a fresh browser context.
External requests and downloads are refused, and modal dialogs are
automatically dismissed. Temporary files and browser state are discarded after
verification.

### Not a security boundary

Turing Gate verifies declared behavior for honest generated code. It is not a
malware detector or proof that arbitrary code is safe. Any finite case set can
miss behavior triggered by an undeclared input.

Do not use the browser-only gate to run:

- Package installation.
- Build scripts.
- Native binaries.
- Local servers.
- Artifacts requiring filesystem or operating-system access.

Those require stronger container or virtual-machine isolation.

### Not a visual-quality judge

The runtime floor checks objective structure: loading, visible content, basic
interaction, errors, and containment. It does not establish that a design is
beautiful, persuasive, or pleasant to use.

### Runtime-only is not correctness

A runtime-only pass means the page loaded and met the containment/structure
floor. It does not mean calculations, validation, game rules, or other business
logic are correct.

## Command reference

### General

```bash
turing-gate --version
turing-gate --help
```

### Open the native GUI

```bash
turing-gate ui
turing-gate ui PROJECT_FOLDER
turing-gate ui --check PROJECT_FOLDER
```

### Create a manifest

```bash
turing-gate init ARTIFACT [options]
```

Options:

```text
--output PATH
--name NAME
--description TEXT
--hook DOTTED_FUNCTION
--case JSON
--domain-schema JSON
--number-tolerance NUMBER
--force
--json
```

### Verify

```bash
turing-gate verify MANIFEST
turing-gate verify MANIFEST --json
```

### Diagnose setup

```bash
turing-gate doctor
turing-gate doctor --json
```

### Install Chromium

```bash
turing-gate install-browser
turing-gate install-browser --with-deps
```

### Demonstrations

```bash
turing-gate demo
turing-gate demo wordle
turing-gate demo calculator
turing-gate demo exfiltration
```

## Final checklist

Before accepting a generated artifact:

- [ ] The artifact is self-contained HTML/JavaScript.
- [ ] The critical logic is exposed through a stable browser hook.
- [ ] Expected values come from the specification, not the candidate code.
- [ ] Cases include ordinary behavior and meaningful boundaries.
- [ ] The domain schema excludes undefined inputs.
- [ ] `doctor` reports ready.
- [ ] `verify` exits `0`.
- [ ] No check is being dismissed as “probably fine.”
- [ ] Runtime-only verification is not presented as functional correctness.
- [ ] The artifact receives normal human usability and visual review.

Project repository:
[github.com/nisimcode/Turing](https://github.com/nisimcode/Turing)

Release:
[Turing Gate v0.2.0](https://github.com/nisimcode/Turing/releases/tag/v0.2.0)
