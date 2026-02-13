"""Promo Mode workflow: update promotional text across locales."""

from typing import Dict, List, Optional

from utils import (
    APP_STORE_LOCALES,
    detect_base_language,
    get_field_limit,
    print_error,
    print_info,
    print_warning,
    show_provider_and_source,
    build_refinement_template,
    parse_refinement_template,
)
from workflows.helpers import pick_provider, select_platform_versions
from workflows.promo_helpers import (
    apply_promotional_updates,
    edit_promotional_translations,
    generate_promotional_translations,
    preview_promotional_translations,
    verify_promotional_updates,
)


def _prompt_source_promotional_text(ui, base_text: str, default_refine: str, refine_phrase: str) -> (str, str):
    """Handle source promotional text selection/edit prompt."""

    base_text = (base_text or "").strip()
    while True:
        if base_text:
            if ui.available():
                choice = ui.select(
                    "Source promotional text",
                    [
                        {"name": "Use base promotional text", "value": "use"},
                        {"name": "Edit base promotional text", "value": "edit"},
                        {"name": "Enter new promotional text", "value": "custom"},
                    ],
                    add_back=True,
                )
                if choice is None:
                    print_info("Cancelled")
                    return "", refine_phrase
            else:
                raw = input("Use base promotional text? (Y/n/e=edit,c=custom): ").strip().lower()
                if raw in ("", "y", "yes"):
                    choice = "use"
                elif raw == "e":
                    choice = "edit"
                elif raw in ("n", "no", "c"):
                    choice = "custom"
                else:
                    choice = "use"
            if choice == "use":
                return base_text, refine_phrase or default_refine
            if choice == "edit":
                initial = build_refinement_template(refine_phrase or default_refine, base_text)
            else:
                initial = build_refinement_template(refine_phrase or default_refine, "")
        else:
            choice = "custom"
            initial = build_refinement_template(refine_phrase or default_refine, "")

        edited = ui.prompt_multiline("Enter promotional text to translate (END with 'EOF'):", initial=initial)
        if not edited:
            print_warning("No content entered")
            continue
        clean, parsed_refine = parse_refinement_template(
            edited, fallback_default=refine_phrase or default_refine
        )
        clean = clean.strip()
        if not clean:
            print_warning("No content entered")
            continue
        return clean, parsed_refine


