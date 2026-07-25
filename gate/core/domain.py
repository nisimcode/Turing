"""Machine-checkable input-domain contracts (Q21).

Natural-language domain descriptions are useful to humans and models but cannot
stop a generated oracle from testing an undefined input. This module implements
a deliberately small JSON-schema-like subset for function argument lists.
"""

from __future__ import annotations

import math
import re

TYPES = {"string", "integer", "number", "boolean", "array", "null"}
SPEC_KEYS = {
    "type", "enum", "minLength", "maxLength", "pattern",
    "minimum", "maximum", "minItems", "maxItems", "items", "uniqueItems",
}


def validate_schema(schema: dict) -> list[str]:
    """Validate the supported argument-schema subset before checking cases."""
    if not isinstance(schema, dict):
        return ["schema: expected an object"]
    if set(schema) != {"args"} or not isinstance(schema.get("args"), list):
        return ["schema: expected only an args array"]

    errors = []

    def visit(spec, path):
        if not isinstance(spec, dict):
            errors.append(f"{path}: schema is not an object")
            return
        unknown = sorted(set(spec) - SPEC_KEYS)
        if unknown:
            errors.append(f"{path}: unsupported keys: {', '.join(unknown)}")
        kinds = spec.get("type")
        kinds = kinds if isinstance(kinds, list) else [kinds]
        if (
            not kinds
            or not all(isinstance(kind, str) and kind in TYPES for kind in kinds)
        ):
            errors.append(f"{path}: type must use {', '.join(sorted(TYPES))}")
        if "enum" in spec and not isinstance(spec["enum"], list):
            errors.append(f"{path}.enum: expected an array")
        for key in ("minLength", "maxLength", "minItems", "maxItems"):
            value = spec.get(key)
            if key in spec and (
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
                errors.append(f"{path}.{key}: expected a non-negative integer")
        for key in ("minimum", "maximum"):
            value = spec.get(key)
            if key in spec and (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(value)
            ):
                errors.append(f"{path}.{key}: expected a finite number")
        if "pattern" in spec:
            try:
                re.compile(spec["pattern"])
            except (re.error, TypeError):
                errors.append(f"{path}.pattern: expected a valid regex string")
        if "uniqueItems" in spec and not isinstance(spec["uniqueItems"], bool):
            errors.append(f"{path}.uniqueItems: expected a boolean")
        if "items" in spec:
            visit(spec["items"], f"{path}.items")

    for index, spec in enumerate(schema["args"]):
        visit(spec, f"schema.args[{index}]")
    return errors


def _type_ok(value, kind: str) -> bool:
    if kind == "string":
        return isinstance(value, str)
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return (isinstance(value, (int, float))
                and not isinstance(value, bool))
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "array":
        return isinstance(value, list)
    if kind == "null":
        return value is None
    return False


def validate_value(value, spec: dict, path: str) -> list[str]:
    """Return domain violations for one JSON-compatible value."""
    if not isinstance(spec, dict):
        return [f"{path}: schema is not an object"]

    if "enum" in spec and value not in spec["enum"]:
        return [f"{path}: value is not in enum"]

    kinds = spec.get("type")
    kinds = kinds if isinstance(kinds, list) else [kinds]
    if not kinds or not all(isinstance(kind, str) for kind in kinds):
        return [f"{path}: schema has no valid type"]
    if not any(_type_ok(value, kind) for kind in kinds):
        return [f"{path}: expected {'|'.join(kinds)}"]

    errors = []
    if isinstance(value, str):
        if len(value) < spec.get("minLength", 0):
            errors.append(f"{path}: shorter than minLength")
        if "maxLength" in spec and len(value) > spec["maxLength"]:
            errors.append(f"{path}: longer than maxLength")
        if "pattern" in spec:
            try:
                matches = re.fullmatch(spec["pattern"], value)
            except (re.error, TypeError):
                errors.append(f"{path}: invalid schema pattern")
            else:
                if matches is None:
                    errors.append(f"{path}: does not match pattern")

    if (isinstance(value, (int, float))
            and not isinstance(value, bool)):
        if "minimum" in spec and value < spec["minimum"]:
            errors.append(f"{path}: below minimum")
        if "maximum" in spec and value > spec["maximum"]:
            errors.append(f"{path}: above maximum")

    if isinstance(value, list):
        if len(value) < spec.get("minItems", 0):
            errors.append(f"{path}: fewer than minItems")
        if "maxItems" in spec and len(value) > spec["maxItems"]:
            errors.append(f"{path}: more than maxItems")
        if spec.get("uniqueItems"):
            frozen = [repr(item) for item in value]
            if len(frozen) != len(set(frozen)):
                errors.append(f"{path}: items are not unique")
        if "items" in spec:
            for index, item in enumerate(value):
                errors.extend(validate_value(
                    item, spec["items"], f"{path}[{index}]"
                ))
    return errors


def validate_args(args, schema: dict) -> list[str]:
    """Validate a function argument list against {"args": [schemas...]}."""
    if not isinstance(args, list):
        return ["args: expected an array"]
    specs = schema.get("args") if isinstance(schema, dict) else None
    if not isinstance(specs, list):
        return ["schema: expected an args array"]
    if len(args) != len(specs):
        return [f"args: expected {len(specs)} values, got {len(args)}"]
    errors = []
    for index, (value, spec) in enumerate(zip(args, specs)):
        errors.extend(validate_value(value, spec, f"args[{index}]"))
    return errors


def filter_cases(cases: list[dict], schema: dict
                 ) -> tuple[list[dict], list[dict]]:
    """Split oracle cases into in-domain and clarification-required groups."""
    accepted, rejected = [], []
    for case in cases:
        errors = validate_args(case.get("args"), schema)
        if errors:
            rejected.append({**case, "domain_errors": errors})
        else:
            accepted.append(case)
    return accepted, rejected
