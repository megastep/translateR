"""
Release Mode workflow: create and translate What's New notes, multi-platform.
"""

from typing import Dict, List, Optional, Tuple
import sys
import time
import textwrap

from release_presets import list_presets, ReleaseNotePreset

from utils import APP_STORE_LOCALES, get_field_limit, format_progress, print_info, print_warning, print_success, print_error, parallel_map_locales, show_provider_and_source, build_refinement_template, parse_refinement_template


def _preset_preview_text(preset: ReleaseNotePreset, base_locale: str) -> str:
    preview = preset.get_translation(base_locale).replace("\n", " ").strip()
    if not preview:
        preview = preset.get_translation("en-US").replace("\n", " ").strip()
    return textwrap.shorten(preview, width=60, placeholder="…") if preview else "(empty)"


def prompt_preset_selection(ui, presets: List[ReleaseNotePreset], base_locale: str, exclude_id: Optional[str] = None, allow_custom: bool = False) -> Tuple[Optional[ReleaseNotePreset], bool]:
    """Prompt user to choose a preset. Returns (preset, use_custom)."""
    filtered = [p for p in presets if p.preset_id != exclude_id]
    if not filtered and not allow_custom:
        return None, False

    base_label = f"{APP_STORE_LOCALES.get(base_locale, base_locale)} [{base_locale}]"

    if ui.available():
        choices = []
        for preset in filtered:
            preview = _preset_preview_text(preset, base_locale)
            label = f"{preset.name} — {preview} (base {base_label})"
            choices.append({"name": label, "value": preset.preset_id})
        if allow_custom:
            choices.append({"name": "Enter custom release notes instead", "value": "__custom__"})
        picked = ui.select("Select a preset", choices, add_back=True)
        if not picked:
            return None, False
        if picked == "__custom__":
            return None, True
        for preset in filtered:
            if preset.preset_id == picked:
                return preset, False
        return None, False

    # Fallback non-TUI prompt
    print("Available presets (base locale content is included):")
    for idx, preset in enumerate(filtered, 1):
        preview = _preset_preview_text(preset, base_locale)
        print(f"{idx}. {preset.name} — {preview} (base {base_label})")
    extra_hint = ""
    if allow_custom:
        extra_hint = " or '0' to enter custom release notes"
    raw = input(f"Select preset by number{extra_hint}, or press Enter to cancel: ").strip()
    if not raw:
        return None, False
    if allow_custom and raw == "0":
        return None, True
    try:
        idx = int(raw)
    except ValueError:
        print_error("Invalid selection")
        return None, False
    if 1 <= idx <= len(filtered):
        return filtered[idx - 1], False
    print_error("Invalid selection")
    return None, False


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
    available_presets = list_presets()
    selected_preset: Optional[ReleaseNotePreset] = None
    default_refine = (getattr(cli, 'config', None).get_prompt_refinement() if getattr(cli, 'config', None) else "") or ""
    refine_phrase = default_refine
    source_notes = base_whats_new or ""
    if base_whats_new:
        while True:
            choice = None
            if ui.available():
                options = [
                    {"name": "Use base language release notes", "value": "use"},
                    {"name": "Edit base release notes", "value": "edit"},
                    {"name": "Enter custom source notes", "value": "custom"},
                ]
                if available_presets:
                    options.insert(0, {"name": "Pick a release note preset", "value": "preset"})
                choice = ui.select("Source release notes", options, add_back=True)
                if choice is None:
                    print_info("Cancelled")
                    return True
            else:
                prompt = "Use base release notes as source? (Y/n/e=edit,c=custom"
                if available_presets:
                    prompt += ",p=preset"
                prompt += "): "
                raw = input(prompt).strip().lower()
                if raw in ("", "y", "yes"):
                    choice = "use"
                elif raw in ("n", "no"):
                    choice = "custom"
                elif raw == "e":
                    choice = "edit"
                elif raw == "c":
                    choice = "custom"
                elif raw == "p" and available_presets:
                    choice = "preset"
                else:
                    choice = "use"
            if choice == "preset":
                preset, _ = prompt_preset_selection(ui, available_presets, base_locale)
                if not preset:
                    continue
                selected_preset = preset
                source_notes = preset.get_translation(base_locale) or preset.get_translation("en-US")
                if not source_notes:
                    print_warning("Preset has no content for the base language; please choose another option.")
                    selected_preset = None
                    source_notes = base_whats_new or ""
                    continue
                refine_phrase = default_refine
                break
            elif choice == "edit":
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
                selected_preset = None
                break
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
                selected_preset = None
                break
            else:
                source_notes = base_whats_new
                selected_preset = None
                break
    else:
        if available_presets:
            while True:
                preset, wants_custom = prompt_preset_selection(ui, available_presets, base_locale, allow_custom=True)
                if preset:
                    selected_preset = preset
                    source_notes = preset.get_translation(base_locale) or preset.get_translation("en-US")
                    if not source_notes:
                        print_warning("Preset has no content for the base language; please choose another.")
                        selected_preset = None
                        continue
                    refine_phrase = default_refine
                    break
                if wants_custom:
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
                    selected_preset = None
                    break
                print_info("Cancelled")
                return True
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
            selected_preset = None

    # Determine empty locales
    empty_by_platform: Dict[str, List[str]] = {}
    union_empty: List[str] = []
    base_missing_platforms: List[str] = []
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
        base_here = (locale_map.get(base_locale, {}).get("whatsNew") or "").strip()
        if not base_here:
            base_missing_platforms.append(plat)
    if not union_empty and not base_missing_platforms:
        print_info("All selected platforms already have release notes for this version")
        return True

    # Select target locales
    if union_empty:
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
    else:
        target_locales = []
        print_info("No additional locales require release notes; the base locale will be updated if empty.")

    # Use session-wide seed
    seed = getattr(cli, 'session_seed', None)

    # Translate + review loop
    limit = get_field_limit("whats_new") or 4000
    translations: Dict[str, str] = {}
    provs = providers.list_providers()
    default_provider = getattr(cli, 'config', None).get_default_ai_provider() if getattr(cli, 'config', None) else None
    selected_provider: Optional[str] = None
    provider = None

    while True:
        if selected_preset is None and provider is None and target_locales:
            if not provs:
                print_error("No AI providers configured. Please run setup.")
                return True
            if len(provs) == 1:
                selected_provider = provs[0]
                print_info(f"Using AI provider: {selected_provider}")
            else:
                # Offer to use configured default provider if set
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

        # Generate translations either from preset or provider
        if selected_preset is not None:
            print_info(f"Using preset: {selected_preset.name}")
            translations = {}
            for loc in target_locales:
                txt = (selected_preset.get_translation(loc) or "").strip()
                if len(txt) > limit:
                    txt = txt[:limit]
                translations[loc] = txt
        elif target_locales:
            show_provider_and_source(provider, selected_provider, base_locale, source_notes, title="Source release notes to translate", seed=seed)

            def _task(loc: str) -> str:
                language = APP_STORE_LOCALES.get(loc, loc)
                txt = provider.translate(
                    text=source_notes,
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

            translations, _errs = parallel_map_locales(target_locales, _task, progress_action="Translated", pacing_seconds=1.0)
        else:
            translations = {}

        # Preview
        if target_locales:
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
                    {"name": "Re-enter source notes and re-translate" if selected_preset is None else "Change preset or enter new source notes", "value": "reenter"},
                    {"name": "Cancel", "value": "cancel"},
                ], add_back=True,
            )
            if choice is None or choice == "cancel":
                print_info("Cancelled")
                return True
            if choice == "reenter":
                if selected_preset is not None:
                    new_preset, wants_custom = prompt_preset_selection(
                        ui,
                        available_presets,
                        base_locale,
                        exclude_id=selected_preset.preset_id,
                        allow_custom=True,
                    )
                    if wants_custom:
                        initial = build_refinement_template(refine_phrase or default_refine, source_notes)
                        new_notes = ui.prompt_multiline("Enter new source release notes (END with 'EOF'):", initial=initial)
                        if not new_notes:
                            print_warning("No content entered; keeping previous source notes.")
                        else:
                            clean, parsed_refine = parse_refinement_template(new_notes, fallback_default=refine_phrase or default_refine)
                            if clean:
                                source_notes = clean
                                refine_phrase = parsed_refine
                                selected_preset = None
                                provider = None
                                selected_provider = None
                        continue
                    if new_preset:
                        selected_preset = new_preset
                        source_notes = new_preset.get_translation(base_locale) or new_preset.get_translation("en-US")
                        continue
                    continue
                else:
                    initial = build_refinement_template(refine_phrase or default_refine, source_notes)
                    new_notes = ui.prompt_multiline("Enter new source release notes (END with 'EOF'):", initial=initial)
                    if not new_notes:
                        print_warning("No content entered; keeping previous source notes.")
                    else:
                        clean, parsed_refine = parse_refinement_template(new_notes, fallback_default=refine_phrase or default_refine)
                        if clean:
                            source_notes = clean
                            refine_phrase = parsed_refine
                    continue
            do_edit = (choice == "edit")
        else:
            raw = input("Apply all (a) / Edit (e) / Re-enter source (r) / Cancel (c): ").strip().lower()
            if raw == 'c':
                print_info("Cancelled")
                return True
            if raw == 'r':
                if selected_preset is not None:
                    new_preset, wants_custom = prompt_preset_selection(
                        ui,
                        available_presets,
                        base_locale,
                        exclude_id=selected_preset.preset_id,
                        allow_custom=True,
                    )
                    if wants_custom:
                        initial = build_refinement_template(refine_phrase or default_refine, source_notes)
                        new_notes = ui.prompt_multiline("Enter new source release notes (END with 'EOF'):", initial=initial)
                        if not new_notes:
                            print_warning("No content entered; keeping previous source notes.")
                        else:
                            clean, parsed_refine = parse_refinement_template(new_notes, fallback_default=refine_phrase or default_refine)
                            if clean:
                                source_notes = clean
                                refine_phrase = parsed_refine
                                selected_preset = None
                                provider = None
                                selected_provider = None
                        continue
                    if new_preset:
                        selected_preset = new_preset
                        source_notes = new_preset.get_translation(base_locale) or new_preset.get_translation("en-US")
                        continue
                    continue
                else:
                    initial = build_refinement_template(refine_phrase or default_refine, source_notes)
                    new_notes = ui.prompt_multiline("Enter new source release notes (END with 'EOF'):", initial=initial)
                    if not new_notes:
                        print_warning("No content entered; keeping previous source notes.")
                    else:
                        clean, parsed_refine = parse_refinement_template(new_notes, fallback_default=refine_phrase or default_refine)
                        if clean:
                            source_notes = clean
                            refine_phrase = parsed_refine
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
        locales_for_platform = empty_by_platform.get(plat, [])
        base_needs_update = plat in base_missing_platforms
        total_to_update = len(locales_for_platform) + (1 if base_needs_update else 0)
        print_info(f"Applying to {plat_name} ({total_to_update} locale{'s' if total_to_update != 1 else ''})...")

        # Update base locale if empty
        success = 0
        base_empty_here = not (locale_map.get(base_locale, {}).get("whatsNew") or "").strip()
        if base_empty_here:
            try:
                asc.update_app_store_version_localization(localization_id=locale_map[base_locale]["id"], whats_new=source_notes[:limit])
                print_success(f"  Base locale {APP_STORE_LOCALES.get(base_locale, base_locale)} updated")
                success += 1
            except Exception as e:
                print_warning(f"  Could not update base locale: {str(e)}")

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
        print_success(f"{plat_name}: {success}/{total_to_update} locale{'s' if total_to_update != 1 else ''} updated")

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
