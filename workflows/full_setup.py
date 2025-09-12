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


def select_platforms(ui, asc, app_id: str) -> Dict[str, dict]:
    versions_resp = asc._request("GET", f"apps/{app_id}/appStoreVersions")
    versions = versions_resp.get("data", [])
    latest_by_platform: Dict[str, dict] = {}
    for v in versions:
        attrs = v.get("attributes", {})
        plat = attrs.get("platform", "UNKNOWN")
        if plat not in latest_by_platform:
            latest_by_platform[plat] = v
    if ui.available():
        choices = []
        for plat, v in latest_by_platform.items():
            a = v.get("attributes", {})
            choices.append({"name": f"{a.get('platform')} v{a.get('versionString')} ({a.get('appStoreState')})", "value": plat, "enabled": True})
        picked = ui.checkbox("Select platforms (Space to toggle, Enter to confirm)", choices, add_back=True)
        return {p: latest_by_platform[p] for p in (picked or [])}
    return latest_by_platform


def run(cli) -> bool:
    ui = cli.ui
    asc = cli.asc_client
    manager = cli.ai_manager

    print_info("Full Setup Mode - Complete localization setup")
    print("This mode adds all missing languages across selected platforms")
    print()

    app_id = ui.prompt_app_id(asc)
    if app_id is None:
        print_info("Cancelled")
        return True

    selected = select_platforms(ui, asc, app_id)
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
    missing = [loc for loc in APP_STORE_LOCALES.keys() if loc not in union_existing]
    if not missing:
        print_info("All supported languages are already localized!")
        return True

    # Choose targets
    if ui.available():
        choices = [{"name": f"{loc} - {APP_STORE_LOCALES[loc]}", "value": loc, "enabled": True} for loc in missing]
        target_locales = ui.checkbox("Select missing languages (Space to toggle, Enter to confirm)", choices, add_back=True)
        if not target_locales:
            target_locales = missing
    else:
        print("Missing languages:")
        for i, loc in enumerate(missing[:20], 1):
            print(f"{i:2d}. {loc} - {APP_STORE_LOCALES[loc]}")
        raw = input("Enter locales (comma-separated) or Enter for all: ").strip()
        target_locales = missing if not raw else [s.strip() for s in raw.split(',') if s.strip() in missing]
        if not target_locales:
            print_warning("No valid languages selected")
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
    # Use global refinement (no per-run prompt here; free text not requested)
    refine_phrase = (getattr(cli, 'config', None).get_prompt_refinement() if getattr(cli, 'config', None) else "") or ""
    # Show provider/model and choose seed
    pname, pmodel = provider_model_info(provider, selected_provider)
    seed = getattr(cli, 'session_seed', None)
    print_info(f"AI provider: {pname} — model: {pmodel or 'n/a'} — seed: {seed}")

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
