"""Portable, deterministic verification manifests for user-owned artifacts."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .domain import validate_args, validate_schema
from .verify import verify

HOOK_RE = re.compile(
    r"^(?:(?:window|globalThis)\.)?"
    r"[A-Za-z_$][A-Za-z0-9_$]*"
    r"(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*$"
)
MAX_CASES = 1_000


class ManifestError(ValueError):
    """The manifest is unsafe, incomplete, or internally inconsistent."""


@dataclass(frozen=True)
class Manifest:
    path: Path
    name: str
    artifact: Path
    hook: str | None
    cases: tuple[dict[str, Any], ...]
    domain_schema: dict[str, Any] | None
    number_tolerance: float
    description: str = ""

    @property
    def runtime_only(self) -> bool:
        return self.hook is None


def _reject_constant(value: str):
    raise ManifestError(f"non-JSON numeric constant is not allowed: {value}")


def _inside(base: Path, relative: str, field: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute():
        raise ManifestError(f"{field} must be relative to the manifest")
    resolved = (base / candidate).resolve()
    try:
        resolved.relative_to(base.resolve())
    except ValueError as exc:
        raise ManifestError(f"{field} must stay inside the manifest directory") from exc
    return resolved


def load_manifest(path: str | Path) -> Manifest:
    """Load and validate a schema-version-1 manifest."""
    manifest_path = Path(path).resolve()
    if not manifest_path.is_file():
        raise ManifestError(f"manifest not found: {manifest_path}")
    try:
        data = json.loads(
            manifest_path.read_text(encoding="utf-8"),
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise ManifestError(
            f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    if not isinstance(data, dict):
        raise ManifestError("manifest root must be an object")
    if data.get("schema_version") != 1:
        raise ManifestError("schema_version must be 1")

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ManifestError("name must be a non-empty string")

    artifact_value = data.get("artifact")
    if not isinstance(artifact_value, str) or not artifact_value.strip():
        raise ManifestError("artifact must be a relative HTML path")
    artifact = _inside(
        manifest_path.parent, artifact_value, "artifact"
    )
    if artifact.suffix.lower() not in {".html", ".htm"}:
        raise ManifestError("artifact must be an HTML file")
    if not artifact.is_file():
        raise ManifestError(f"artifact not found: {artifact}")

    hook = data.get("hook")
    cases = data.get("cases", [])
    if hook is None:
        if cases not in (None, []):
            raise ManifestError("cases require a hook")
        cases = []
    else:
        if not isinstance(hook, str) or not HOOK_RE.fullmatch(hook):
            raise ManifestError(
                "hook must be a dotted browser identifier, "
                "for example window.__tool.evaluate"
            )
        if not isinstance(cases, list) or not cases:
            raise ManifestError("a functional hook requires at least one case")
        if len(cases) > MAX_CASES:
            raise ManifestError(f"cases cannot exceed {MAX_CASES}")

    domain_schema = data.get("domain_schema")
    if domain_schema is not None and not isinstance(domain_schema, dict):
        raise ManifestError("domain_schema must be an object")
    if domain_schema is not None:
        schema_errors = validate_schema(domain_schema)
        if schema_errors:
            raise ManifestError(f"invalid domain_schema: {'; '.join(schema_errors)}")

    validated_cases: list[dict[str, Any]] = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ManifestError(f"cases[{index}] must be an object")
        args = case.get("args")
        if not isinstance(args, list):
            raise ManifestError(f"cases[{index}].args must be an array")
        if "expected" not in case:
            raise ManifestError(f"cases[{index}] must contain expected")
        if domain_schema is not None:
            errors = validate_args(args, domain_schema)
            if errors:
                raise ManifestError(
                    f"cases[{index}] is outside domain_schema: {'; '.join(errors)}"
                )
        label = case.get("label", f"case {index + 1}")
        if not isinstance(label, str) or not label.strip():
            raise ManifestError(f"cases[{index}].label must be a non-empty string")
        validated_cases.append(
            {"label": label, "args": args, "expected": case["expected"]}
        )

    tolerance = data.get("number_tolerance", 0)
    if (not isinstance(tolerance, (int, float))
            or isinstance(tolerance, bool)
            or not math.isfinite(tolerance)
            or tolerance < 0):
        raise ManifestError("number_tolerance must be a finite non-negative number")

    description = data.get("description", "")
    if not isinstance(description, str):
        raise ManifestError("description must be a string")

    return Manifest(
        path=manifest_path,
        name=name.strip(),
        artifact=artifact,
        hook=hook,
        cases=tuple(validated_cases),
        domain_schema=domain_schema,
        number_tolerance=float(tolerance),
        description=description.strip(),
    )


def values_equal(actual: Any, expected: Any, tolerance: float) -> bool:
    """Deep JSON comparison with an optional absolute numeric tolerance."""
    numeric = (
        isinstance(actual, (int, float))
        and not isinstance(actual, bool)
        and isinstance(expected, (int, float))
        and not isinstance(expected, bool)
    )
    if numeric:
        return (
            math.isfinite(actual)
            and math.isfinite(expected)
            and abs(float(actual) - float(expected)) <= tolerance
        )
    if isinstance(actual, list) and isinstance(expected, list):
        return (
            len(actual) == len(expected)
            and all(
                values_equal(left, right, tolerance)
                for left, right in zip(actual, expected)
            )
        )
    if isinstance(actual, dict) and isinstance(expected, dict):
        return (
            actual.keys() == expected.keys()
            and all(
                values_equal(actual[key], expected[key], tolerance)
                for key in actual
            )
        )
    return type(actual) is type(expected) and actual == expected


def _functional(manifest: Manifest):
    hook_parts = manifest.hook.split(".") if manifest.hook else []
    if hook_parts and hook_parts[0] in {"window", "globalThis"}:
        hook_parts = hook_parts[1:]

    async_js = """
    async ({parts, cases}) => {
      let owner = globalThis;
      for (const part of parts.slice(0, -1)) {
        if (owner == null || !(part in owner)) {
          return {contract: false, results: []};
        }
        owner = owner[part];
      }
      const name = parts[parts.length - 1];
      const fn = owner == null ? undefined : owner[name];
      if (typeof fn !== "function") {
        return {contract: false, results: []};
      }
      const results = [];
      for (const test of cases) {
        try {
          const value = await fn.apply(owner, test.args);
          results.push(
            value === undefined
              ? {ok: true, undefined: true}
              : {ok: true, value}
          );
        } catch (error) {
          results.push({
            ok: false,
            error: String(error && error.message ? error.message : error)
          });
        }
      }
      return {contract: true, results};
    }
    """

    def check(page):
        outcome = page.evaluate(
            async_js,
            {
                "parts": hook_parts,
                "cases": [{"args": case["args"]} for case in manifest.cases],
            },
        )
        contract = bool(outcome.get("contract"))
        checks = [{
            "name": "manifest_contract",
            "ok": contract,
            "detail": manifest.hook or "",
        }]
        if not contract:
            return checks

        results = outcome.get("results", [])
        mismatches = []
        if len(results) != len(manifest.cases):
            mismatches.append(
                f"hook returned {len(results)} results for "
                f"{len(manifest.cases)} cases"
            )
        for index, case in enumerate(manifest.cases):
            if index >= len(results):
                mismatches.append(f"{case['label']}: no result returned")
                continue
            result = results[index]
            if not result.get("ok"):
                mismatches.append(
                    f"{case['label']}: raised {result.get('error', 'unknown error')}"
                )
                continue
            if result.get("undefined"):
                mismatches.append(f"{case['label']}: returned undefined")
                continue
            actual = result.get("value")
            if not values_equal(
                actual, case["expected"], manifest.number_tolerance
            ):
                mismatches.append(
                    f"{case['label']}: got {actual!r}, "
                    f"expected {case['expected']!r}"
                )

        ok = not mismatches
        detail = (
            f"all {len(manifest.cases)} cases correct"
            if ok
            else mismatches[0]
            + (f" (+{len(mismatches) - 1} more)" if len(mismatches) > 1 else "")
        )
        checks.append({"name": "manifest_cases", "ok": ok, "detail": detail})
        return checks

    return check


def verify_manifest(path: str | Path):
    """Load a manifest and verify its exact artifact."""
    manifest = load_manifest(path)
    functional = None if manifest.runtime_only else _functional(manifest)
    verdict = verify(
        manifest.artifact,
        functional=functional,
        vertical=manifest.name,
    )
    return manifest, verdict
