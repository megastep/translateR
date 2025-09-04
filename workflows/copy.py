"""
Copy Mode workflow with per-platform selection.
"""

from typing import Dict, List, Optional
import sys
import time

from utils import APP_STORE_LOCALES, format_progress, print_info, print_warning, print_success, print_error


def select_platforms(ui, asc_client, app_id: str) -> Optional[Dict[str, dict]]:
    versions_response = asc_client._request("GET", f"apps/{app_id}/appStoreVersions")
    versions = versions_response.get("data", [])
    if not versions:
        print_error("No App Store versions found for this app")
        return None
    latest_by_platform: Dict[str, dict] = {}
    for v in versions:
        attrs = v.get("attributes", {})
        plat = attrs.get("platform", "UNKNOWN")
        if plat not in latest_by_platform:
            latest_by_platform[plat] = v
    # Choose platforms
    if ui.available():
        choices = []
        for plat, v in latest_by_platform.items():
            attrs = v.get("attributes", {})
            label = f"{attrs.get('platform','?')} v{attrs.get('versionString','?')} ({attrs.get('appStoreState','?')})"
            choices.append({"name": label, "value": plat, "enabled": True})
        picked = ui.checkbox("Select platforms to copy (Space to toggle, Enter to confirm)", choices, add_back=True)
        if not picked:
            print_info("Cancelled")
            return None
        return {p: latest_by_platform[p] for p in picked}
    else:
        return latest_by_platform


def pick_version_for_platform(ui, asc_client, app_id: str, platform: str, prompt: str) -> Optional[dict]:
    versions_response = asc_client._request("GET", f"apps/{app_id}/appStoreVersions")
    versions = [v for v in versions_response.get("data", []) if v.get("attributes", {}).get("platform") == platform]
    if not versions:
        print_error(f"No versions found for platform {platform}")
        return None
    if ui.available():
        choices = []
        for v in versions[:20]:
            a = v.get("attributes", {})
            choices.append({"name": f"{a.get('versionString','?')} ({a.get('appStoreState','?')})", "value": v})
        sel = ui.select(prompt, choices, add_back=True)
        return sel
    else:
        print(prompt)
        for i, v in enumerate(versions[:20], 1):
            a = v.get("attributes", {})
            print(f"{i}. {a.get('versionString','?')} ({a.get('appStoreState','?')})")
        raw = input("Select version (number): ").strip()
        try:
            idx = int(raw)
            return versions[idx - 1]
        except Exception:
            print_error("Invalid selection")
            return None


def run(cli) -> bool:
    ui = cli.ui
    asc = cli.asc_client

    print_info("Copy Mode - Copy content from previous version")
    print()

    app_id = ui.prompt_app_id(asc)
    if app_id is None:
        print_info("Cancelled")
        return True

    selected_platforms = select_platforms(ui, asc, app_id)
    if not selected_platforms:
        return True

    for plat, latest_ver in selected_platforms.items():
        # Pick source and target versions for this platform
        source = pick_version_for_platform(ui, asc, app_id, plat, f"Select source {plat} version to copy FROM")
        if not source:
            print_warning(f"Skipped {plat}")
            continue
        target = pick_version_for_platform(ui, asc, app_id, plat, f"Select target {plat} version to copy TO")
        if not target:
            print_warning(f"Skipped {plat}")
            continue
        if source["id"] == target["id"]:
            print_error("Source and target versions cannot be the same")
            continue

        print_info(f"Copying from {source['attributes'].get('versionString')} to {target['attributes'].get('versionString')} ({plat})")
        # Determine locales in source
        source_localizations = asc.get_app_store_version_localizations(source["id"]).get("data", [])
        if not source_localizations:
            print_warning("No localizations found in source version")
            continue
        locales_to_copy: List[str] = [loc["attributes"]["locale"] for loc in source_localizations]

        # Copy loop
        success = 0
        last_len = 0
        total = len(locales_to_copy)
        for i, locale in enumerate(locales_to_copy, 1):
            language_name = APP_STORE_LOCALES.get(locale, "Unknown")
            try:
                line = format_progress(i, total, f"Copying {language_name} ({plat})")
                pad = max(0, last_len - len(line))
                sys.stdout.write("\r" + line + (" " * pad))
                sys.stdout.flush()
                last_len = len(line)
            except Exception:
                print(format_progress(i, total, f"Copying {language_name} ({plat})"))
            try:
                ok = asc.copy_localization_from_previous_version(source["id"], target["id"], locale)
                if ok:
                    success += 1
                time.sleep(1)
            except Exception as e:
                print_error(f"  ❌ Error copying {language_name}: {str(e)}")
                continue
        try:
            sys.stdout.write("\r" + (" " * last_len) + "\r")
            sys.stdout.flush()
        except Exception:
            pass
        print()
        print_success(f"{plat}: {success}/{total} localizations copied successfully")

    input("\nPress Enter to continue...")
    return True

