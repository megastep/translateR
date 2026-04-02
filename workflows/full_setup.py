"""
Full Setup Mode: translate missing languages across selected platforms.
"""

from typing import Dict
import time

from utils import (
    APP_STORE_LOCALES, detect_base_language, get_field_limit, truncate_keywords,
    print_info, print_warning, print_success, print_error, format_progress,
    parallel_map_locales, provider_model_info,
)
from workflows.helpers import pick_provider, select_platform_versions, choose_target_locales, pick_locale_scope


def run(cli) -> bool:
    ui = cli.ui
    asc = cli.asc_client

    print_info("Full Setup Mode - Complete localization setup")
    print("This mode adds all missing languages across selected platforms")
    print()

    app_id = ui.prompt_app_id(asc)
    if app_id is None:
        print_info("Cancelled")
        return True

    selected, _, _ = select_platform_versions(ui, asc, app_id)
    if not selected:
        print_warning("No platforms selected")
        return True

    # Determine base and existing locales
    first_ver = next(iter(selected.values()))
    locs = asc.get_app_store_version_localizations(first_ver["id"]).get("data", [])
    if not locs:
        print_error("No localizations found")
        return True
    base_locale = detect_base_language(locs)
    if not base_locale:
        print_error("Could not detect base language")
        return True
    print_info(f"Base language: {base_locale} ({APP_STORE_LOCALES.get(base_locale, 'Unknown')})")

    base_attrs = {}
    for l in locs:
        if l["attributes"]["locale"] == base_locale:
            base_attrs = l["attributes"]
            break
    if not any([base_attrs.get("description"), base_attrs.get("keywords"), base_attrs.get("promotionalText"), base_attrs.get("whatsNew")]):
        print_error("Base localization has no content to translate")
        return True

    # Missing locales union
    union_existing = set()
    for plat, ver in selected.items():
        ls = asc.get_app_store_version_localizations(ver["id"]).get("data", [])
        union_existing |= {x["attributes"]["locale"] for x in ls}
    supported_minus_base = {k: v for k, v in APP_STORE_LOCALES.items() if k != base_locale}
    existing_minus_base = {loc for loc in union_existing if loc and loc != base_locale}
    missing = [loc for loc in supported_minus_base.keys() if loc not in union_existing]

    scope = pick_locale_scope(ui, default="missing", prompt="Which locales do you want to include?")
    if scope == "back":
        print_info("Cancelled")
        return True

    if scope == "existing":
        available_targets = {loc: supported_minus_base[loc] for loc in sorted(existing_minus_base) if loc in supported_minus_base}
        preferred = sorted(existing_minus_base)
    elif scope == "all":
        available_targets = supported_minus_base
        preferred = sorted(existing_minus_base)
    else:
        available_targets = {loc: supported_minus_base[loc] for loc in sorted(missing) if loc in supported_minus_base}
        preferred = None

    if not available_targets:
        print_info("No locales available for that selection")
        return True

    # Choose targets
    target_locales = choose_target_locales(
        ui,
        available_targets,
        base_locale,
        preferred_locales=preferred,
        prompt="Select languages",
    )
    if not target_locales:
        print_warning("No valid languages selected")
        return True

    # Provider
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

    print_info(f"Starting full setup for {len(target_locales)} languages across {len(selected)} platform(s)...")
    def _task(loc: str):
        language_name = APP_STORE_LOCALES.get(loc, loc)
        translated = {}
        if base_attrs.get("description"):
            translated["description"] = provider.translate(base_attrs["description"], language_name, max_length=get_field_limit("description"), seed=seed, refinement=refine_phrase)
        if base_attrs.get("keywords"):
            kw = provider.translate(base_attrs["keywords"], language_name, max_length=get_field_limit("keywords"), is_keywords=True, seed=seed, refinement=refine_phrase)
            translated["keywords"] = truncate_keywords(kw)
        if base_attrs.get("promotionalText"):
            translated["promotionalText"] = provider.translate(base_attrs["promotionalText"], language_name, max_length=get_field_limit("promotional_text"), seed=seed, refinement=refine_phrase)
        if base_attrs.get("whatsNew"):
            translated["whatsNew"] = provider.translate(base_attrs["whatsNew"], language_name, max_length=get_field_limit("whats_new"), seed=seed, refinement=refine_phrase)
        time.sleep(1)
        return translated

    results, errs = parallel_map_locales(target_locales, _task, progress_action="Setup", pacing_seconds=0.0)

    # Warn on empty translations per locale
    for loc in target_locales:
        language_name = APP_STORE_LOCALES.get(loc, loc)
        data = results.get(loc) or {}
        has_any = any((v or "").strip() for v in data.values() if isinstance(v, str))
        if not has_any:
            print_warning(f"Empty translation for {language_name} [{loc}]")

    for target_locale, translated in results.items():
        for plat, ver in selected.items():
            asc.create_app_store_version_localization(
                version_id=ver["id"],
                locale=target_locale,
                description=translated.get("description", ""),
                keywords=translated.get("keywords"),
                promotional_text=translated.get("promotionalText"),
                whats_new=translated.get("whatsNew"),
            )

    print_success("✅ Full setup completed!")
    input("\nPress Enter to continue...")
    return True
