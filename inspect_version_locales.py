#!/usr/bin/env python3
"""
Inspect App Store version localization codes by reading back Apple API data.

Usage:
    python inspect_version_locales.py <app-id>
    python inspect_version_locales.py <app-id> --version-id <version-id> --json
"""

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

from app_store_client import AppStoreConnectClient
from config import ConfigManager
from utils import APP_STORE_LOCALES, resolve_private_key_path


def build_locale_rows(response: Dict[str, Any]) -> List[Dict[str, str]]:
    """Convert ASC appStoreVersionLocalizations payload to sorted report rows."""
    rows: List[Dict[str, str]] = []
    for item in response.get("data", []) or []:
        attrs = item.get("attributes", {}) or {}
        locale = (attrs.get("locale") or "").strip()
        if not locale:
            continue
        rows.append(
            {
                "locale": locale,
                "name": APP_STORE_LOCALES.get(locale, "<unknown>"),
                "id": item.get("id", ""),
            }
        )
    rows.sort(key=lambda row: row["locale"])
    return rows


def format_locale_rows(rows: List[Dict[str, str]]) -> str:
    """Render locale rows as a plain text table."""
    headers = ("Locale", "Name", "ID")
    locale_width = max(len(headers[0]), *(len(row["locale"]) for row in rows)) if rows else len(headers[0])
    name_width = max(len(headers[1]), *(len(row["name"]) for row in rows)) if rows else len(headers[1])
    id_width = max(len(headers[2]), *(len(row["id"]) for row in rows)) if rows else len(headers[2])

    lines = [
        f"{headers[0]:<{locale_width}}  {headers[1]:<{name_width}}  {headers[2]:<{id_width}}",
        f"{'-' * locale_width}  {'-' * name_width}  {'-' * id_width}",
    ]
    for row in rows:
        lines.append(f"{row['locale']:<{locale_width}}  {row['name']:<{name_width}}  {row['id']:<{id_width}}")
    return "\n".join(lines)


def load_client() -> AppStoreConnectClient:
    """Build an ASC client from local config files."""
    config = ConfigManager()
    asc_config = config.get_app_store_config()
    if not asc_config:
        raise RuntimeError("App Store Connect configuration not found in config/api_keys.json")

    resolved_key_path = resolve_private_key_path(
        key_id=asc_config["key_id"],
        configured_path=asc_config.get("private_key_path"),
    )
    with open(resolved_key_path, "r", encoding="utf-8") as handle:
        private_key = handle.read()

    return AppStoreConnectClient(
        key_id=asc_config["key_id"],
        issuer_id=asc_config["issuer_id"],
        private_key=private_key,
    )


def resolve_target_version_id(client: AppStoreConnectClient, app_id: str, version_id: Optional[str]) -> str:
    """Resolve a version id from explicit input or latest version lookup."""
    if version_id:
        return version_id
    latest = client.get_latest_app_store_version(app_id)
    if not latest:
        raise RuntimeError(f"Could not find an App Store version for app_id={app_id}")
    return latest


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Read back App Store version localization locale codes.")
    parser.add_argument("app_id", help="App ID to inspect")
    parser.add_argument("--version-id", help="Explicit App Store version ID to inspect instead of the latest version")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Print rows as JSON")
    args = parser.parse_args(argv)

    try:
        client = load_client()
        target_version_id = resolve_target_version_id(client, args.app_id, args.version_id)
        response = client.get_app_store_version_localizations(target_version_id)
        rows = build_locale_rows(response)
    except Exception as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    if args.as_json:
        print(json.dumps({"app_id": args.app_id, "version_id": target_version_id, "rows": rows}, ensure_ascii=False, indent=2))
    else:
        print(f"App ID: {args.app_id}")
        print(f"Version ID: {target_version_id}")
        print()
        print(format_locale_rows(rows))
        if any(row["name"] == "<unknown>" for row in rows):
            print("\nNote: <unknown> means the locale was returned by ASC but is not mapped in APP_STORE_LOCALES.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