def run(cli) -> bool:
    """Execute Promo Mode workflow."""

    ui = cli.ui
    asc = cli.asc_client
    providers = cli.ai_manager

    print_info("Promo Mode - Update promotional text across locales")
    print()

    app_id = ui.prompt_app_id(asc)
    if app_id is None:
        print_info("Cancelled")
        return True

    selected_versions, _latest_by_platform, plat_label = select_platform_versions(ui, asc, app_id)
    if not selected_versions:
        return True
    print_success(
        "Selected platforms: "
        + ", ".join(plat_label.get(p, p) for p in selected_versions.keys())
    )

    per_version_locales: Dict[str, Dict[str, dict]] = {}
    base_locale: Optional[str] = None
    base_promotional = ""
    for plat, ver in selected_versions.items():
        vid = ver.get("id")
        locs_resp = asc.get_app_store_version_localizations(vid)
        locs = locs_resp.get("data", [])
        locale_map: Dict[str, dict] = {}
        for loc in locs:
            attrs = loc.get("attributes", {})
            locale_map[attrs.get("locale")] = {"id": loc.get("id"), **attrs}
        per_version_locales[plat] = locale_map
        if base_locale is None:
            detected = detect_base_language(locs)
            if detected:
                base_locale = detected
                base_promotional = (locale_map.get(detected, {}).get("promotionalText") or "").strip()

    if not base_locale:
        print_error("Could not detect base language from selected platforms")
        return True
    print_info(f"Base language: {base_locale} ({APP_STORE_LOCALES.get(base_locale, 'Unknown')})")

    default_refine = (
        getattr(cli, "config", None).get_prompt_refinement()
        if getattr(cli, "config", None)
        else ""
    ) or ""
    refine_phrase = default_refine
    source_text = base_promotional or ""

    source_text, refine_phrase = _prompt_source_promotional_text(
        ui, source_text, default_refine, refine_phrase
    )
    if not source_text:
        print_warning("No promotional text provided")
        return True

    available_locales = sorted(
        {loc for locale_map in per_version_locales.values() for loc in locale_map.keys() if loc and loc != base_locale}
    )
    if not available_locales:
        print_warning("No additional locales found; only base locale will be updated.")
        target_locales: List[str] = []
    else:
        if ui.available():
            choices = [
                {"name": f"{APP_STORE_LOCALES.get(loc, loc)} [{loc}]", "value": loc, "enabled": True}
                for loc in available_locales
            ]
            selected = ui.checkbox(
                "Select locales to update (Space to toggle, Enter for all)", choices, add_back=True
            )
            target_locales = selected or available_locales
        else:
            print("Locales that will be updated:")
            for i, loc in enumerate(available_locales, 1):
                print(f"{i:2d}. {loc} ({APP_STORE_LOCALES.get(loc, 'Unknown')})")
            raw = input("Enter locales (comma-separated, blank = all, 'b' to cancel): ").strip()
            if raw.lower() == "b":
                print_info("Cancelled")
                return True
            target_locales = (
                available_locales
                if not raw
                else [s.strip() for s in raw.split(",") if s.strip() in available_locales]
            )
            if not target_locales:
                print_warning("No valid locales selected")
                return True

    seed = getattr(cli, "session_seed", None)
    limit = get_field_limit("promotional_text") or 170
    translations: Dict[str, str] = {}
    selected_provider: Optional[str] = None
    provider = None

    while True:
        if provider is None and target_locales:
            provider, selected_provider = pick_provider(cli)
            if not provider:
                return True

        if target_locales:
            show_provider_and_source(
                provider,
                selected_provider,
                base_locale,
                source_text,
                title="Source promotional text",
                seed=seed,
            )
            translations = generate_promotional_translations(
                provider=provider,
                target_locales=target_locales,
                source_text=source_text,
                limit=limit,
                seed=seed,
                refine_phrase=refine_phrase,
            )
        else:
            translations = {}

        if target_locales:
            preview_promotional_translations(target_locales, translations)

        do_edit = False
        if ui.available():
            choice = ui.select(
                "Next step",
                [
                    {"name": "Apply all now", "value": "apply"},
                    {"name": "Edit selected locales", "value": "edit"},
                    {"name": "Re-enter source promotional text and re-translate", "value": "reenter"},
                    {"name": "Cancel", "value": "cancel"},
                ],
                add_back=True,
            )
            if choice is None or choice == "cancel":
                print_info("Cancelled")
                return True
            if choice == "reenter":
                initial = build_refinement_template(refine_phrase or default_refine, source_text)
                new_text = ui.prompt_multiline(
                    "Enter new source promotional text (END with 'EOF'):",
                    initial=initial,
                )
                if not new_text:
                    print_warning("No content entered; keeping previous source text.")
                else:
                    clean, parsed_refine = parse_refinement_template(
                        new_text, fallback_default=refine_phrase or default_refine
                    )
                    if clean:
                        source_text = clean
                        refine_phrase = parsed_refine
                continue
            if choice == "edit":
                do_edit = True
        else:
            raw = input("Apply (a), edit (e), re-enter source (r), or cancel (c)? ").strip().lower()
            if raw in ("c", "cancel"):
                print_info("Cancelled")
                return True
            if raw in ("r", "reenter"):
                initial = build_refinement_template(refine_phrase or default_refine, source_text)
                new_text = ui.prompt_multiline(
                    "Enter new source promotional text (END with 'EOF'):",
                    initial=initial,
                )
                if new_text:
                    clean, parsed_refine = parse_refinement_template(
                        new_text, fallback_default=refine_phrase or default_refine
                    )
                    if clean:
                        source_text = clean
                        refine_phrase = parsed_refine
                continue
            do_edit = raw == "e"

        if do_edit and target_locales:
            edit_promotional_translations(ui, target_locales, translations, limit)

        break

    proceed = ui.confirm("Apply promotional text to selected locales?", True)
    if proceed is None:
        ans = input("Proceed to apply? (Y/n): ").strip().lower()
        proceed = ans in ("", "y", "yes")
    if not proceed:
        print_info("Cancelled")
        return True

    print()
    base_text = source_text[:limit]
    apply_promotional_updates(
        asc=asc,
        per_version_locales=per_version_locales,
        selected_versions=selected_versions,
        plat_label=plat_label,
        base_locale=base_locale,
        base_text=base_text,
        target_locales=target_locales,
        translations=translations,
    )

    try:
        verify_failures = verify_promotional_updates(
            asc=asc,
            per_version_locales=per_version_locales,
            selected_versions=selected_versions,
            base_locale=base_locale,
            base_text=base_text,
            target_locales=target_locales,
            translations=translations,
        )
        if verify_failures:
            print_warning(
                f"Promotional text may not have applied to {verify_failures} locale(s). Please verify in App Store Connect."
            )
    except Exception:
        pass

    input("\nPress Enter to continue...")
    return True
