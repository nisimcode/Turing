"""Canonical identities for reviewable gate artifacts."""

from __future__ import annotations

import hashlib
import json


def revision_digest(payload) -> str:
    """Stable SHA-256 identity for the exact material a human reviews."""
    encoded = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
