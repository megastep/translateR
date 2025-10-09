"""
Manage release note presets.

Allows users to create reusable release note snippets, translate them into
all supported locales, and delete custom presets.
"""

from __future__ import annotations

import textwrap
from typing import Dict, List, Optional, Tuple

from release_presets import (
    ReleaseNotePreset,
    list_presets,
    save_user_preset,
    delete_user_preset,
    generate_preset_id,
    preset_exists,
)
from utils import (
    APP_STORE_LOCALES,
    get_field_limit,
    parallel_map_locales,
    print_error,
    print_info,
    print_success,
    print_warning,
)


def _preset_preview(preset: ReleaseNotePreset) -> str:
    text = preset.get_translation("en-US").replace("\n", " ").strip()
    if not text:
        text = preset.get_translation(next(iter(APP_STORE_LOCALES.keys())))
    return textwrap.shorten(text or "(empty)", width=70, placeholder="…")


def _select_provider(cli) -> Optional[Tuple[str, object]]:
    ui = cli.ui
    providers_mgr = cli.ai_manager
    provs = providers_mgr.list_providers()
    if not provs:
        print_error("No AI providers configured. Run configuration first.")
        return None

    default_provider = getattr(cli, "config", None).get_default_ai_provider() if getattr(cli, "config", None) else None
    selected_provider: Optional[str] = None

    if len(provs) == 1:
        selected_provider = provs[0]
        print_info(f"Using AI provider: {selected_provider}")
    else:
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
                selected_provider = ui.select("Select AI provider for preset translation", choices, add_back=True)
            if not selected_provider:
                print("Available AI providers:")
                for i, p in enumerate(provs, 1):
                    star = " *" if p == default_provider else ""
                    print(f"{i}. {p}{star}")
                raw = input("Select provider (number) or 'b' to cancel (Enter = default): ").strip().lower()
                if raw == "b":
                    print_info("Cancelled")
                    return None
                if not raw and default_provider and default_provider in provs:
                    selected_provider = default_provider
                else:
                    try:
                        idx = int(raw)
                        if 1 <= idx <= len(provs):
                            selected_provider = provs[idx - 1]
                        else:
                            print_error("Invalid choice")
                            return None
                    except ValueError:
                        print_error("Please enter a number")
                        return None

    if not selected_provider:
        print_info("Cancelled")
        return None
    provider = providers_mgr.get_provider(selected_provider)
    return selected_provider, provider


def _prompt_text(ui, prompt: str, initial: str = "") -> Optional[str]:
    text = ui.prompt_multiline(prompt, initial=initial)
    if text is None:
        return None
    cleaned = text.strip()
    return cleaned or None


def _create_preset(cli) -> None:
    ui = cli.ui
    name = ui.text("Preset name (for menus): ") if ui.available() else input("Preset name (for menus): ").strip()
    if not name:
        print_warning("Preset name is required.")
        return
    preset_id = generate_preset_id(name)
    if preset_exists(preset_id):
        overwrite = ui.confirm(f"Preset '{name}' already exists. Overwrite?", False)
        if overwrite is None:
            raw = input(f"Preset '{name}' exists. Overwrite? (y/N): ").strip().lower()
            overwrite = raw in ("y", "yes")
        if not overwrite:
            print_info("Keeping existing preset.")
            return

    description = ""
    if ui.available():
        desc = ui.text("Optional description (press Enter to skip): ")
        description = desc or ""
    else:
        description = input("Optional description (press Enter to skip): ").strip()

    english_prompt = "Enter the English release notes for this preset (END with 'EOF'):"
    english_text = _prompt_text(ui, english_prompt)
    if not english_text:
        print_warning("No English text entered; aborting preset creation.")
        return

    limit = get_field_limit("whats_new") or 4000
    if len(english_text) > limit:
        english_text = english_text[:limit]
        print_warning(f"English text truncated to {limit} characters.")

    provider_choice = _select_provider(cli)
    if not provider_choice:
        return
    provider_name, provider = provider_choice

    seed = getattr(cli, "session_seed", None)
    default_refine = (getattr(cli, "config", None).get_prompt_refinement() if getattr(cli, "config", None) else "") or ""

    translations: Dict[str, str] = {}
    for locale in APP_STORE_LOCALES.keys():
        if locale.startswith("en"):
            translations[locale] = english_text

    target_locales = [loc for loc in APP_STORE_LOCALES.keys() if not loc.startswith("en")]
    print_info(f"Translating preset into {len(target_locales)} locale(s) with {provider_name}…")

    def _task(locale: str) -> str:
        language = APP_STORE_LOCALES.get(locale, locale)
        txt = provider.translate(
            text=english_text,
            target_language=language,
            max_length=limit,
            is_keywords=False,
            seed=seed,
            refinement=default_refine,
        )
        txt = (txt or "").strip()
        if len(txt) > limit:
            txt = txt[:limit]
        return txt

    translated, errors = parallel_map_locales(target_locales, _task, progress_action="Translated", pacing_seconds=1.0)
    print()
    if errors:
        print_error("Unable to create preset; some translations failed:")
        for loc, err in errors.items():
            language = APP_STORE_LOCALES.get(loc, loc)
            print_error(f"  {language} [{loc}]: {err}")
        return

    translations.update(translated)

    preset, path = save_user_preset(name=name, translations=translations, description=description or None, preset_id=preset_id)
    print_success(f"Preset '{preset.name}' saved to {path}")


