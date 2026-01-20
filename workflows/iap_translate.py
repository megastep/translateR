"""
In-App Purchase localization translation workflow.

Translates IAP display name and description to missing locales using the
configured AI provider.
"""

import time
from typing import Dict, List

from utils import (
    APP_STORE_LOCALES,
    get_field_limit,
    detect_base_language,
    print_info,
    print_warning,
    print_error,
    print_success,
    parallel_map_locales,
    provider_model_info,
    format_progress,
)
from workflows.helpers import pick_provider, choose_target_locales, get_app_locales


def _select_iaps(ui, asc, app_id: str) -> List[Dict]:
    """Let the user pick one or more IAPs for translation."""
    resp = asc.get_in_app_purchases(app_id)
    items = resp.get("data", []) if isinstance(resp, dict) else []
    if not items:
        print_error("No in-app purchases found for this app")
        return []

    choices = []
    for i in items:
        attrs = i.get("attributes", {})
        name = attrs.get("referenceName") or attrs.get("name") or "Untitled IAP"
        pid = attrs.get("productId")
        iap_type = attrs.get("inAppPurchaseType") or ""
        resource_type = i.get("type") or "inAppPurchasesV2"
        label = name
        if pid:
            label += f"  [{pid}]"
        if iap_type:
            label += f" — {iap_type}"
        choices.append({"name": label, "value": i.get("id"), "resource_type": resource_type})

    selected_ids: List[str] = []
    if ui.available():
        selected_ids = ui.checkbox(
            "Select in-app purchases to translate (Space to toggle, Enter to confirm)",
            choices,
            add_back=True,
        ) or []
    else:
        print("Available IAPs:")
        for idx, choice in enumerate(choices, 1):
            print(f"{idx:2d}. {choice['name']}")
        raw = input("Enter IAP numbers (comma-separated): ").strip()
        if raw:
            try:
                nums = [int(x) for x in raw.replace(' ', '').split(',') if x]
                for n in nums:
                    if 1 <= n <= len(choices):
                        selected_ids.append(choices[n - 1]["value"])
            except Exception:
                selected_ids = []

    if not selected_ids:
        print_warning("No in-app purchases selected")
        return []

    selected_items = [item for item in items if item.get("id") in selected_ids]
    if not selected_items:
        missing = ", ".join(selected_ids)
        print_warning(f"Selected IAPs not found in response: {missing}")
    return selected_items


