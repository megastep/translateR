"""
App Name & Subtitle translation workflow.
Note: App Info is global at the app level (not per platform).
"""

from typing import Dict
import time

from utils import APP_STORE_LOCALES, get_field_limit, print_info, print_warning, print_success, print_error, format_progress


def run(cli) -> bool:
    ui = cli.ui
    asc = cli.asc_client
    manager = cli.ai_manager

    print_info("App Name & Subtitle Mode - Translate app name and subtitle")

    # App selection
    app_id = ui.prompt_app_id(asc)
    if app_id is None:
        print_info("Cancelled")
        return True

    app_info_id = asc.find_primary_app_info_id(app_id)
    if not app_info_id:
        print_error("Could not find app info for this app")
        return True

    existing_localizations = asc.get_app_info_localizations(app_info_id)
    loc_map: Dict[str, str] = {}
    for loc in existing_localizations.get("data", []):
        loc_map[loc["attributes"]["locale"]] = loc["id"]

    # Base localization
    base_locale = None
    base_name = ""
    base_subtitle = ""
    for loc in existing_localizations.get("data", []):
        attrs = loc.get("attributes", {})
        # Prefer en-US
        if attrs.get("locale") == "en-US":
            base_locale = "en-US"
            base_id = loc["id"]
            base_attrs = asc.get_app_info_localization(base_id).get("data", {}).get("attributes", {})
            base_name = base_attrs.get("name", "")
            base_subtitle = base_attrs.get("subtitle", "")
            break
    if not base_locale:
        # Fallback to first
        any_id = existing_localizations.get("data", [])[0]["id"]
        base_attrs = asc.get_app_info_localization(any_id).get("data", {}).get("attributes", {})
        base_name = base_attrs.get("name", "")
        base_subtitle = base_attrs.get("subtitle", "")

    if not base_name and not base_subtitle:
        print_error("No name or subtitle found in base language")
        return True

    # Targets
    available_targets = [loc for loc in APP_STORE_LOCALES if loc not in loc_map]
    if ui.available():
        choices = [{"name": f"{loc} ({APP_STORE_LOCALES[loc]})", "value": loc} for loc in available_targets]
        target_locales = ui.checkbox("Select target languages (Space to toggle, Enter to confirm)", choices, add_back=True)
        if not target_locales:
            print_warning("No target languages selected")
            return True
    else:
        print(", ".join([f"{l} ({APP_STORE_LOCALES[l]})" for l in available_targets[:10]]))
        raw = input("Enter target locales (comma-separated): ").strip()
        if not raw:
            print_warning("No target languages selected")
            return True
        target_locales = [s.strip() for s in raw.split(',') if s.strip() in available_targets]
        if not target_locales:
            print_warning("No valid locales selected")
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

    print_info(f"Starting app name & subtitle translation for {len(target_locales)} languages...")
    success = 0
    for i, target_locale in enumerate(target_locales, 1):
        language_name = APP_STORE_LOCALES.get(target_locale, "Unknown")
        print()
        print(format_progress(i, len(target_locales), f"Translating to {language_name}"))
        try:
            translated_name = None
            translated_subtitle = None
            if base_name:
                translated_name = provider.translate(base_name, language_name, max_length=get_field_limit("name"))
            if base_subtitle:
                translated_subtitle = provider.translate(base_subtitle, language_name, max_length=get_field_limit("subtitle"))
            asc.create_app_info_localization(app_info_id, target_locale, translated_name, translated_subtitle)
            success += 1
            time.sleep(1)
        except Exception as e:
            print_error(f"  ❌ Failed to translate {language_name}: {str(e)}")
            continue

    print_success(f"App name & subtitle translation completed! {success}/{len(target_locales)} languages translated successfully")
    input("\nPress Enter to continue...")
    return True

