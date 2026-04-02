"""
Shared workflow helpers for selection prompts and provider setup.
"""

from typing import Dict, Iterable, List, Optional, Tuple

from utils import APP_STORE_LOCALES, print_error, print_info


def pick_locale_scope(
    ui,
    *,
    default: str = "missing",
    prompt: str = "Which locales do you want to include?",
) -> str:
    """Pick locale scope: 'existing', 'missing', or 'all'."""
    default = (default or "missing").strip().lower()
    if default not in ("existing", "missing", "all"):
        default = "missing"

    if ui.available():
        picked = ui.select(
            prompt,
            [
                {"name": "Existing locales only (update)", "value": "existing"},
                {"name": "Missing locales only (create)", "value": "missing"},
                {"name": "All locales (existing + missing)", "value": "all"},
            ],
            add_back=True,
        )
        return picked or default

    raw = input("Locales to include: (e)xisting, (m)issing, (a)ll (Enter = missing): ").strip().lower()
    if raw in ("b", "back"):
        return "back"
    if raw in ("e", "existing"):
        return "existing"
    if raw in ("a", "all", "*"):
        return "all"
    return "missing"


def pick_provider(
    cli,
    prompt: str = "Select AI provider",
    allow_cancel: bool = True,
) -> Tuple[Optional[object], Optional[str]]:
    """Select an AI provider and return (provider_instance, provider_key)."""
    ui = cli.ui
    manager = cli.ai_manager
    provs = manager.list_providers()
    if not provs:
        print_error("No AI providers configured. Run setup first.")
        return None, None

    selected_provider: Optional[str] = None
    default_provider = getattr(cli, "config", None).get_default_ai_provider() if getattr(cli, "config", None) else None

    if len(provs) == 1:
        selected_provider = provs[0]
        print_info(f"Using AI provider: {selected_provider}")
    else:
        if default_provider and default_provider in provs:
            use_default = ui.confirm(f"Use default AI provider: {default_provider}?", True)
            if use_default is None:
                raw = input(f"Use default provider '{default_provider}'? (Y/n): ").strip().lower()
                use_default = raw in ("", "y", "yes")
            if use_default:
                selected_provider = default_provider
        if not selected_provider:
            if ui.available():
                selected_provider = ui.select(
                    prompt,
                    [{"name": p + ("  (default)" if p == default_provider else ""), "value": p} for p in provs],
                    add_back=allow_cancel,
                )
            if not selected_provider:
                for i, p in enumerate(provs, 1):
                    star = " *" if p == default_provider else ""
                    print(f"{i}. {p}{star}")
                raw = input("Select provider (number) (Enter = default): ").strip().lower()
                if allow_cancel and raw in ("b", "back"):
                    print_info("Cancelled")
                    return None, None
                if not raw and default_provider and default_provider in provs:
                    selected_provider = default_provider
                else:
                    try:
                        idx = int(raw)
                        selected_provider = provs[idx - 1]
                    except Exception:
                        print_error("Invalid selection")
                        return None, None

    if not selected_provider:
        print_info("Cancelled")
        return None, None
    provider = manager.get_provider(selected_provider)
    return provider, selected_provider


