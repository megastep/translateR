"""
Update Mode workflow with multi-platform handling.
"""

from typing import Dict
import time
import random

from utils import (
    APP_STORE_LOCALES, detect_base_language, get_field_limit, truncate_keywords,
    print_info, print_warning, print_error, format_progress,
    parallel_map_locales, provider_model_info,
)


def select_platform_versions(ui, asc_client, app_id: str):
    versions_resp = asc_client._request("GET", f"apps/{app_id}/appStoreVersions")
    versions = versions_resp.get("data", [])
    if not versions:
        print_error("No App Store versions found for this app")
        return None
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
            return None
        selected = {p: latest_by_platform[p] for p in picked}
    else:
        selected = latest_by_platform
    return selected


def run(cli) -> bool:
    ui = cli.ui
    asc = cli.asc_client
    manager = cli.ai_manager

    print_info("Update Mode - Update existing localizations with new content")
    print("Perfect for updating specific fields in existing languages (e.g., What's New)")
    print()

    app_id = ui.prompt_app_id(asc)
    if app_id is None:
        print_info("Cancelled")
        return True

    selected_versions = select_platform_versions(ui, asc, app_id)
    if not selected_versions:
        return True

    # Use first platform to find base and content
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

    base_data = None
    for loc in localizations:
        if loc["attributes"]["locale"] == base_locale:
            base_data = loc["attributes"]
            break
    if not base_data:
        print_error("Could not find base localization data")
        return True

    # Choose languages to update (existing excluding base, across union of platforms)
    existing_by_platform: Dict[str, set] = {}
    for plat, ver in selected_versions.items():
        locs = asc.get_app_store_version_localizations(ver["id"]).get("data", [])
        existing_by_platform[plat] = {l["attributes"]["locale"] for l in locs}
    union_existing = set().union(*existing_by_platform.values())
    existing_locales = [l for l in union_existing if l != base_locale]
    if not existing_locales:
        print_warning("No other localizations found to update")
        return True

    # TUI checkbox
    if ui.available():
        choices = [{"name": f"{loc} ({APP_STORE_LOCALES.get(loc, 'Unknown')})", "value": loc} for loc in existing_locales]
        target_locales = ui.checkbox("Select languages to update (Space to toggle, Enter to confirm)", choices, add_back=True)
        if not target_locales:
            print_warning("No languages selected")
            return True
    else:
        for i, loc in enumerate(existing_locales, 1):
            print(f"{i:2d}. {loc} ({APP_STORE_LOCALES.get(loc, 'Unknown')})")
        raw = input("Languages to update (comma-separated): ").strip()
        if not raw:
            print_warning("No languages selected")
            return True
        target_locales = [s.strip() for s in raw.split(',') if s.strip() in existing_locales]
        if not target_locales:
            print_warning("No valid languages selected")
            return True

    # Fields to update (available in base)
    field_mapping = {
        "description": ("Description", base_data.get("description")),
        "keywords": ("Keywords", base_data.get("keywords")),
        "promotional_text": ("Promotional Text", base_data.get("promotionalText")),
        "whats_new": ("What's New", base_data.get("whatsNew")),
    }
    available_fields = [k for k, (_, v) in field_mapping.items() if v]
    if not available_fields:
        print_error("No content found in base language to translate")
        return True

    if ui.available():
        name_map = {"description": "Description", "keywords": "Keywords", "promotional_text": "Promotional Text", "whats_new": "What's New"}
        choices = [{"name": name_map[f], "value": f} for f in available_fields]
        selected_fields = ui.checkbox("Select fields to update (Space to toggle, Enter to confirm)", choices, add_back=True)
        if not selected_fields:
            print_warning("No fields selected")
            return True
    else:
        print("Available fields:", ", ".join(available_fields))
        raw = input("Fields to update (comma-separated): ").strip()
        if not raw:
            print_warning("No fields selected")
            return True
        selected_fields = [s.strip() for s in raw.split(',') if s.strip() in available_fields]
        if not selected_fields:
            print_warning("No valid fields selected")
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
    seed = random.randint(1, 2**31 - 1)
    print_info(f"AI provider: {pname} — model: {pmodel or 'n/a'} — seed: {seed}")

    # Summary
    print_info("Update Summary:")
    print(f"  • Languages: {len(target_locales)} ({', '.join(target_locales[:3])}{'...' if len(target_locales) > 3 else ''})")
    print(f"  • Fields: {len(selected_fields)} ({', '.join(selected_fields)})")
    print(f"  • AI Provider: {selected_provider}")

    # Confirm
    ans = ui.confirm("Proceed with updates?", True)
    if ans is None:
        raw = input("Proceed? (Y/n): ").strip().lower()
        ans = raw in ("", "y", "yes")
    if not ans:
        print_info("Update cancelled")
        return True

    print_info(f"Starting updates for {len(target_locales)} languages across {len(selected_versions)} platform(s)...")
    def _task(loc: str):
        language_name = APP_STORE_LOCALES.get(loc, loc)
        translated = {}
        for field in selected_fields:
            field_name, source_content = field_mapping[field]
            if not source_content:
                continue
            is_keywords = field == "keywords"
            max_length = get_field_limit(field.replace("_", ""))
            out = provider.translate(source_content, language_name, max_length=max_length, is_keywords=is_keywords, seed=seed, refinement=refine_phrase)
            if is_keywords:
                out = truncate_keywords(out.strip())
            translated[field] = out
        time.sleep(1)
        return translated

    results, errs = parallel_map_locales(target_locales, _task, progress_action="Updated", pacing_seconds=0.0)

    # Warn on empty translations per locale
    for loc in target_locales:
        language_name = APP_STORE_LOCALES.get(loc, loc)
        data = results.get(loc) or {}
        has_any = any((v or "").strip() for v in data.values() if isinstance(v, str))
        if not has_any:
            print_warning(f"Empty translation for {language_name} [{loc}]")

    # Apply translations per platform
    for target_locale, translated in results.items():
        language_name = APP_STORE_LOCALES.get(target_locale, target_locale)
        for plat, ver in selected_versions.items():
            locs = asc.get_app_store_version_localizations(ver["id"]).get("data", [])
            loc_id = None
            for l in locs:
                if l["attributes"]["locale"] == target_locale:
                    loc_id = l["id"]
                    break
            if not loc_id:
                print_warning(f"  Locale {language_name} not found for platform {plat}; skipping")
                continue
            asc.update_app_store_version_localization(
                localization_id=loc_id,
                description=translated.get("description"),
                keywords=translated.get("keywords"),
                promotional_text=translated.get("promotional_text"),
                whats_new=translated.get("whats_new"),
            )

    input("\nPress Enter to continue...")
    return True