def run(cli) -> bool:
    ui = cli.ui
    asc = cli.asc_client

    print_info("In-App Purchase Translation Mode - Translate product name and description")

    app_id = ui.prompt_app_id(asc)
    if app_id is None:
        print_info("Cancelled")
        return True

    # Collect app locales to pre-fill targets
    app_locales = get_app_locales(asc, app_id)

    selected_iaps = _select_iaps(ui, asc, app_id)
    if not selected_iaps:
        return True

    provider, provider_key = pick_provider(cli)
    if not provider:
        return True
    refine_phrase = (getattr(cli, "config", None).get_prompt_refinement() if getattr(cli, "config", None) else "") or ""
    seed = getattr(cli, "session_seed", None)
    pname, pmodel = provider_model_info(provider, provider_key)
    print_info(f"AI provider: {pname} — model: {pmodel or 'n/a'} — seed: {seed}")

    total_translated = 0
    for idx, iap in enumerate(selected_iaps, 1):
        attrs = iap.get("attributes", {})
        iap_name = attrs.get("referenceName") or attrs.get("name") or "Untitled IAP"
        product_id = attrs.get("productId", "")
        label = f"{iap_name} [{product_id}]" if product_id else iap_name
        resource_type = iap.get("type") or "inAppPurchasesV2"
        print()
        print_info(f"({idx}/{len(selected_iaps)}) Processing {label}")

        loc_resp = asc.get_in_app_purchase_localizations(iap.get("id"))
        localizations = loc_resp.get("data", []) if isinstance(loc_resp, dict) else []
        if not localizations:
            print_warning("No existing localization found; unable to detect base language")
            continue

        base_locale = detect_base_language(localizations)
        if not base_locale:
            print_error("Could not detect base language for this IAP; skipping")
            continue
        base_attrs = next((l.get("attributes", {}) for l in localizations if l.get("attributes", {}).get("locale") == base_locale), {})
        base_name = base_attrs.get("name", "")
        base_description = base_attrs.get("description", "")
        if not (base_name or "").strip():
            # Name is required for InAppPurchaseLocalizationCreateRequest; without it we cannot create new locales.
            print_error("Base localization is missing required name; skipping")
            continue
        print_info(f"Base language: {APP_STORE_LOCALES.get(base_locale, base_locale)} [{base_locale}]")

        existing_locale_ids: Dict[str, str] = {l.get("attributes", {}).get("locale"): l.get("id") for l in localizations if l.get("id")}
        available_targets = {k: v for k, v in APP_STORE_LOCALES.items() if k not in existing_locale_ids and k != base_locale}
        if not available_targets:
            print_warning("All supported languages are already localized for this IAP")
            continue
        target_locales = choose_target_locales(ui, available_targets, base_locale, preferred_locales=app_locales, prompt="Select target languages")
        if not target_locales:
            print_warning("No target languages selected; skipping this IAP")
            continue

        name_limit = get_field_limit("iap_name") or 30
        desc_limit = get_field_limit("iap_description") or 45

        def _task(loc: str):
            language_name = APP_STORE_LOCALES.get(loc, loc)
            translated = {}
            # Name is required; retry once if the model returns empty.
            translated_name = provider.translate(base_name, language_name, max_length=name_limit, seed=seed, refinement=refine_phrase) or ""
            if not translated_name.strip():
                stronger = (refine_phrase or "").strip()
                extra = " Do not return an empty string. Return ONLY the translated text."
                stronger = (stronger + extra).strip() if stronger else extra.strip()
                translated_name = provider.translate(base_name, language_name, max_length=name_limit, seed=seed, refinement=stronger) or ""
            translated["name"] = translated_name.strip()
            if base_description:
                translated["description"] = provider.translate(base_description, language_name, max_length=desc_limit, seed=seed, refinement=refine_phrase)
            time.sleep(1)
            return translated

        results, errs = parallel_map_locales(target_locales, _task, progress_action="Translated", pacing_seconds=0.0)

        success_count = 0
        total_targets = len(target_locales)
        completed = 0
        last_progress_len = 0
        try:
            line = format_progress(0, total_targets, "Saving locales...")
            print(line, end="\r")
            last_progress_len = len(line)
        except Exception:
            pass
        for loc, data in results.items():
            if not (data.get("name") or "").strip():
                language_name = APP_STORE_LOCALES.get(loc, loc)
                print_error(f"  ❌ Skipping {language_name}: translated name is empty (required)")
                completed += 1
                try:
                    line = format_progress(completed, total_targets, f"Skipped {APP_STORE_LOCALES.get(loc, loc)}")
                    pad = max(0, last_progress_len - len(line))
                    print("\r" + line + (" " * pad), end="")
                    last_progress_len = len(line)
                except Exception:
                    pass
                continue
            loc_id = existing_locale_ids.get(loc)
            try:
                if loc_id:
                    asc.update_in_app_purchase_localization(loc_id, data.get("name"), data.get("description"))
                else:
                    asc.create_in_app_purchase_localization(
                        iap.get("id"),
                        loc,
                        data.get("name", ""),
                        data.get("description"),
                    )
                success_count += 1
                completed += 1
                try:
                    line = format_progress(completed, total_targets, f"Saved {APP_STORE_LOCALES.get(loc, loc)}")
                    pad = max(0, last_progress_len - len(line))
                    print("\r" + line + (" " * pad), end="")
                    last_progress_len = len(line)
                except Exception:
                    pass
            except Exception as e:
                # If creation conflicted, try to refresh and update instead
                if "409" in str(e) and not loc_id:
                    try:
                        refreshed = asc.get_in_app_purchase_localizations(iap.get("id"))
                        refreshed_map = {l.get("attributes", {}).get("locale"): l.get("id") for l in refreshed.get("data", [])}
                        new_id = refreshed_map.get(loc)
                        if new_id:
                            asc.update_in_app_purchase_localization(new_id, data.get("name"), data.get("description"))
                            success_count += 1
                            existing_locale_ids[loc] = new_id
                            completed += 1
                            try:
                                line = format_progress(completed, total_targets, f"Saved {APP_STORE_LOCALES.get(loc, loc)}")
                                pad = max(0, last_progress_len - len(line))
                                print("\r" + line + (" " * pad), end="")
                                last_progress_len = len(line)
                            except Exception:
                                pass
                            continue
                    except Exception:
                        pass
                language_name = APP_STORE_LOCALES.get(loc, loc)
                print_error(f"  ❌ Failed to save {language_name}: {e}")

        try:
            print("\r" + (" " * last_progress_len) + "\r", end="")
        except Exception:
            pass
        total_translated += success_count
        print_success(f"Saved {success_count}/{len(target_locales)} locales for {label}")

    print()
    print_success(f"In-App Purchase translation finished. Localizations saved: {total_translated}")
    input("\nPress Enter to continue...")
    return True
