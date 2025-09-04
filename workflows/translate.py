"""
Translation Mode workflow with multi-platform handling.
"""

from typing import Dict
import time

from utils import APP_STORE_LOCALES, get_field_limit, format_progress, print_info, print_warning, print_success, print_error, truncate_keywords, detect_base_language


def select_platform_versions(ui, asc_client, app_id: str):
    versions_resp = asc_client._request("GET", f"apps/{app_id}/appStoreVersions")
    versions = versions_resp.get("data", [])
    if not versions:
        print_error("No App Store versions found for this app")
        return None, None
    latest_by_platform: Dict[str, dict] = {}
    for v in versions:
        attrs = v.get("attributes", {})
        plat = attrs.get("platform", "UNKNOWN")
        if plat not in latest_by_platform:
            latest_by_platform[plat] = v
    if ui.available():
        choices = []
        for plat, v in latest_by_platform.items():
            attrs = v.get("attributes", {})
            name = f"{attrs.get('platform','?')} v{attrs.get('versionString','?')} ({attrs.get('appStoreState','?')})"
            choices.append({"name": name, "value": plat, "enabled": True})
        picked = ui.checkbox("Select platforms (Space to toggle, Enter to confirm)", choices, add_back=True)
        if not picked:
            print_info("Cancelled")
            return None, None
        selected = {p: latest_by_platform[p] for p in picked}
    else:
        selected = latest_by_platform
    return selected, latest_by_platform


