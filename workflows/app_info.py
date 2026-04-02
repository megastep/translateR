"""
App Name & Subtitle translation workflow.
Note: App Info is global at the app level (not per platform).
"""

from typing import Dict
import time

from utils import APP_STORE_LOCALES, get_field_limit, print_info, print_warning, print_success, print_error, format_progress, parallel_map_locales, provider_model_info
from workflows.helpers import pick_provider, choose_target_locales, pick_locale_scope


def run(cli) -> bool:
    ui = cli.ui
    asc = cli.asc_client

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
    scope = pick_locale_scope(ui, default="missing", prompt="Which locales do you want to include?")
    if scope == "back":
        print_info("Cancelled")
        return True

    supported_minus_base = {k: v for k, v in APP_STORE_LOCALES.items() if k != base_locale}
    existing_minus_base = {loc for loc in loc_map.keys() if loc and loc != base_locale}
    missing = {loc for loc in supported_minus_base.keys() if loc not in loc_map}
    if scope == "existing":
        available_targets = {loc: supported_minus_base[loc] for loc in sorted(existing_minus_base) if loc in supported_minus_base}
        preferred = sorted(existing_minus_base)
    elif scope == "all":
        available_targets = supported_minus_base
        preferred = sorted(existing_minus_base)
    else:
        available_targets = {loc: supported_minus_base[loc] for loc in sorted(missing) if loc in supported_minus_base}
        preferred = sorted(available_targets.keys())
    target_locales = choose_target_locales(
        ui,
        available_targets,
        base_locale,
        preferred_locales=preferred,
        prompt="Select target languages",
    )
    if not target_locales:
        print_warning("No target languages selected")
        return True

    provider, selected_provider = pick_provider(cli)
    if not provider:
        return True
    # Use global refinement (no per-run prompt here; free text not requested)
    refine_phrase = (getattr(cli, 'config', None).get_prompt_refinement() if getattr(cli, 'config', None) else "") or ""
    # Show provider/model and choose seed
    pname, pmodel, extra = provider_model_info(provider, selected_provider)
    seed = getattr(cli, 'session_seed', None)
    tier = extra.get("service_tier")
    tier_txt = f" — tier: {tier}" if tier else ""
    print_info(f"AI provider: {pname} — model: {pmodel or 'n/a'}{tier_txt} — seed: {seed}")

    print_info(f"Starting app name & subtitle translation for {len(target_locales)} languages...")
    def _task(loc: str):
        language_name = APP_STORE_LOCALES.get(loc, loc)
        name_out = provider.translate(base_name, language_name, max_length=get_field_limit("name"), seed=seed, refinement=refine_phrase) if base_name else None
        subtitle_out = provider.translate(base_subtitle, language_name, max_length=get_field_limit("subtitle"), seed=seed, refinement=refine_phrase) if base_subtitle else None
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