def _delete_preset(ui, presets: List[ReleaseNotePreset]) -> None:
    user_presets = [p for p in presets if not p.built_in]
    if not user_presets:
        print_info("No user-defined presets to delete.")
        return

    if ui.available():
        choices = [{"name": f"{p.name} — {_preset_preview(p)}", "value": p.preset_id} for p in user_presets]
        chosen = ui.select("Select preset to delete", choices, add_back=True)
        if not chosen:
            return
        target = next((p for p in user_presets if p.preset_id == chosen), None)
    else:
        print("User presets:")
        for idx, preset in enumerate(user_presets, 1):
            label = f"{preset.name} — {_preset_preview(preset)}"
            print(f"{idx}. {label}")
        raw = input("Select preset to delete (number) or press Enter to cancel: ").strip()
        if not raw:
            return
        try:
            idx = int(raw)
            target = user_presets[idx - 1] if 1 <= idx <= len(user_presets) else None
        except ValueError:
            print_error("Invalid selection")
            return
    if not target:
        print_error("Preset not found.")
        return

    confirm = ui.confirm(f"Delete preset '{target.name}'?", False)
    if confirm is None:
        raw = input(f"Delete preset '{target.name}'? (y/N): ").strip().lower()
        confirm = raw in ("y", "yes")
    if not confirm:
        print_info("Deletion cancelled.")
        return
    if delete_user_preset(target.preset_id):
        print_success(f"Preset '{target.name}' deleted.")
    else:
        print_error("Failed to delete preset. Check file permissions.")


def _view_preset(ui, presets: List[ReleaseNotePreset]) -> None:
    if not presets:
        print_info("No presets available yet.")
        return

    if ui.available():
        choices = []
        for preset in presets:
            tag = " (built-in)" if preset.built_in else ""
            choices.append({"name": f"{preset.name}{tag} — {_preset_preview(preset)}", "value": preset.preset_id})
        chosen = ui.select("Select preset to view", choices, add_back=True)
        if not chosen:
            return
        target = next((p for p in presets if p.preset_id == chosen), None)
    else:
        print("Presets:")
        for idx, preset in enumerate(presets, 1):
            tag = " (built-in)" if preset.built_in else ""
            print(f"{idx}. {preset.name}{tag} — {_preset_preview(preset)}")
        raw = input("Select preset to view (number) or press Enter to cancel: ").strip()
        if not raw:
            return
        try:
            idx = int(raw)
            target = presets[idx - 1] if 1 <= idx <= len(presets) else None
        except ValueError:
            print_error("Invalid selection")
            return
    if not target:
        print_error("Preset not found.")
        return

    print()
    print_info(f"Preset: {target.name} ({'built-in' if target.built_in else 'user'})")
    if target.description:
        print_info(f"Description: {target.description}")
    print_info("English text:")
    print("-" * 60)
    print(target.get_translation("en-US"))
    print("-" * 60)
    print_info(f"Stored translations: {len(target.translations)} locales")
    sample_locales = [loc for loc in ("fr-FR", "de-DE", "ja", "es-ES") if loc in target.translations]
    for loc in sample_locales:
        print(f"{APP_STORE_LOCALES.get(loc, loc)} [{loc}]: {target.translations.get(loc, '')[:120]}")
    print()


def run(cli) -> bool:
    """Manage release note presets."""
    ui = cli.ui
    print_info("Preset Manager - Create and organize release note presets")
    while True:
        presets = list_presets()
        print()
        print_info(f"{len(presets)} preset(s) available")
        for preset in presets:
            tag = "🛠" if not preset.built_in else "📦"
            print(f"  {tag} {preset.name} — {_preset_preview(preset)}")

        if ui.available():
            choices = [
                {"name": "Create new preset", "value": "create"},
                {"name": "View preset details", "value": "view"},
                {"name": "Delete a preset", "value": "delete"},
                {"name": "Back to main menu", "value": "back"},
            ]
            action = ui.select("Preset Manager", choices, add_back=False)
        else:
            print()
            print("Actions:")
            print("1. Create new preset")
            print("2. View preset details")
            print("3. Delete a preset")
            print("4. Back to main menu")
            action = input("Choose an action (1-4): ").strip()
            mapping = {"1": "create", "2": "view", "3": "delete", "4": "back"}
            action = mapping.get(action, "")

        if action in (None, "", "back"):
            print_info("Returning to main menu.")
            return True
        if action == "create":
            _create_preset(cli)
        elif action == "view":
            _view_preset(ui, presets)
        elif action == "delete":
            _delete_preset(ui, presets)
        else:
            print_warning("Unknown action. Please choose again.")
