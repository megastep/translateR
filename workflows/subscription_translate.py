"""
Subscription localization translation workflow.

Translates subscription name and description to missing locales.
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
)


def _pick_group(ui, asc, app_id: str):
    resp = asc.get_subscription_groups(app_id)
    groups = resp.get("data", []) if isinstance(resp, dict) else []
    if not groups:
        print_warning("No subscription groups found for this app")
        return None
    choices = []
    for g in groups:
        attrs = g.get("attributes", {})
        label = attrs.get("referenceName") or g.get("id")
        choices.append({"name": label, "value": g.get("id")})
    if ui.available():
        return ui.select("Select subscription group", choices, add_back=True)
    for idx, c in enumerate(choices, 1):
        print(f"{idx}. {c['name']}")
    raw = input("Select group (number): ").strip()
    try:
        idx = int(raw)
        return choices[idx - 1]["value"] if 1 <= idx <= len(choices) else None
    except Exception:
        return None


def _pick_subscriptions(ui, asc, group_id: str) -> List[Dict]:
    resp = asc.get_subscriptions_for_group(group_id)
    subs = resp.get("data", []) if isinstance(resp, dict) else []
    if not subs:
        print_warning("No subscriptions found in this group")
        return []
    choices = []
    id_to_item = {}
    for s in subs:
        attrs = s.get("attributes", {})
        name = attrs.get("name") or s.get("id")
        pid = attrs.get("productId", "")
        label = name + (f"  [{pid}]" if pid else "")
        choices.append({"name": label, "value": s.get("id")})
        id_to_item[s.get("id")] = s
    selected: List[str] = []
    if ui.available():
        selected = ui.checkbox("Select subscriptions to translate", choices, add_back=True) or []
    else:
        for idx, c in enumerate(choices, 1):
            print(f"{idx}. {c['name']}")
        raw = input("Enter numbers (comma-separated): ").strip()
        if raw:
            try:
                nums = [int(x) for x in raw.replace(' ', '').split(',') if x]
                for n in nums:
                    if 1 <= n <= len(choices):
                        selected.append(choices[n - 1]["value"])
            except Exception:
                selected = []
    if not selected:
        print_warning("No subscriptions selected")
        return []
    return [id_to_item[sid] for sid in selected if sid in id_to_item]


def _mode_selector(ui) -> str:
    if ui.available():
        choice = ui.select("Select subscription translation scope", [
            {"name": "Subscriptions (products)", "value": "sub"},
            {"name": "Subscription Groups (group display)", "value": "group"},
        ], add_back=True)
        return choice or "sub"
    print("1) Subscriptions (products)\n2) Subscription Groups")
    raw = input("Select (1-2): ").strip()
    return "group" if raw == "2" else "sub"


def run(cli) -> bool:
    ui = cli.ui
    asc = cli.asc_client

    print_info("Subscription Translation Mode - Translate subscription name and description")

    scope = _mode_selector(ui)

    app_id = ui.prompt_app_id(asc)
    if app_id is None:
        print_info("Cancelled")
        return True

    group_id = _pick_group(ui, asc, app_id)
    if not group_id:
        print_warning("No group selected")
        return True

    subs: List[Dict] = []
    groups: List[Dict] = []
    if scope == "sub":
        subs = _pick_subscriptions(ui, asc, group_id)
        if not subs:
            return True
    else:
        groups = [g for g in (asc.get_subscription_groups(app_id).get("data", []) or []) if g.get("id") == group_id]
        if not groups:
            print_warning("No group data found")
            return True

    # Prefill locales from app's latest version
    app_locales = set()
    try:
        latest_ver = asc.get_latest_app_store_version(app_id)
        if latest_ver:
            locs = asc.get_app_store_version_localizations(latest_ver).get("data", [])
            app_locales = {l.get("attributes", {}).get("locale") for l in locs if l.get("attributes", {}).get("locale")}
    except Exception:
        pass

    # Provider selection (reuse helper from IAP)
    from workflows.iap_translate import _pick_provider  # reuse selection helper
    provider, provider_key = _pick_provider(cli)
    if not provider:
        return True
    refine_phrase = (getattr(cli, "config", None).get_prompt_refinement() if getattr(cli, "config", None) else "") or ""
    seed = getattr(cli, "session_seed", None)
    pname, pmodel = provider_model_info(provider, provider_key)
    print_info(f"AI provider: {pname} — model: {pmodel or 'n/a'} — seed: {seed}")

    targets = subs if scope == "sub" else groups
    global_targets: List[str] = []
    global_targets_enabled = scope == "sub" and len(subs) > 1

    # Preselect targets once for multi-sub runs
    if global_targets_enabled:
        first_sub = subs[0]
        loc_resp = asc.get_subscription_localizations(first_sub.get("id"))
        locs_first = loc_resp.get("data", []) if isinstance(loc_resp, dict) else []
        base_locale_first = detect_base_language(locs_first)
        existing_first = {l.get("attributes", {}).get("locale") for l in locs_first if l.get("attributes", {}).get("locale")}
        from workflows.iap_translate import _choose_targets
        global_targets = _choose_targets(ui, list(existing_first), base_locale_first or "", preferred_locales=app_locales)

    for idx, sub in enumerate(targets, 1):
        attrs = sub.get("attributes", {})
        if scope == "sub":
            sub_name = attrs.get("name") or "Untitled Subscription"
            product_id = attrs.get("productId", "")
            label = f"{sub_name} [{product_id}]" if product_id else sub_name
        else:
            sub_name = attrs.get("referenceName") or "Subscription Group"
            label = sub_name
        print()
        print_info(f"({idx}/{len(targets)}) Processing {label}")

        loc_resp = asc.get_subscription_localizations(sub.get("id")) if scope == "sub" else asc.get_subscription_group_localizations(sub.get("id"))
        locs = loc_resp.get("data", []) if isinstance(loc_resp, dict) else []
        if not locs:
            print_warning("No existing localizations; skipping")
            continue

        base_locale = detect_base_language(locs)
        if not base_locale:
            print_error("Could not detect base language; skipping")
            continue
        base_attrs = next((l.get("attributes", {}) for l in locs if l.get("attributes", {}).get("locale") == base_locale), {})
        base_name = base_attrs.get("name", "")
        base_desc = base_attrs.get("description", "") if scope == "sub" else base_attrs.get("customAppName", "")
        if not base_name:
            print_error("Base subscription name missing; skipping")
            continue
        print_info(f"Base language: {APP_STORE_LOCALES.get(base_locale, base_locale)} [{base_locale}]")

        existing_locale_ids: Dict[str, str] = {l.get("attributes", {}).get("locale"): l.get("id") for l in locs if l.get("id")}
        from workflows.iap_translate import _choose_targets  # reuse locale selector with defaults
        if global_targets_enabled and global_targets:
            target_locales = [t for t in global_targets if t not in existing_locale_ids and t != base_locale]
        else:
            target_locales = _choose_targets(ui, list(existing_locale_ids.keys()), base_locale, preferred_locales=app_locales)
        if not target_locales:
            print_warning("No target languages selected; skipping this subscription")
            continue

        name_limit = get_field_limit("subscription_name") if scope == "sub" else get_field_limit("subscription_group_name")
        desc_limit = get_field_limit("subscription_description") if scope == "sub" else get_field_limit("subscription_group_custom_app_name")

        def _task(loc: str):
            language_name = APP_STORE_LOCALES.get(loc, loc)
            translated = {}
            translated["name"] = provider.translate(base_name, language_name, max_length=name_limit, seed=seed, refinement=refine_phrase)
            if base_desc:
                field = "description" if scope == "sub" else "customAppName"
                translated[field] = provider.translate(base_desc, language_name, max_length=desc_limit, seed=seed, refinement=refine_phrase)
            time.sleep(1)
            return translated

        results, errs = parallel_map_locales(target_locales, _task, progress_action="Translated", pacing_seconds=0.0)

        success = 0
        for loc, data in results.items():
            loc_id = existing_locale_ids.get(loc)
            try:
                if scope == "sub":
                    if loc_id:
                        asc.update_subscription_localization(loc_id, data.get("name"), data.get("description"))
                    else:
                        asc.create_subscription_localization(sub.get("id"), loc, data.get("name", ""), data.get("description"))
                else:
                    if loc_id:
                        asc.update_subscription_group_localization(loc_id, data.get("name"), data.get("customAppName"))
                    else:
                        asc.create_subscription_group_localization(sub.get("id"), loc, data.get("name", ""), data.get("customAppName"))
                success += 1
            except Exception as e:
                if "409" in str(e) and not loc_id:
                    try:
                        refreshed = asc.get_subscription_localizations(sub.get("id")) if scope == "sub" else asc.get_subscription_group_localizations(sub.get("id"))
                        refreshed_map = {l.get("attributes", {}).get("locale"): l.get("id") for l in refreshed.get("data", [])}
                        new_id = refreshed_map.get(loc)
                        if new_id:
                            if scope == "sub":
                                asc.update_subscription_localization(new_id, data.get("name"), data.get("description"))
                            else:
                                asc.update_subscription_group_localization(new_id, data.get("name"), data.get("customAppName"))
                            success += 1
                            continue
                    except Exception:
                        success += 1
                        continue
                language_name = APP_STORE_LOCALES.get(loc, loc)
                print_error(f"  ❌ Failed to save {language_name}: {e}")

        print_success(f"Saved {success}/{len(target_locales)} locales for {label}")

    input("\nPress Enter to continue...")
    return True
