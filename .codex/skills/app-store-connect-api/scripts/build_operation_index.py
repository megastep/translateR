#!/usr/bin/env python3
"""Build a compact index from the App Store Connect OpenAPI spec."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


def default_spec_path() -> Path:
    return Path(__file__).resolve().parent.parent / "references" / "openapi.oas.json"


def default_output_path() -> Path:
    return Path(__file__).resolve().parent.parent / "references" / "operation-index.json"


def load_spec(spec_path: Path) -> Dict:
    with spec_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def iter_operations(spec: Dict) -> Iterable[Tuple[str, str, Dict]]:
    paths = spec.get("paths", {})
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, op in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete", "head", "options"}:
                continue
            if isinstance(op, dict):
                yield method.upper(), path, op


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
        default=str(default_output_path()),
        help="Where to write operation index JSON",
    )
    args = parser.parse_args()

    spec_path = Path(args.spec)
    out_path = Path(args.output)

    if not spec_path.exists():
        print(f"spec file not found: {spec_path}")
        return 1

    spec = load_spec(spec_path)
    index = {
        "info": spec.get("info", {}),
        "operationCount": 0,
        "operations": build_index(spec),
    }
    index["operationCount"] = len(index["operations"])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(index, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    print(f"Wrote {index['operationCount']} operations to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
