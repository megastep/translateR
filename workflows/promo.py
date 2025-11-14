"""Promo Mode workflow: update promotional text across locales."""

from typing import Dict, List, Optional

from utils import (
    APP_STORE_LOCALES,
    detect_base_language,
    get_field_limit,
    print_error,
    print_info,
    print_success,
    print_warning,
    parallel_map_locales,
    show_provider_and_source,
    build_refinement_template,
    parse_refinement_template,
)
from workflows.release import select_platform_versions


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
    provs = providers.list_providers()
    default_provider = (
        getattr(cli, "config", None).get_default_ai_provider()
        if getattr(cli, "config", None)
        else None
    )
    selected_provider: Optional[str] = None
    provider = None

    while True:
        if provider is None and target_locales:
            if not provs:
                print_error("No AI providers configured. Please run setup.")
                return True
            if len(provs) == 1:
                selected_provider = provs[0]
                print_info(f"Using AI provider: {selected_provider}")
            else:
                if default_provider and default_provider in provs:
                    use_default = ui.confirm(
                        f"Use default AI provider: {default_provider}?", True
                    )
                    if use_default is None:
                        raw = input(
                            f"Use default provider '{default_provider}'? (Y/n): "
                        ).strip().lower()
                        use_default = raw in ("", "y", "yes")
                    if use_default:
                        selected_provider = default_provider
                if not selected_provider:
                    if ui.available():
                        choices = [
                            {
                                "name": p + ("  (default)" if p == default_provider else ""),
                                "value": p,
                            }
                            for p in provs
                        ]
                        selected_provider = ui.select(
                            "Select AI provider", choices, add_back=True
                        )
                    if not selected_provider:
                        print("Available AI providers:")
                        for i, p in enumerate(provs, 1):
                            star = " *" if p == default_provider else ""
                            print(f"{i}. {p}{star}")
                        raw = input(
                            "Select provider (number) or 'b' to go back (Enter = default): "
                        ).strip().lower()
                        if raw == "b":
                            print_info("Cancelled")
                            return True
                        if not raw and default_provider and default_provider in provs:
                            selected_provider = default_provider
                        else:
                            try:
                                idx = int(raw)
                                if 1 <= idx <= len(provs):
                                    selected_provider = provs[idx - 1]
                                else:
                                    print_error("Invalid choice")
                                    return True
                            except ValueError:
                                print_error("Please enter a number")
                                return True
            provider = providers.get_provider(selected_provider)

        if target_locales:
            show_provider_and_source(
                provider,
                selected_provider,
                base_locale,
                source_text,
                title="Source promotional text",
                seed=seed,
            )

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
        else:
            translations = {}

        if target_locales:
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
            elif choice == "apply":
                pass
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
            if ui.available():
                choices = [
                    {"name": f"{APP_STORE_LOCALES.get(loc, loc)} [{loc}]", "value": loc}
                    for loc in target_locales
                ]
                to_edit = ui.checkbox("Select locales to edit", choices, add_back=True)
                if to_edit:
                    for loc in to_edit:
                        language = APP_STORE_LOCALES.get(loc, loc)
                        edited = ui.prompt_multiline(
                            f"Edit promotional text for {language} (END with 'EOF'):",
                            initial=translations.get(loc, ""),
                        )
                        if edited is not None:
                            edited = edited.strip()
                            if len(edited) > limit:
                                edited = edited[:limit]
                            translations[loc] = edited
            else:
                raw = input("Enter locales to edit (comma-separated) or Enter to skip: ").strip()
                if raw:
                    for loc in [s.strip() for s in raw.split(",") if s.strip() in target_locales]:
                        language = APP_STORE_LOCALES.get(loc, loc)
                        edited = ui.prompt_multiline(
                            f"Edit promotional text for {language} (END with 'EOF'):",
                            initial=translations.get(loc, ""),
                        )
                        if edited is not None:
                            edited = edited.strip()
                            if len(edited) > limit:
                                edited = edited[:limit]
                            translations[loc] = edited

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
            except Exception as e:
                print_warning(f"  Could not update base locale: {str(e)}")

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

    try:
        verify_failures = 0
        expected_base = base_text.strip()
        for plat, locale_map in per_version_locales.items():
            if plat not in selected_versions:
                continue
            if base_locale in locale_map:
                data = asc.get_app_store_version_localization(locale_map[base_locale]["id"]) or {}
                promo = (
                    data.get("data", {}).get("attributes", {}).get("promotionalText")
                    or ""
                ).strip()
                if promo != expected_base:
                    verify_failures += 1
            for loc in target_locales:
                if loc not in locale_map:
                    continue
                data = asc.get_app_store_version_localization(locale_map[loc]["id"]) or {}
                promo = (
                    data.get("data", {}).get("attributes", {}).get("promotionalText")
                    or ""
                ).strip()
                expected = (translations.get(loc, "") or "").strip()
                if promo != expected:
                    verify_failures += 1
        if verify_failures:
            print_warning(
                f"Promotional text may not have applied to {verify_failures} locale(s). Please verify in App Store Connect."
            )
    except Exception:
        pass

    input("\nPress Enter to continue...")
    return True
