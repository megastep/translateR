"""
Release Mode workflow: create and translate What's New notes, multi-platform.
"""

from typing import Dict, List, Optional
import sys
import time
import random

from utils import APP_STORE_LOCALES, get_field_limit, format_progress, print_info, print_warning, print_success, print_error, parallel_map_locales, show_provider_and_source, build_refinement_template, parse_refinement_template


def select_platform_versions(ui, asc_client, app_id: str):
    versions_resp = asc_client._request("GET", f"apps/{app_id}/appStoreVersions")
    versions = versions_resp.get("data", [])
    if not versions:
        print_error("No App Store versions found for this app")
        return None, None, None

    latest_by_platform: Dict[str, dict] = {}
    for v in versions:
        attrs = v.get("attributes", {})
        plat = attrs.get("platform", "UNKNOWN")
        if plat not in latest_by_platform:
            latest_by_platform[plat] = v

    plat_label = {"IOS": "iOS", "MAC_OS": "macOS", "TV_OS": "tvOS", "VISION_OS": "visionOS", "UNKNOWN": "Unknown"}

    selected_versions: Dict[str, dict] = {}
    if ui.available():
        choices = []
        for plat, v in latest_by_platform.items():
            attrs = v.get("attributes", {})
            name = f"{plat_label.get(plat, plat)} v{attrs.get('versionString', 'Unknown')} ({attrs.get('appStoreState', 'Unknown')})"
            choices.append({"name": name, "value": plat, "enabled": True})
        picked = ui.checkbox("Select platforms to update (Space to toggle, Enter to confirm)", choices, add_back=True)
        if not picked:
            print_info("Cancelled")
            return None, None, None
        for plat in picked:
            selected_versions[plat] = latest_by_platform[plat]
    else:
        print("Available platforms:")
        plats = list(latest_by_platform.keys())
        for i, plat in enumerate(plats, 1):
            attrs = latest_by_platform[plat].get("attributes", {})
            print(f"{i}. {plat_label.get(plat, plat)} v{attrs.get('versionString', 'Unknown')} ({attrs.get('appStoreState', 'Unknown')})")
        raw = input("Select platforms (comma numbers) or Enter for all, 'b' to back: ").strip().lower()
        if raw == 'b':
            print_info("Cancelled")
            return None, None, None
        if not raw:
            picked_idx = list(range(1, len(plats) + 1))
        else:
            try:
                picked_idx = [int(x.strip()) for x in raw.split(',')]
            except ValueError:
                print_error("Invalid selection")
                return None, None, None
        for idx in picked_idx:
            if 1 <= idx <= len(plats):
                plat = plats[idx - 1]
                selected_versions[plat] = latest_by_platform[plat]

    return selected_versions, latest_by_platform, plat_label


def detect_base_language(localizations: List[Dict]) -> Optional[str]:
    from utils import detect_base_language as _dbl
    return _dbl(localizations)


