"""
Update Mode workflow with multi-platform handling.
"""

from typing import Dict
import time

from utils import (
    APP_STORE_LOCALES, detect_base_language, get_field_limit, truncate_keywords,
    print_info, print_warning, print_error, format_progress,
    parallel_map_locales, provider_model_info,
)
from workflows.helpers import choose_target_locales, pick_provider, select_platform_versions


def run(cli) -> bool:
    ui = cli.ui
    asc = cli.asc_client

    print_info("Update Mode - Update existing localizations with new content")
    print("Perfect for updating specific fields in existing languages (e.g., What's New)")
    print()

    app_id = ui.prompt_app_id(asc)
    if app_id is None:
        print_info("Cancelled")
        return True

    selected_versions, _, _ = select_platform_versions(ui, asc, app_id)
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

    # Choose languages to update (existing, missing, or both)
    existing_by_platform: Dict[str, set] = {}
    for plat, ver in selected_versions.items():
        locs = asc.get_app_store_version_localizations(ver["id"]).get("data", [])
        existing_by_platform[plat] = {l["attributes"]["locale"] for l in locs}
    union_existing = set().union(*existing_by_platform.values())
    existing_locales = [l for l in union_existing if l != base_locale]

    # Locale scope
    locale_scope = "existing"  # existing | missing | all
    if ui.available():
        picked = ui.select(
            "Which locales do you want to include?",
            [
                {"name": "Existing locales only (update)", "value": "existing"},
                {"name": "Missing locales only (create)", "value": "missing"},
                {"name": "All locales (existing + missing)", "value": "all"},
            ],
            add_back=True,
        )
        if not picked:
            print_info("Cancelled")
            return True
        locale_scope = picked
    else:
        raw = input("Locales to include: (e)xisting, (m)issing, (a)ll (Enter = existing): ").strip().lower()
        if raw in ("b", "back"):
            print_info("Cancelled")
            return True
        if raw in ("m", "missing"):
            locale_scope = "missing"
        elif raw in ("a", "all", "*"):
            locale_scope = "all"
        else:
            locale_scope = "existing"

    allow_create_missing = locale_scope in ("missing", "all")

    supported_minus_base = {k: v for k, v in APP_STORE_LOCALES.items() if k != base_locale}
    missing_union = [
        loc
        for loc in supported_minus_base.keys()
        if any(loc not in (existing_by_platform.get(plat) or set()) for plat in selected_versions.keys())
    ]

    if locale_scope == "existing":
        available_targets = {loc: APP_STORE_LOCALES.get(loc, loc) for loc in existing_locales}
        preferred = existing_locales
    elif locale_scope == "missing":
        available_targets = {loc: supported_minus_base[loc] for loc in missing_union if loc in supported_minus_base}
        preferred = missing_union
    else:
        available_targets = supported_minus_base
        preferred = existing_locales

    if not available_targets:
        print_warning("No locales available for that selection")
        return True

    target_locales = choose_target_locales(
        ui,
        available_targets,
        base_locale,
        preferred_locales=preferred,
        prompt="Select languages",
    )
    if not target_locales:
        print_warning("No languages selected")
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
        fields_to_translate = set(selected_fields)
        if allow_create_missing:
            # Creating a new App Store version localization requires a description attribute.
            fields_to_translate.add("description")
        for field in fields_to_translate:
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
                if not allow_create_missing:
                    print_warning(f"  Locale {language_name} not found for platform {plat}; skipping")
                    continue
                # Create missing localization (requires description)
                desc = (translated.get("description") or "").strip()
                if not desc:
                    # Fall back to base description if we couldn't translate for some reason.
                    desc = (base_data.get("description") or "").strip()
                if not desc:
                    print_warning(f"  Locale {language_name} missing description; cannot create for platform {plat}; skipping")
                    continue
                asc.create_app_store_version_localization(
                    version_id=ver["id"],
                    locale=target_locale,
                    description=desc,
                    keywords=translated.get("keywords"),
                    promotional_text=translated.get("promotional_text"),
                    whats_new=translated.get("whats_new"),
                )
                continue

            # Missing-only mode: don't modify already-existing locales.
            if locale_scope == "missing":
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
