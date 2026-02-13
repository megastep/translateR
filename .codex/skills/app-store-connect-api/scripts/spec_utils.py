#!/usr/bin/env python3
"""Shared OpenAPI spec utilities for App Store Connect skill scripts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, Tuple

_ALLOWED_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}


def script_root() -> Path:
    return Path(__file__).resolve().parent


def skill_root() -> Path:
    return script_root().parent


def references_dir() -> Path:
    return skill_root() / "references"


def default_spec_path() -> Path:
    return references_dir() / "openapi.oas.json"


def load_spec(spec_path: Path) -> Dict:
    with spec_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def iter_operations(spec: Dict) -> Iterable[Tuple[str, str, Dict]]:
    for path, path_item in (spec.get("paths", {}) or {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in _ALLOWED_METHODS:
                continue
            if isinstance(operation, dict):
                yield method.upper(), path, operation


def resolve_output_in_references(raw_output: str) -> Path:
    """Resolve output path and enforce it stays under references directory."""

    refs = references_dir().resolve()
    candidate = Path(raw_output)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (refs / candidate).resolve()

    if not resolved.is_relative_to(refs):
        raise ValueError(f"output must be inside {refs}, got: {resolved}")

    return resolved
