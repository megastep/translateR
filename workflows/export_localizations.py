"""
Export Localizations workflow with platform selection.
"""

from typing import Dict

from utils import print_info, print_warning, print_success, export_existing_localizations


def select_platform(ui, asc, app_id: str) -> Dict[str, dict]:
    versions_resp = asc._request("GET", f"apps/{app_id}/appStoreVersions")
    versions = versions_resp.get("data", [])
    latest_by_platform: Dict[str, dict] = {}
    for v in versions:
        a = v.get("attributes", {})
        p = a.get("platform", "UNKNOWN")
        if p not in latest_by_platform:
            latest_by_platform[p] = v
    if ui.available():
        choices = []
        for plat, v in latest_by_platform.items():
            a = v.get("attributes", {})
            choices.append({"name": f"{a.get('platform')} v{a.get('versionString')} ({a.get('appStoreState')})", "value": plat})
        sel = ui.select("Select platform to export", choices, add_back=True)
        return {sel: latest_by_platform[sel]} if sel else {}
    else:
        return latest_by_platform


def run(cli) -> bool:
    ui = cli.ui
    asc = cli.asc_client

    print_info("Export Localizations Mode - Export all existing localizations to file")
    print()

    app_id = ui.prompt_app_id(asc)
    if app_id is None:
        print_info("Cancelled")
        return True

    selected = select_platform(ui, asc, app_id)
    if not selected:
        print_warning("No platform selected")
        return True

    # App name for file
    apps_response = asc.get_apps(limit=200)
    app_name = "Unknown App"
    for app in apps_response.get("data", []):
        if app["id"] == app_id:
            app_name = app.get("attributes", {}).get("name", "Unknown App")
            break

    for plat, ver in selected.items():
        locs = asc.get_app_store_version_localizations(ver["id"]).get("data", [])
        filename = export_existing_localizations(locs, app_name=app_name, app_id=app_id, version_string=ver.get("attributes", {}).get("versionString", "unknown"))
        print_success(f"Exported {len(locs)} localizations to {filename}")

    input("\nPress Enter to continue...")
    return True