def run(cli) -> bool:
    ui = cli.ui
    asc = cli.asc_client
    manager = cli.ai_manager

    print_info("Translation Mode - Translate existing content to new languages")
    print()

    # Translation type
    include_app_info = False
    if ui.available():
        choice = ui.select(
            "Select translation type",
            [
                {"name": "Metadata Only (description, keywords, promotional text, what's new)", "value": "1"},
                {"name": "Complete Translation (metadata + app name & subtitle)", "value": "2"},
            ], add_back=True,
        )
        if choice is None:
            print_info("Cancelled")
            return True
        include_app_info = (choice == '2')
    else:
        print("1) Metadata Only\n2) Complete Translation")
        raw = input("Select (1-2): ").strip()
        if raw not in ['1', '2']:
            print_error("Invalid selection")
            return True
        include_app_info = (raw == '2')

    # App
    app_id = ui.prompt_app_id(asc)
    if app_id is None:
        print_info("Cancelled")
        return True

    # Platforms
    selected_versions, _ = select_platform_versions(ui, asc, app_id)
    if not selected_versions:
        return True

    # Use first platform to derive base + localizations
    first_ver = next(iter(selected_versions.values()))
    vid = first_ver["id"]
    localizations_response = asc.get_app_store_version_localizations(vid)
    localizations = localizations_response.get("data", [])
    if not localizations:
        print_error("No existing localizations found")
        return True

    base_locale = detect_base_language(localizations)
    if not base_locale:
        print_error("Could not detect base language")
        return True
    print_info(f"Detected base language: {base_locale} ({APP_STORE_LOCALES.get(base_locale, 'Unknown')})")

    # Source base data
    base_data = None
    for loc in localizations:
        if loc["attributes"]["locale"] == base_locale:
            base_data = loc["attributes"]
            break
    if not base_data:
        print_error("Could not find base localization data")
        return True

    # Target languages (union across selected platforms)
    existing_by_platform: Dict[str, set] = {}
    for plat, ver in selected_versions.items():
        locs = asc.get_app_store_version_localizations(ver["id"]).get("data", [])
        existing_by_platform[plat] = {l["attributes"]["locale"] for l in locs}
    union_existing = set().union(*existing_by_platform.values())
    available_targets = {k: v for k, v in APP_STORE_LOCALES.items() if k not in union_existing and k != base_locale}
    if not available_targets:
        print_warning("All supported languages are already localized for selected platforms")
        return True

    # Choose targets
    if ui.available():
        choices = [{"name": f"{loc} - {nm}", "value": loc} for (loc, nm) in available_targets.items()]
        target_locales = ui.checkbox("Select target languages (Space to toggle, Enter to confirm)", choices, add_back=True)
        if not target_locales:
            print_warning("No target languages selected")
            return True
    else:
        for i, (loc, nm) in enumerate(list(available_targets.items())[:20], 1):
            print(f"{i:2d}. {loc:8} - {nm}")
        raw = input("Enter target locales (comma-separated): ").strip()
        if not raw:
            print_warning("No target languages selected")
            return True
        target_locales = [s.strip() for s in raw.split(',') if s.strip() in available_targets]
        if not target_locales:
            print_warning("No valid target languages selected")
            return True

    # Provider
    provs = manager.list_providers()
    if len(provs) == 1:
        selected_provider = provs[0]
        print_info(f"Using AI provider: {selected_provider}")
    else:
        selected_provider = None
        if ui.available():
            selected_provider = ui.select("Select AI provider", [{"name": p, "value": p} for p in provs], add_back=True)
        if not selected_provider:
            for i, p in enumerate(provs, 1):
                print(f"{i}. {p}")
            raw = input("Select provider (number): ").strip()
            try:
                idx = int(raw)
                selected_provider = provs[idx - 1]
            except Exception:
                print_error("Invalid selection")
                return True
    provider = manager.get_provider(selected_provider)

    # Translate and create per platform
    print_info(f"Starting translation for {len(target_locales)} languages across {len(selected_versions)} platform(s)...")
    for i, target_locale in enumerate(target_locales, 1):
        language_name = APP_STORE_LOCALES.get(target_locale, "Unknown")
        print()
        print(format_progress(i, len(target_locales), f"Translating to {language_name}"))
        try:
            translated_data = {}
            # Description
            if base_data.get("description"):
                translated_data["description"] = provider.translate(base_data["description"], language_name, max_length=get_field_limit("description"))
            # Keywords
            if base_data.get("keywords"):
                kw = provider.translate(base_data["keywords"], language_name, max_length=get_field_limit("keywords"), is_keywords=True)
                translated_data["keywords"] = truncate_keywords(kw)
            # Promo
            if base_data.get("promotionalText"):
                translated_data["promotionalText"] = provider.translate(base_data["promotionalText"], language_name, max_length=get_field_limit("promotional_text"))
            # What's New
            if base_data.get("whatsNew"):
                translated_data["whatsNew"] = provider.translate(base_data["whatsNew"], language_name, max_length=get_field_limit("whats_new"))

            for plat, ver in selected_versions.items():
                # Skip if already exists for this platform
                locs = asc.get_app_store_version_localizations(ver["id"]).get("data", [])
                exists = any(l["attributes"]["locale"] == target_locale for l in locs)
                if exists:
                    # Update existing selectively
                    loc_id = next(l["id"] for l in locs if l["attributes"]["locale"] == target_locale)
                    asc.update_app_store_version_localization(
                        localization_id=loc_id,
                        description=translated_data.get("description"),
                        keywords=translated_data.get("keywords"),
                        promotional_text=translated_data.get("promotionalText"),
                        whats_new=translated_data.get("whatsNew"),
                    )
                else:
                    # Create new
                    asc.create_app_store_version_localization(
                        version_id=ver["id"],
                        locale=target_locale,
                        description=translated_data.get("description", ""),
                        keywords=translated_data.get("keywords"),
                        promotional_text=translated_data.get("promotionalText"),
                        whats_new=translated_data.get("whatsNew"),
                    )
            time.sleep(2)
        except Exception as e:
            print_error(f"  ❌ Failed to translate {language_name}: {str(e)}")
            continue

    # Optional: App name/subtitle
    if include_app_info:
        print_warning("App name/subtitle translation for multi-platform is not yet implemented in this refactor.")

    input("\nPress Enter to continue...")
    return True

