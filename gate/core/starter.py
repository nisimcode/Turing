"""Safe, deterministic starter-manifest creation for the public CLI."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .manifest import ManifestError, load_manifest


def _reject_constant(value: str):
    raise ManifestError(f"non-JSON numeric constant is not allowed: {value}")


def _json_object(value: str, field: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value, parse_constant=_reject_constant)
    except json.JSONDecodeError as exc:
        raise ManifestError(
            f"{field} is invalid JSON at column {exc.colno}: {exc.msg}"
        ) from exc
    if not isinstance(parsed, dict):
        raise ManifestError(f"{field} must be a JSON object")
    return parsed


def create_starter_manifest(
    artifact_value: str | Path,
    *,
    output_value: str | Path | None = None,
    name: str | None = None,
    description: str | None = None,
    hook: str | None = None,
    case_values: list[str] | None = None,
    domain_schema_value: str | None = None,
    number_tolerance: float | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Validate and atomically create one version-1 manifest.

    With no hook this intentionally creates a runtime-only starter. Functional
    mode requires at least one explicit JSON case; no expected behavior is
    guessed.
    """
    artifact = Path(artifact_value).resolve()
    if not artifact.is_file():
        raise ManifestError(f"artifact not found: {artifact}")
    if artifact.suffix.lower() not in {".html", ".htm"}:
        raise ManifestError("artifact must be an HTML file")

    if output_value is None:
        output = artifact.parent / "turing.json"
    else:
        requested = Path(output_value)
        if not requested.is_absolute():
            requested = Path.cwd() / requested
        parent = requested.parent.resolve()
        output = parent / requested.name
    if output.suffix.lower() != ".json":
        raise ManifestError("output must be a JSON file")
    if not output.parent.is_dir():
        raise ManifestError(f"output directory not found: {output.parent}")
    if output == artifact:
        raise ManifestError("output cannot overwrite the HTML artifact")
    if output.exists() and not output.is_file():
        raise ManifestError(f"output is not a regular file: {output}")
    if output.exists() and not force:
        raise ManifestError(
            f"output already exists: {output} (use --force to replace it)"
        )

    try:
        relative_artifact = artifact.relative_to(output.parent.resolve())
    except ValueError as exc:
        raise ManifestError(
            "artifact must stay inside the output manifest directory"
        ) from exc

    cases = [
        _json_object(value, f"case {index}")
        for index, value in enumerate(case_values or [], start=1)
    ]
    domain_schema = (
        _json_object(domain_schema_value, "domain schema")
        if domain_schema_value is not None
        else None
    )
    if hook is None and (cases or domain_schema is not None):
        raise ManifestError("--case and --domain-schema require --hook")
    if hook is not None and not cases:
        raise ManifestError("--hook requires at least one --case")
    if hook is None and number_tolerance is not None:
        raise ManifestError("--number-tolerance requires --hook")

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "name": name if name is not None else artifact.stem,
        "description": description if description is not None else (
            f"Runtime-only starter for {artifact.name}; add a hook and "
            "explicit cases to verify functional correctness."
            if hook is None
            else f"Functional verification for {artifact.name}."
        ),
        "artifact": relative_artifact.as_posix(),
    }
    if hook is not None:
        manifest["hook"] = hook
        if domain_schema is not None:
            manifest["domain_schema"] = domain_schema
        if number_tolerance is not None:
            manifest["number_tolerance"] = number_tolerance
        manifest["cases"] = cases

    encoded = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=".turing-starter-",
            suffix=".json",
            dir=output.parent,
            delete=False,
        ) as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)

        # The temporary manifest lives beside the final path, so artifact path
        # confinement and every schema/case rule are validated before publish.
        checked = load_manifest(temporary)
        if force:
            os.replace(temporary, output)
            temporary = None
        else:
            try:
                os.link(temporary, output)
            except FileExistsError as exc:
                raise ManifestError(
                    f"output already exists: {output} "
                    "(use --force to replace it)"
                ) from exc
        return {
            "schema_version": 1,
            "manifest": str(output),
            "artifact": str(artifact),
            "runtime_only": checked.runtime_only,
            "cases": len(checked.cases),
        }
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
