#!/usr/bin/env python3
"""Query helper for the App Store Connect OpenAPI specification."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


def default_spec_path() -> Path:
    return Path(__file__).resolve().parent.parent / "references" / "openapi.oas.json"


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
            if not isinstance(op, dict):
                continue
            yield method.upper(), path, op


def cmd_summary(spec: Dict) -> int:
    info = spec.get("info", {})
    servers = spec.get("servers", [])
    methods = {}
    tags = set()

    op_count = 0
    for method, _path, op in iter_operations(spec):
        op_count += 1
        methods[method] = methods.get(method, 0) + 1
        for tag in op.get("tags", []):
            if isinstance(tag, str):
                tags.add(tag)

    print(f"title: {info.get('title', 'n/a')}")
    print(f"version: {info.get('version', 'n/a')}")
    print(f"servers: {len(servers)}")
    for server in servers:
        url = server.get("url") if isinstance(server, dict) else None
        if url:
            print(f"  - {url}")
    print(f"paths: {len(spec.get('paths', {}))}")
    print(f"operations: {op_count}")
    print("methods:")
    for method in sorted(methods):
        print(f"  {method}: {methods[method]}")
    print(f"tags: {len(tags)}")
    for tag in sorted(tags):
        print(f"  - {tag}")
    return 0


def operation_text(method: str, path: str, op: Dict) -> str:
    fields: List[str] = [method, path]
    for key in ("operationId", "summary", "description"):
        value = op.get(key)
        if isinstance(value, str):
            fields.append(value)
    for tag in op.get("tags", []):
        if isinstance(tag, str):
            fields.append(tag)
    return "\n".join(fields).lower()


def cmd_search(spec: Dict, keyword: str, limit: int) -> int:
    keyword = keyword.lower().strip()
    if not keyword:
        print("keyword cannot be empty")
        return 2

    matches = []
    for method, path, op in iter_operations(spec):
        haystack = operation_text(method, path, op)
        if keyword in haystack:
            matches.append((method, path, op))

    if not matches:
        print("No matches")
        return 0

    for method, path, op in matches[:limit]:
        op_id = op.get("operationId", "")
        summary = op.get("summary", "")
        tags = ", ".join(t for t in op.get("tags", []) if isinstance(t, str))
        print(f"{method:6} {path}")
        if op_id:
            print(f"  operationId: {op_id}")
        if summary:
            print(f"  summary: {summary}")
        if tags:
            print(f"  tags: {tags}")
        print()

    if len(matches) > limit:
        print(f"... {len(matches) - limit} more match(es)")

    return 0


def cmd_show(spec: Dict, method: str, path: str) -> int:
    target = spec.get("paths", {}).get(path, {})
    op = target.get(method.lower()) if isinstance(target, dict) else None
    if not isinstance(op, dict):
        print(f"Operation not found: {method.upper()} {path}")
        return 1

    print(f"{method.upper()} {path}")
    if op.get("operationId"):
        print(f"operationId: {op['operationId']}")
    if op.get("summary"):
        print(f"summary: {op['summary']}")
    if op.get("description"):
        print(f"description: {op['description']}")

    tags = [t for t in op.get("tags", []) if isinstance(t, str)]
    if tags:
        print(f"tags: {', '.join(tags)}")

    parameters = op.get("parameters", [])
    print("parameters:")
    if parameters:
        for param in parameters:
            name = param.get("name", "unknown")
            location = param.get("in", "unknown")
            required = bool(param.get("required", False))
            schema_type = (param.get("schema") or {}).get("type", "unknown")
            print(f"  - {name} ({location}) required={required} type={schema_type}")
    else:
        print("  - none")

    request_body = op.get("requestBody")
    print("requestBody:")
    if isinstance(request_body, dict):
        required = bool(request_body.get("required", False))
        content = request_body.get("content", {})
        mime_types = sorted(content.keys()) if isinstance(content, dict) else []
        print(f"  required={required}")
        print(f"  content_types={', '.join(mime_types) if mime_types else 'none'}")
    else:
        print("  - none")

    responses = op.get("responses", {})
    print("responses:")
    if responses:
        for status in sorted(responses.keys()):
            desc = responses.get(status, {}).get("description", "")
            print(f"  - {status}: {desc}")
    else:
        print("  - none")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--spec",
        default=str(default_spec_path()),
        help="Path to OpenAPI json file.",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("summary", help="Print high-level API summary")

    search = sub.add_parser("search", help="Search operations by keyword")
    search.add_argument("keyword", help="Keyword to search in path, operationId, summary, tags")
    search.add_argument("--limit", type=int, default=25, help="Max operations to print")

    show = sub.add_parser("show", help="Show one operation details")
    show.add_argument("method", help="HTTP method, e.g. GET")
    show.add_argument("path", help="Path, e.g. /v1/apps")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    spec_path = Path(args.spec)
    if not spec_path.exists():
        print(f"spec file not found: {spec_path}")
        return 1

    spec = load_spec(spec_path)

    if args.command == "summary":
        return cmd_summary(spec)
    if args.command == "search":
        return cmd_search(spec, keyword=args.keyword, limit=args.limit)
    if args.command == "show":
        return cmd_show(spec, method=args.method, path=args.path)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
