"""
App Name & Subtitle translation workflow.
Note: App Info is global at the app level (not per platform).
"""

from typing import Dict
import time
import random

from utils import APP_STORE_LOCALES, get_field_limit, print_info, print_warning, print_success, print_error, format_progress, parallel_map_locales, provider_model_info


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
    selected_provider = None
    if len(provs) == 1:
        selected_provider = provs[0]
        print_info(f"Using AI provider: {selected_provider}")
    else:
        default_provider = getattr(cli, 'config', None).get_default_ai_provider() if getattr(cli, 'config', None) else None
        if default_provider and default_provider in provs:
            use_default = ui.confirm(f"Use default AI provider: {default_provider}?", True)
            if use_default is None:
                raw = input(f"Use default provider '{default_provider}'? (Y/n): ").strip().lower()
                use_default = raw in ("", "y", "yes")
            if use_default:
                selected_provider = default_provider
        if not selected_provider:
            if ui.available():
                selected_provider = ui.select("Select AI provider", [{"name": p + ("  (default)" if p == default_provider else ""), "value": p} for p in provs], add_back=True)
            if not selected_provider:
                for i, p in enumerate(provs, 1):
                    star = " *" if p == default_provider else ""
                    print(f"{i}. {p}{star}")
                raw = input("Select provider (number) (Enter = default): ").strip()
                if not raw and default_provider and default_provider in provs:
                    selected_provider = default_provider
                else:
                    try:
                        idx = int(raw)
                        selected_provider = provs[idx - 1]
                    except Exception:
                        print_error("Invalid selection")
                        return True
    provider = manager.get_provider(selected_provider)
    # Show provider/model and choose seed
    pname, pmodel = provider_model_info(provider, selected_provider)
    seed = random.randint(1, 2**31 - 1)
    print_info(f"AI provider: {pname} — model: {pmodel or 'n/a'} — seed: {seed}")

    print_info(f"Starting app name & subtitle translation for {len(target_locales)} languages...")
    def _task(loc: str):
        language_name = APP_STORE_LOCALES.get(loc, loc)
        name_out = provider.translate(base_name, language_name, max_length=get_field_limit("name"), seed=seed) if base_name else None
        subtitle_out = provider.translate(base_subtitle, language_name, max_length=get_field_limit("subtitle"), seed=seed) if base_subtitle else None
        time.sleep(1)
        return {"name": name_out, "subtitle": subtitle_out}

    results, errs = parallel_map_locales(target_locales, _task, progress_action="Translated", pacing_seconds=0.0)

    # Warn on empty translations per locale
    for loc in target_locales:
        language_name = APP_STORE_LOCALES.get(loc, loc)
        data = results.get(loc) or {}
        name_ok = (data.get("name") or "").strip()
        subtitle_ok = (data.get("subtitle") or "").strip()
        if not (name_ok or subtitle_ok):
            print_warning(f"Empty translation for {language_name} [{loc}]")

    success = 0
    for target_locale, data in results.items():
        try:
            asc.create_app_info_localization(app_info_id, target_locale, data.get("name"), data.get("subtitle"))
            success += 1
        except Exception as e:
            language_name = APP_STORE_LOCALES.get(target_locale, target_locale)
            print_error(f"  ❌ Failed to save {language_name}: {str(e)}")

    print_success(f"App name & subtitle translation completed! {success}/{len(target_locales)} languages translated successfully")
    input("\nPress Enter to continue...")
    return True