def choose_target_locales(
    ui,
    available_targets: Dict[str, str],
    base_locale: str,
    preferred_locales: Optional[Iterable[str]] = None,
    prompt: str = "Select target locales",
) -> List[str]:
    """Choose target locales from a map of locale -> display name."""
    preferred_locales = set(preferred_locales or [])
    if not available_targets:
        return []

    default_checked = {loc for loc in available_targets if loc in preferred_locales}

    if ui.available():
        choices = [
            {"name": "🌐 Select all available locales", "value": "__all__"},
            {"name": "📝 Manual entry (comma-separated locales)", "value": "__manual__"},
        ]
        choices += [
            {"name": f"{loc} - {nm}", "value": loc, "enabled": loc in default_checked}
            for (loc, nm) in available_targets.items()
        ]
        selected = ui.checkbox(prompt, choices, add_back=True)
        if not selected:
            # In TUI mode, an empty selection should behave like "cancel/back".
            # Manual entry is explicitly available via "__manual__".
            return []
        selected = selected or []
        if "__all__" in selected:
            return [loc for loc in available_targets.keys() if loc != base_locale]
        if "__manual__" in selected:
            raw = input("Enter target locales (comma-separated): ").strip()
            if not raw:
                return []
            return [s.strip() for s in raw.split(",") if s.strip() in available_targets]
        if selected:
            return [s for s in selected if s in available_targets]
        return []

    print("Available target locales:")
    items = list(available_targets.items())
    col_width = 28
    for i in range(0, len(items), 2):
        left = items[i]
        right = items[i + 1] if i + 1 < len(items) else None
        left_txt = f"{left[0]:8} - {left[1]}".ljust(col_width)
        right_txt = f"{right[0]:8} - {right[1]}" if right else ""
        print(f"{left_txt} {right_txt}")
    default_list = sorted(default_checked)
    raw = input("Enter target locales (comma-separated, 'all' for every locale, Enter = app locales): ").strip()
    if not raw:
        return default_list if default_list else []
    if raw.lower() in ("all", "*"):
        return [loc for loc in available_targets.keys() if loc != base_locale]
    selected = [s.strip() for s in raw.split(',') if s.strip() in available_targets]
    return selected or default_list


def select_platform_versions(ui, asc_client, app_id: str):
    """Select latest version per platform for an app."""
    versions_resp = asc_client._request("GET", f"apps/{app_id}/appStoreVersions")
    versions = versions_resp.get("data", [])
    if not versions:
        print_error("No App Store versions found for this app")
        return None, None, None

    latest_by_platform: Dict[str, dict] = {}
    for v in versions:
        attrs = v.get("attributes", {})
        plat = attrs.get("platform", "UNKNOWN")
        if plat not in latest_by_platform:
            latest_by_platform[plat] = v

    plat_label = {"IOS": "iOS", "MAC_OS": "macOS", "TV_OS": "tvOS", "VISION_OS": "visionOS", "UNKNOWN": "Unknown"}

    selected_versions: Dict[str, dict] = {}
    if ui.available():
        choices = []
        for plat, v in latest_by_platform.items():
            attrs = v.get("attributes", {})
            name = f"{plat_label.get(plat, plat)} v{attrs.get('versionString', 'Unknown')} ({attrs.get('appStoreState', 'Unknown')})"
            choices.append({"name": name, "value": plat, "enabled": True})
        picked = ui.checkbox("Select platforms (Space to toggle, Enter to confirm)", choices, add_back=True)
        if not picked:
            print_info("Cancelled")
            return None, None, None
        for plat in picked:
            selected_versions[plat] = latest_by_platform[plat]
    else:
        print("Available platforms:")
        plats = list(latest_by_platform.keys())
        for i, plat in enumerate(plats, 1):
            attrs = latest_by_platform[plat].get("attributes", {})
            print(f"{i}. {plat_label.get(plat, plat)} v{attrs.get('versionString', 'Unknown')} ({attrs.get('appStoreState', 'Unknown')})")
        raw = input("Select platforms (comma numbers) or Enter for all, 'b' to back: ").strip().lower()
        if raw == 'b':
            print_info("Cancelled")
            return None, None, None
        if not raw:
            picked_idx = list(range(1, len(plats) + 1))
        else:
            try:
                picked_idx = [int(x.strip()) for x in raw.split(',')]
            except ValueError:
                print_error("Invalid selection")
                return None, None, None
        for idx in picked_idx:
            if 1 <= idx <= len(plats):
                plat = plats[idx - 1]
                selected_versions[plat] = latest_by_platform[plat]

    return selected_versions, latest_by_platform, plat_label


def get_app_locales(asc_client, app_id: str) -> set:
    """Return locales available on the latest App Store version (if any)."""
    try:
        latest_ver = asc_client.get_latest_app_store_version(app_id)
        if latest_ver:
            locs = asc_client.get_app_store_version_localizations(latest_ver).get("data", [])
            return {l.get("attributes", {}).get("locale") for l in locs if l.get("attributes", {}).get("locale")}
    except Exception:
        return set()
    return set()
