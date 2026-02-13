"""Shared helper functions for promo workflow translation/apply steps."""

from typing import Dict, List

import requests

from utils import (
    APP_STORE_LOCALES,
    parallel_map_locales,
    print_info,
    print_success,
    print_warning,
)


def generate_promotional_translations(
    provider,
    target_locales: List[str],
    source_text: str,
    limit: int,
    seed,
    refine_phrase: str,
) -> Dict[str, str]:
    """Generate promotional text translations for all selected locales."""

    def _task(loc: str) -> str:
        language = APP_STORE_LOCALES.get(loc, loc)
        txt = provider.translate(
            text=source_text,
            target_language=language,
            max_length=limit,
            is_keywords=False,
            seed=seed,
            refinement=refine_phrase,
        )
        txt = (txt or "").strip()
        if len(txt) > limit:
            txt = txt[:limit]
        return txt

    translations, _errs = parallel_map_locales(
        target_locales,
        _task,
        progress_action="Translated",
        pacing_seconds=1.0,
    )
    return translations


def preview_promotional_translations(target_locales: List[str], translations: Dict[str, str]) -> None:
    """Print a preview of translated promotional text for each locale."""

    print_info("Preview generated promotional text:")
    for loc in target_locales:
        language = APP_STORE_LOCALES.get(loc, loc)
        print("-" * 60)
        print(f"{language} [{loc}]")
        print("-" * 60)
        txt = translations.get(loc, "")
        print(txt)
        if not (txt or "").strip():
            print_warning(f"Empty translation for {language} [{loc}]")
        print()


def edit_promotional_translations(
    ui,
    target_locales: List[str],
    translations: Dict[str, str],
    limit: int,
) -> None:
    """Allow manual edits for one or more translated locales."""

    if ui.available():
        choices = [
            {"name": f"{APP_STORE_LOCALES.get(loc, loc)} [{loc}]", "value": loc}
            for loc in target_locales
        ]
        to_edit = ui.checkbox("Select locales to edit", choices, add_back=True)
        if not to_edit:
            return
        editable_locales = to_edit
    else:
        raw = input("Enter locales to edit (comma-separated) or Enter to skip: ").strip()
        if not raw:
            return
        editable_locales = [s.strip() for s in raw.split(",") if s.strip() in target_locales]

    for loc in editable_locales:
        language = APP_STORE_LOCALES.get(loc, loc)
        edited = ui.prompt_multiline(
            f"Edit promotional text for {language} (END with 'EOF'):",
            initial=translations.get(loc, ""),
        )
        if edited is None:
            continue
        edited = edited.strip()
        if len(edited) > limit:
            edited = edited[:limit]
        translations[loc] = edited


def apply_promotional_updates(
    asc,
    per_version_locales: Dict[str, Dict[str, dict]],
    selected_versions: Dict[str, dict],
    plat_label: Dict[str, str],
    base_locale: str,
    base_text: str,
    target_locales: List[str],
    translations: Dict[str, str],
) -> None:
    """Apply base and translated promotional text updates per platform."""

    for plat, locale_map in per_version_locales.items():
        if plat not in selected_versions:
            continue
        plat_name = plat_label.get(plat, plat)
        apply_locales = [loc for loc in target_locales if loc in locale_map]
        total_to_update = len(apply_locales) + (1 if base_locale in locale_map else 0)
        if total_to_update == 0:
            continue

        print_info(
            f"Applying to {plat_name} ({total_to_update} locale{'s' if total_to_update != 1 else ''})..."
        )

        success = 0
        if base_locale in locale_map:
            try:
                asc.update_app_store_version_localization(
                    localization_id=locale_map[base_locale]["id"],
                    promotional_text=base_text,
                )
                print_success(
                    f"  Base locale {APP_STORE_LOCALES.get(base_locale, base_locale)} updated"
                )
                success += 1
            except requests.exceptions.RequestException as exc:
                print_warning(f"  Could not update base locale: {str(exc)}")

        if apply_locales:

            def _apply(loc: str) -> bool:
                asc.update_app_store_version_localization(
                    localization_id=locale_map[loc]["id"],
                    promotional_text=translations.get(loc, ""),
                )
                return True

            updated, errors = parallel_map_locales(
                apply_locales,
                _apply,
                progress_action=f"Updating {plat_name}",
                pacing_seconds=0.0,
            )
            success += len(updated)
            if errors:
                print()

        print_success(
            f"{plat_name}: {success}/{total_to_update} locale{'s' if total_to_update != 1 else ''} updated"
        )


def verify_promotional_updates(
    asc,
    per_version_locales: Dict[str, Dict[str, dict]],
    selected_versions: Dict[str, dict],
    base_locale: str,
    base_text: str,
    target_locales: List[str],
    translations: Dict[str, str],
) -> int:
    """Return count of locales whose readback differs from expected text."""

    verify_failures = 0
    expected_base = base_text.strip()
    for plat, locale_map in per_version_locales.items():
        if plat not in selected_versions:
            continue
        if base_locale in locale_map:
            data = asc.get_app_store_version_localization(locale_map[base_locale]["id"]) or {}
            promo = (data.get("data", {}).get("attributes", {}).get("promotionalText") or "").strip()
            if promo != expected_base:
                verify_failures += 1
        for loc in target_locales:
            if loc not in locale_map:
                continue
            data = asc.get_app_store_version_localization(locale_map[loc]["id"]) or {}
            promo = (data.get("data", {}).get("attributes", {}).get("promotionalText") or "").strip()
            expected = (translations.get(loc, "") or "").strip()
            if promo != expected:
                verify_failures += 1

    return verify_failures
