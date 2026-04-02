"""
Translation Mode workflow with multi-platform handling.
"""

from typing import Dict
import time

from utils import (
    APP_STORE_LOCALES,
    get_field_limit,
    print_info,
    print_warning,
    print_error,
    truncate_keywords,
    detect_base_language,
    parallel_map_locales,
    provider_model_info,
)
from workflows.helpers import pick_provider, select_platform_versions, choose_target_locales, pick_locale_scope


def run(cli) -> bool:
    ui = cli.ui
    asc = cli.asc_client

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
    selected_versions, _, _ = select_platform_versions(ui, asc, app_id)
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
    locales_with_empty_description = set()
    for plat, ver in selected_versions.items():
        locs = asc.get_app_store_version_localizations(ver["id"]).get("data", [])
        locale_codes = set()
        for loc in locs:
            attrs = loc.get("attributes", {})
            locale_code = attrs.get("locale")
            if not locale_code:
                continue
            locale_codes.add(locale_code)
            if not (attrs.get("description") or "").strip():
                locales_with_empty_description.add(locale_code)
        existing_by_platform[plat] = locale_codes

    union_existing = set()
    for locales in existing_by_platform.values():
        union_existing.update(locales)

    def _is_locale_available(loc: str) -> bool:
        if loc == base_locale:
            return False
        if loc not in union_existing:
            return True
        return loc in locales_with_empty_description

    # Locale scope (existing/missing/all)
    scope = pick_locale_scope(ui, default="missing", prompt="Which locales do you want to translate?")
    if scope == "back":
        print_info("Cancelled")
        return True

    supported_minus_base = {k: v for k, v in APP_STORE_LOCALES.items() if k != base_locale}
    existing_minus_base = {loc for loc in union_existing if loc and loc != base_locale}
    missing_or_empty = {loc for loc in supported_minus_base.keys() if _is_locale_available(loc)}

    if scope == "existing":
        available_targets = {k: supported_minus_base[k] for k in sorted(existing_minus_base) if k in supported_minus_base}
        preferred = sorted(existing_minus_base)
    elif scope == "all":
        available_targets = supported_minus_base
        preferred = sorted(existing_minus_base)
    else:
        available_targets = {k: supported_minus_base[k] for k in sorted(missing_or_empty) if k in supported_minus_base}
        preferred = sorted(available_targets.keys())

    if not available_targets:
        print_warning("No locales available for that selection")
        return True

    # Choose targets
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

    # Provider
    provider, selected_provider = pick_provider(cli)
    if not provider:
        return True
    # Use global refinement (no per-run prompt here; free text not requested)
    refine_phrase = (getattr(cli, 'config', None).get_prompt_refinement() if getattr(cli, 'config', None) else "") or ""
    # Show provider/model and choose seed for this run
    pname, pmodel, extra = provider_model_info(provider, selected_provider)
    seed = getattr(cli, 'session_seed', None)
    tier = extra.get("service_tier")
    tier_txt = f" — tier: {tier}" if tier else ""
    print_info(f"AI provider: {pname} — model: {pmodel or 'n/a'}{tier_txt} — seed: {seed}")

    # Translate and create per platform (parallel by locale)
    print_info(f"Starting translation for {len(target_locales)} languages across {len(selected_versions)} platform(s)...")
    def _task(loc: str):
        language_name = APP_STORE_LOCALES.get(loc, loc)
        translated = {}
        if base_data.get("description"):
            translated["description"] = provider.translate(base_data["description"], language_name, max_length=get_field_limit("description"), seed=seed, refinement=refine_phrase)
        if base_data.get("keywords"):
            kw = provider.translate(base_data["keywords"], language_name, max_length=get_field_limit("keywords"), is_keywords=True, seed=seed, refinement=refine_phrase)
            translated["keywords"] = truncate_keywords(kw)
        if base_data.get("promotionalText"):
            translated["promotionalText"] = provider.translate(base_data["promotionalText"], language_name, max_length=get_field_limit("promotional_text"), seed=seed, refinement=refine_phrase)
        if base_data.get("whatsNew"):
            translated["whatsNew"] = provider.translate(base_data["whatsNew"], language_name, max_length=get_field_limit("whats_new"), seed=seed, refinement=refine_phrase)
        if base_data.get("marketingUrl"):
            translated["marketingUrl"] = base_data["marketingUrl"]
        if base_data.get("supportUrl"):
            translated["supportUrl"] = base_data["supportUrl"]
        time.sleep(1)
        return translated

    results, errs = parallel_map_locales(target_locales, _task, progress_action="Translated", pacing_seconds=0.0)

    # Warn on empty translations per locale
    for loc in target_locales:
        language_name = APP_STORE_LOCALES.get(loc, loc)
        data = results.get(loc) or {}
        has_any = any((v or "").strip() for v in data.values() if isinstance(v, str))
        if not has_any:
            print_warning(f"Empty translation for {language_name} [{loc}]")

    for target_locale, translated_data in results.items():
        for plat, ver in selected_versions.items():
            locs = asc.get_app_store_version_localizations(ver["id"]).get("data", [])
            exists = any(l["attributes"]["locale"] == target_locale for l in locs)
            if exists:
                loc_id = next(l["id"] for l in locs if l["attributes"]["locale"] == target_locale)
                asc.update_app_store_version_localization(
                    localization_id=loc_id,
                    description=translated_data.get("description"),
                    keywords=translated_data.get("keywords"),
                    promotional_text=translated_data.get("promotionalText"),
                    whats_new=translated_data.get("whatsNew"),
                    marketing_url=translated_data.get("marketingUrl"),
                    support_url=translated_data.get("supportUrl"),
                )
            else:
                asc.create_app_store_version_localization(
                    version_id=ver["id"],
                    locale=target_locale,
                    description=translated_data.get("description", ""),
                    keywords=translated_data.get("keywords"),
                    promotional_text=translated_data.get("promotionalText"),
                    whats_new=translated_data.get("whatsNew"),
                    marketing_url=translated_data.get("marketingUrl"),
                    support_url=translated_data.get("supportUrl"),
                )

    # Optional: App name/subtitle
    if include_app_info:
        print_warning("App name/subtitle translation for multi-platform is not yet implemented in this refactor.")

    input("\nPress Enter to continue...")
    return True