def run(cli) -> bool:
    """Execute Release Mode.

    cli must have: asc_client, ai_manager, ui
    """
    ui = cli.ui
    asc = cli.asc_client
    providers = cli.ai_manager

    print_info("Release Mode - Create and translate release notes")
    print()

    # Pick app
    app_id = ui.prompt_app_id(asc)
    if app_id is None:
        print_info("Cancelled")
        return True

    # Select platforms
    selected_versions, latest_by_platform, plat_label = select_platform_versions(ui, asc, app_id)
    if not selected_versions:
        return True
    print_success("Selected platforms: " + ", ".join(plat_label.get(p, p) for p in selected_versions.keys()))

    # Build per-version locale maps and detect base
    per_version_locales: Dict[str, Dict[str, dict]] = {}
    base_locale = None
    base_whats_new = ""
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
                base_whats_new = (locale_map.get(base_locale, {}).get("whatsNew") or "").strip()

    if not base_locale:
        print_error("Could not detect base language from selected platforms")
        return True
    print_info(f"Base language: {base_locale} ({APP_STORE_LOCALES.get(base_locale, 'Unknown')})")

    # Source notes + refinement via inline template
    default_refine = (getattr(cli, 'config', None).get_prompt_refinement() if getattr(cli, 'config', None) else "") or ""
    refine_phrase = default_refine
    source_notes = base_whats_new
    if base_whats_new:
        choice = None
        if ui.available():
            choice = ui.select(
                "Source release notes",
                [
                    {"name": "Use base language release notes", "value": "use"},
                    {"name": "Edit base release notes", "value": "edit"},
                    {"name": "Enter custom source notes", "value": "custom"},
                ], add_back=True,
            )
            if choice is None:
                print_info("Cancelled")
                return True
        else:
            raw = input("Use base release notes as source? (Y/n/e=edit,c=custom): ").strip().lower()
            if raw in ("", "y", "yes"): choice = "use"
            elif raw in ("n", "no"): choice = "custom"
            elif raw in ("e",): choice = "edit"
            elif raw in ("c",): choice = "custom"
            else: choice = "use"
        if choice == "edit":
            initial = build_refinement_template(refine_phrase or default_refine, base_whats_new)
            edited = ui.prompt_multiline("Edit base release notes (END with 'EOF'):", initial=initial)
            if not edited:
                print_warning("No content entered")
                return True
            clean, parsed_refine = parse_refinement_template(edited, fallback_default=refine_phrase or default_refine)
            if not clean:
                print_warning("No content entered")
                return True
            source_notes = clean
            refine_phrase = parsed_refine
        elif choice == "custom":
            initial = build_refinement_template(refine_phrase or default_refine, "")
            custom = ui.prompt_multiline("Enter release notes to translate (END with 'EOF'):", initial=initial)
            if not custom:
                print_warning("No content entered")
                return True
            clean, parsed_refine = parse_refinement_template(custom, fallback_default=refine_phrase or default_refine)
            if not clean:
                print_warning("No content entered")
                return True
            source_notes = clean
            refine_phrase = parsed_refine
        else:
            source_notes = base_whats_new
    else:
        print_warning("Base language has no release notes. Please enter source notes.")
        initial = build_refinement_template(refine_phrase or default_refine, "")
        custom = ui.prompt_multiline("Enter release notes to translate (END with 'EOF'):", initial=initial)
        if not custom:
            print_warning("No source text entered")
            return True
        clean, parsed_refine = parse_refinement_template(custom, fallback_default=refine_phrase or default_refine)
        if not clean:
            print_warning("No source text entered")
            return True
        source_notes = clean
        refine_phrase = parsed_refine

    # Determine empty locales
    empty_by_platform: Dict[str, List[str]] = {}
    union_empty: List[str] = []
    for plat, locale_map in per_version_locales.items():
        empties: List[str] = []
        for locale, data in locale_map.items():
            if locale == base_locale:
                continue
            wn = (data.get("whatsNew") or "").strip()
            if not wn:
                empties.append(locale)
                if locale not in union_empty:
                    union_empty.append(locale)
        empty_by_platform[plat] = empties
    if not union_empty:
        print_info("All selected platforms already have release notes for this version")
        return True

    # Select target locales
    if ui.available():
        choices = [{"name": f"{loc} ({APP_STORE_LOCALES.get(loc, 'Unknown')})", "value": loc, "enabled": True} for loc in union_empty]
        selected = ui.checkbox("Select locales to fill (Space to toggle, Enter to confirm)", choices, add_back=True)
        if not selected:
            selected = union_empty
        target_locales = selected
    else:
        print("Locales missing release notes:")
        for i, loc in enumerate(union_empty, 1):
            print(f"{i:2d}. {loc} ({APP_STORE_LOCALES.get(loc, 'Unknown')})")
        raw = input("Enter locales (comma-separated) or 'b' to go back (blank = all): ").strip()
        if raw.lower() == 'b':
            print_info("Cancelled")
            return True
        target_locales = union_empty if not raw else [s.strip() for s in raw.split(',') if s.strip() in union_empty]
        if not target_locales:
            print_warning("No valid locales selected")
            return True

    # Provider
    provs = providers.list_providers()
    if not provs:
        print_error("No AI providers configured. Please run setup.")
        return True
    selected_provider = None
    if len(provs) == 1:
        selected_provider = provs[0]
        print_info(f"Using AI provider: {selected_provider}")
    else:
        # Offer to use configured default provider if set
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
                choices = [{"name": p + ("  (default)" if p == default_provider else ""), "value": p} for p in provs]
                selected_provider = ui.select("Select AI provider", choices, add_back=True)
            if not selected_provider:
                print("Available AI providers:")
                for i, p in enumerate(provs, 1):
                    star = " *" if p == default_provider else ""
                    print(f"{i}. {p}{star}")
                raw = input("Select provider (number) or 'b' to go back (Enter = default): ").strip().lower()
                if raw == 'b':
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

    # Pick a per-run seed reused across locales
    seed = random.randint(1, 2**31 - 1)

    # Translate + review loop
    limit = get_field_limit("whats_new") or 4000
    translations: Dict[str, str] = {}
    while True:
        # Show provider/model and source preview
        show_provider_and_source(provider, selected_provider, base_locale, source_notes, title="Source release notes to translate", seed=seed)

        # Parallel translate all
        def _task(loc: str) -> str:
            language = APP_STORE_LOCALES.get(loc, loc)
            txt = provider.translate(text=source_notes, target_language=language, max_length=limit, is_keywords=False, seed=seed, refinement=refine_phrase)
            txt = (txt or "").strip()
            if len(txt) > limit:
                txt = txt[:limit]
            return txt

        translations, _errs = parallel_map_locales(target_locales, _task, progress_action="Translated", pacing_seconds=1.0)

        # Preview
        print_info("Preview generated release notes:")
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

        # Next step selection (apply / edit locales / re-enter source / cancel)
        do_edit = False
        if ui.available():
            choice = ui.select(
                "Next step",
                [
                    {"name": "Apply all now", "value": "apply"},
                    {"name": "Edit selected locales", "value": "edit"},
                    {"name": "Re-enter source notes and re-translate", "value": "reenter"},
                    {"name": "Cancel", "value": "cancel"},
                ], add_back=True,
            )
            if choice is None or choice == "cancel":
                print_info("Cancelled")
                return True
            if choice == "reenter":
                initial = build_refinement_template(refine_phrase or default_refine, source_notes)
                new_notes = ui.prompt_multiline("Enter new source release notes (END with 'EOF'):", initial=initial)
                if not new_notes:
                    print_warning("No content entered; keeping previous source notes.")
                else:
                    clean, parsed_refine = parse_refinement_template(new_notes, fallback_default=refine_phrase or default_refine)
                    if clean:
                        source_notes = clean
                        refine_phrase = parsed_refine
                # Loop to re-translate
                continue
            do_edit = (choice == "edit")
        else:
            raw = input("Apply all (a) / Edit (e) / Re-enter source (r) / Cancel (c): ").strip().lower()
            if raw == 'c':
                print_info("Cancelled")
                return True
            if raw == 'r':
                initial = build_refinement_template(refine_phrase or default_refine, source_notes)
                new_notes = ui.prompt_multiline("Enter new source release notes (END with 'EOF'):", initial=initial)
                if not new_notes:
                    print_warning("No content entered; keeping previous source notes.")
                else:
                    clean, parsed_refine = parse_refinement_template(new_notes, fallback_default=refine_phrase or default_refine)
                    if clean:
                        source_notes = clean
                        refine_phrase = parsed_refine
                # Loop to re-translate
                continue
            do_edit = (raw == 'e')

        # Optional per-locale edits, then break to confirmation/apply
        if do_edit:
            if ui.available():
                choices = [{"name": f"{APP_STORE_LOCALES.get(loc, loc)} [{loc}]", "value": loc} for loc in target_locales]
                to_edit = ui.checkbox("Select locales to edit", choices, add_back=True)
                if to_edit:
                    for loc in to_edit:
                        language = APP_STORE_LOCALES.get(loc, loc)
                        edited = ui.prompt_multiline(f"Edit release notes for {language} (END with 'EOF'):", initial=translations.get(loc, ""))
                        if edited is not None:
                            edited = edited.strip()
                            if len(edited) > limit:
                                edited = edited[:limit]
                            translations[loc] = edited
            else:
                raw = input("Enter locales to edit (comma-separated) or Enter to skip: ").strip()
                if raw:
                    for loc in [s.strip() for s in raw.split(',') if s.strip() in target_locales]:
                        language = APP_STORE_LOCALES.get(loc, loc)
                        edited = ui.prompt_multiline(f"Edit release notes for {language} (END with 'EOF'):", initial=translations.get(loc, ""))
                        if edited is not None:
                            edited = edited.strip()
                            if len(edited) > limit:
                                edited = edited[:limit]
                            translations[loc] = edited

        # Break out to confirmation/apply
        break

    # Confirm
    proceed = ui.confirm("Apply release notes to all listed locales?", True)
    if proceed is None:
        ans = input("Proceed to apply? (Y/n): ").strip().lower()
        proceed = ans in ("", "y", "yes")
    if not proceed:
        print_info("Cancelled")
        return True

    # Apply per platform
    print()
    for plat, locale_map in per_version_locales.items():
        if plat not in selected_versions:
            continue
        plat_name = plat_label.get(plat, plat)
        print_info(f"Applying to {plat_name} ({len(target_locales)} locales)...")

        # Update base locale if empty
        base_empty_here = not (locale_map.get(base_locale, {}).get("whatsNew") or "").strip()
        if base_empty_here:
            try:
                asc.update_app_store_version_localization(localization_id=locale_map[base_locale]["id"], whats_new=source_notes[:limit])
                print_success(f"  Base locale {APP_STORE_LOCALES.get(base_locale, base_locale)} updated")
            except Exception as e:
                print_warning(f"  Could not update base locale: {str(e)}")

        success = 0
        total = len(target_locales)
        last_len = 0
        for i, loc in enumerate(target_locales, 1):
            if loc not in empty_by_platform.get(plat, []):
                continue
            language = APP_STORE_LOCALES.get(loc, loc)
            try:
                line = format_progress(i, total, f"Updating {language} ({plat_name})")
                pad = max(0, last_len - len(line))
                sys.stdout.write("\r" + line + (" " * pad))
                sys.stdout.flush()
                last_len = len(line)
            except Exception:
                print(format_progress(i, total, f"Updating {language} ({plat_name})"))
            try:
                asc.update_app_store_version_localization(localization_id=locale_map[loc]["id"], whats_new=translations.get(loc, ""))
                success += 1
                time.sleep(1)
            except Exception as e:
                print_error(f"  ❌ Failed to update {language} ({plat_name}): {str(e)}")
                continue
        try:
            sys.stdout.write("\r" + (" " * last_len) + "\r")
            sys.stdout.flush()
        except Exception:
            pass
        print()
        print_success(f"{plat_name}: {success}/{len(empty_by_platform.get(plat, []))} locales updated")

    # Verify (best effort)
    try:
        verify_failures = 0
        for plat, locale_map in per_version_locales.items():
            if plat not in selected_versions:
                continue
            for loc in empty_by_platform.get(plat, []):
                data = asc.get_app_store_version_localization(locale_map[loc]["id"]) or {}
                wn = (data.get("data", {}).get("attributes", {}).get("whatsNew") or "").strip()
                if not wn:
                    verify_failures += 1
        if verify_failures:
            print_warning(f"Release notes may not have applied to {verify_failures} locale(s). Ensure you are editing the correct version state in App Store Connect.")
    except Exception:
        pass

    input("\nPress Enter to continue...")
    return True
