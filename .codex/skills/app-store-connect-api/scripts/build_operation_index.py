#!/usr/bin/env python3
"""Build a compact index from the App Store Connect OpenAPI spec."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

from spec_utils import (
    default_spec_path,
    iter_operations,
    load_spec,
    references_dir,
    resolve_output_in_references,
)


def default_output_path() -> Path:
    return references_dir() / "operation-index.json"


def build_index(spec: Dict) -> List[Dict]:
    records: List[Dict] = []
    for method, path, op in iter_operations(spec):
        records.append(
            {
                "method": method,
                "path": path,
                "operationId": op.get("operationId"),
                "summary": op.get("summary"),
                "tags": [t for t in op.get("tags", []) if isinstance(t, str)],
                "hasRequestBody": isinstance(op.get("requestBody"), dict),
                "responseCodes": sorted((op.get("responses") or {}).keys()),
            }
        )
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", default=str(default_spec_path()), help="Path to OpenAPI json")
    parser.add_argument(
        "--output",
        default=str(default_output_path().name),
        help=(
            "Output file path under references/. Absolute paths are allowed only if they "
            "still resolve inside references/."
        ),
    )
    args = parser.parse_args()

    spec_path = Path(args.spec)
    if not spec_path.exists():
        print(f"spec file not found: {spec_path}")
        return 1

    try:
        out_path = resolve_output_in_references(args.output)
    except ValueError as exc:
        print(str(exc))
        return 2

    spec = load_spec(spec_path)
    index = {
        "info": spec.get("info", {}),
        "operationCount": 0,
        "operations": build_index(spec),
    }
    index["operationCount"] = len(index["operations"])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump(index, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    print(f"Wrote {index['operationCount']} operations to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
