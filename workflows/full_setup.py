"""
Full Setup Mode: translate missing languages across selected platforms.
"""

from typing import Dict
import time

from utils import (
    APP_STORE_LOCALES, detect_base_language, get_field_limit, truncate_keywords,
    print_info, print_warning, print_success, print_error, format_progress,
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

    print_info(f"Starting full setup for {len(target_locales)} languages across {len(selected)} platform(s)...")
    for i, target_locale in enumerate(target_locales, 1):
        language_name = APP_STORE_LOCALES[target_locale]
        print()
        print(format_progress(i, len(target_locales), f"Setting up {language_name}"))
        try:
            translated = {}
            if base_attrs.get("description"):
                translated["description"] = provider.translate(base_attrs["description"], language_name, max_length=get_field_limit("description"))
            if base_attrs.get("keywords"):
                kw = provider.translate(base_attrs["keywords"], language_name, max_length=get_field_limit("keywords"), is_keywords=True)
                translated["keywords"] = truncate_keywords(kw)
            if base_attrs.get("promotionalText"):
                translated["promotionalText"] = provider.translate(base_attrs["promotionalText"], language_name, max_length=get_field_limit("promotional_text"))
            if base_attrs.get("whatsNew"):
                translated["whatsNew"] = provider.translate(base_attrs["whatsNew"], language_name, max_length=get_field_limit("whats_new"))

            for plat, ver in selected.items():
                asc.create_app_store_version_localization(
                    version_id=ver["id"],
                    locale=target_locale,
                    description=translated.get("description", ""),
                    keywords=translated.get("keywords"),
                    promotional_text=translated.get("promotionalText"),
                    whats_new=translated.get("whatsNew"),
                )
            time.sleep(2)
        except Exception as e:
            print_error(f"  ❌ Failed to setup {language_name}: {str(e)}")
            continue

    print_success("✅ Full setup completed!")
    input("\nPress Enter to continue...")
    return True

