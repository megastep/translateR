"""
Subscription localization translation workflow.

Translates subscription name and description to missing locales.
"""

import json
import time
from typing import Dict, List, Tuple

from translation_validation import translate_with_validation
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
from workflows.helpers import pick_provider, choose_target_locales, get_app_locales, pick_locale_scope


SUBSCRIPTION_LOCALIZATION_LOCKED_STATES = {
    "WAITING_FOR_REVIEW",
    "IN_REVIEW",
    "PENDING_BINARY_APPROVAL",
}


def _subscription_state(asc, subscription: Dict) -> str:
    """Return the product state, fetching the single resource when list data omitted it."""
    state = (subscription.get("attributes") or {}).get("state")
    if state:
        return state
    subscription_id = subscription.get("id")
    if not subscription_id:
        return ""
    try:
        response = asc.get_subscription(subscription_id)
        return (response.get("data", {}).get("attributes") or {}).get("state") or ""
    except Exception:
        return ""


def _is_localization_validation_error(error: Exception) -> bool:
    """Return whether an ASC error can plausibly be fixed by new field values."""
    if isinstance(error, ValueError):
        return True
    response = getattr(error, "response", None)
    status = getattr(response, "status_code", None)
    if response is not None and status in (400, 409, 422):
        try:
            body = response.json()
        except Exception:
            body = None
        errors = body.get("errors", []) if isinstance(body, dict) else []
        if errors:
            error_text = json.dumps(errors, ensure_ascii=False).lower()
            field_markers = (
                "/data/attributes/name",
                "/data/attributes/description",
                "/data/attributes/customappname",
                "character",
                "too long",
                "maximum length",
                "invalid attribute",
            )
            return any(marker in error_text for marker in field_markers)
        return True
    message = str(error).upper()
    return any(marker in message for marker in ("400", "409", "422", "ENTITY_ERROR", "INVALID"))


def _asc_error_summary(error: Exception) -> str:
    """Extract actionable JSON:API error details from an ASC exception."""
    response = getattr(error, "response", None)
    if response is None:
        return str(error)
    status = getattr(response, "status_code", None)
    try:
        body = response.json()
    except Exception:
        body = getattr(response, "text", "") or ""
    details = []
    if isinstance(body, dict):
        for item in body.get("errors", []) or []:
            if not isinstance(item, dict):
                continue
            source = item.get("source") or {}
            pointer = source.get("pointer") if isinstance(source, dict) else None
            parts = [item.get("code"), item.get("title"), item.get("detail"), pointer]
            detail = " | ".join(str(part) for part in parts if part)
            if detail:
                details.append(detail)
    if not details and body:
        details.append(json.dumps(body, ensure_ascii=False)[:800] if isinstance(body, dict) else str(body)[:800])
    prefix = f"ASC {status}" if status else "ASC error"
    return f"{prefix}: {'; '.join(details)}" if details else f"{prefix}: {error}"


def _require_saved_resource(response, desired: Dict[str, str], *, group_scope: bool) -> str:
    """Require the successful JSON:API resource ASC promises for POST/PATCH."""
    resource = response.get("data") if isinstance(response, dict) else None
    if not isinstance(resource, dict) or not resource.get("id"):
        raise RuntimeError("ASC returned no saved localization resource")
    attrs = resource.get("attributes")
    if isinstance(attrs, dict):
        description_field = "customAppName" if group_scope else "description"
        desired_name = desired.get("name")
        if (
            desired_name is not None
            and attrs.get("name") is not None
            and attrs.get("name") != desired_name
        ):
            raise RuntimeError("ASC response did not preserve the submitted display name")
        desired_description = desired.get(description_field)
        if (
            desired_description is not None
            and attrs.get(description_field) is not None
            and attrs.get(description_field) != desired_description
        ):
            raise RuntimeError("ASC response did not preserve the submitted description")
    return resource["id"]


def _translate_locale_fields(provider, base_name: str, base_desc: str,
                             language_name: str, name_limit: int, desc_limit: int,
                             seed, refinement: str, *, group_scope: bool,
                             submission_retry: bool = False) -> Dict[str, str]:
    translated = {
        "name": translate_with_validation(
            provider, base_name, language_name, max_length=name_limit, seed=seed,
            refinement=refinement,
            field_label="Subscription display name",
            single_line=True,
            forbid_emoji=True,
            submission_retry=submission_retry,
        )
    }
    if base_desc:
        field = "customAppName" if group_scope else "description"
        translated[field] = translate_with_validation(
            provider, base_desc, language_name, max_length=desc_limit, seed=seed,
            refinement=refinement,
            field_label=("Subscription group app name" if group_scope else "Subscription description"),
            single_line=True,
            forbid_emoji=True,
            submission_retry=submission_retry,
        )
    return translated


def _build_subscription_locale_plan(base_locale: str, existing_locale_ids: Dict[str, str]) -> Tuple[Dict[str, Dict[str, str]], Dict[str, List[str]]]:
    """Build locale choice maps for each scope for one subscription item."""
    supported_minus_base = {k: v for k, v in APP_STORE_LOCALES.items() if k != base_locale}
    existing_minus_base = {k for k in existing_locale_ids.keys() if k and k != base_locale}
    missing = {k for k in supported_minus_base.keys() if k not in existing_locale_ids}
    options = {
        "existing": {k: supported_minus_base[k] for k in sorted(existing_minus_base) if k in supported_minus_base},
        "missing": {k: supported_minus_base[k] for k in sorted(missing) if k in supported_minus_base},
        "all": supported_minus_base,
    }
    preferred = {
        "existing": sorted(existing_minus_base),
        "missing": sorted(options["missing"].keys()),
        "all": sorted(existing_minus_base),
    }
    return options, preferred


def _selection_profile_key(base_locale: str, locale_options: Dict[str, Dict[str, str]]) -> Tuple[str, Tuple[str, ...], Tuple[str, ...], Tuple[str, ...]]:
    """Return a stable key for deciding whether locale prompts can be reused."""
    return (
        base_locale,
        tuple(sorted(locale_options["existing"].keys())),
        tuple(sorted(locale_options["missing"].keys())),
        tuple(sorted(locale_options["all"].keys())),
    )


def _pick_groups(ui, asc, app_id: str) -> List[Dict]:
    resp = asc.get_subscription_groups(app_id)
    groups = resp.get("data", []) if isinstance(resp, dict) else []
    if not groups:
        print_warning("No subscription groups found for this app")
        return []
    choices = []
    id_to_group = {}
    for g in groups:
        attrs = g.get("attributes", {})
        label = attrs.get("referenceName") or g.get("id")
        choices.append({"name": label, "value": g.get("id")})
        id_to_group[g.get("id")] = g
    selected_ids: List[str] = []
    if ui.available():
        selected_ids = ui.checkbox("Select subscription group(s)", choices, add_back=True) or []
    else:
        for idx, c in enumerate(choices, 1):
            print(f"{idx}. {c['name']}")
        raw = input("Enter group numbers (comma-separated): ").strip()
        if raw:
            try:
                nums = [int(x) for x in raw.replace(' ', '').split(',') if x]
                for n in nums:
                    if 1 <= n <= len(choices):
                        selected_ids.append(choices[n - 1]["value"])
            except Exception:
                selected_ids = []
    if not selected_ids:
        print_warning("No subscription groups selected")
        return []
    return [id_to_group[sid] for sid in selected_ids if sid in id_to_group]


def _pick_subscriptions(ui, asc, groups: List[Dict]) -> List[Dict]:
    """Select subscriptions across one or more groups."""
    choices = []
    id_to_item: Dict[str, Dict] = {}
    for group in groups:
        group_id = group.get("id")
        group_name = (group.get("attributes") or {}).get("referenceName") or group_id
        resp = asc.get_subscriptions_for_group(group_id)
        subs = resp.get("data", []) if isinstance(resp, dict) else []
        if not subs:
            continue
        for s in subs:
            attrs = s.get("attributes", {})
            name = attrs.get("name") or s.get("id")
            pid = attrs.get("productId", "")
            label = name + (f"  [{pid}]" if pid else "")
            label = f"{group_name}: {label}"
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

    groups_selected = _pick_groups(ui, asc, app_id)
    if not groups_selected:
        return True

    subs: List[Dict] = []
    groups: List[Dict] = []
    if scope == "sub":
        subs = _pick_subscriptions(ui, asc, groups_selected)
        if not subs:
            return True
    else:
        groups = groups_selected

    # Prefill locales from app's latest version
    app_locales = get_app_locales(asc, app_id)

    provider, provider_key = pick_provider(cli)
    if not provider:
        return True
    refine_phrase = (getattr(cli, "config", None).get_prompt_refinement() if getattr(cli, "config", None) else "") or ""
    seed = getattr(cli, "session_seed", None)
    pname, pmodel, extra = provider_model_info(provider, provider_key)
    tier = extra.get("service_tier")
    tier_txt = f" — tier: {tier}" if tier else ""
    print_info(f"AI provider: {pname} — model: {pmodel or 'n/a'}{tier_txt} — seed: {seed}")

    targets = subs if scope == "sub" else groups

    prepared_subs = []
    prepared_groups = []
    if scope == "sub":
        for idx, sub in enumerate(subs, 1):
            attrs = sub.get("attributes", {})
            sub_name = attrs.get("name") or "Untitled Subscription"
            product_id = attrs.get("productId", "")
            label = f"{sub_name} [{product_id}]" if product_id else sub_name

            product_state = _subscription_state(asc, sub)
            if product_state in SUBSCRIPTION_LOCALIZATION_LOCKED_STATES:
                print()
                print_info(f"({idx}/{len(subs)}) Processing {label}")
                print_warning(
                    f"Subscription state is {product_state}; ASC locks localization changes "
                    f"while review is pending. Skipping before translation."
                )
                continue

            loc_resp = asc.get_subscription_localizations(sub.get("id"))
            locs = loc_resp.get("data", []) if isinstance(loc_resp, dict) else []
            if not locs:
                print()
                print_info(f"({idx}/{len(subs)}) Processing {label}")
                print_warning("No existing localizations; skipping")
                continue

            pending_localization_states = {
                (loc.get("attributes") or {}).get("state")
                for loc in locs
            } & SUBSCRIPTION_LOCALIZATION_LOCKED_STATES
            if pending_localization_states:
                print()
                print_info(f"({idx}/{len(subs)}) Processing {label}")
                states = ", ".join(sorted(pending_localization_states))
                print_warning(
                    f"Existing subscription localization state is {states}; ASC locks new or "
                    f"changed localizations until review completes. Skipping before translation."
                )
                continue

            base_locale = detect_base_language(locs)
            if not base_locale:
                print()
                print_info(f"({idx}/{len(subs)}) Processing {label}")
                print_error("Could not detect base language; skipping")
                continue

            base_attrs = next((l.get("attributes", {}) for l in locs if l.get("attributes", {}).get("locale") == base_locale), {})
            base_name = base_attrs.get("name", "")
            base_desc = base_attrs.get("description", "")
            if not base_name:
                print()
                print_info(f"({idx}/{len(subs)}) Processing {label}")
                print_error("Base subscription name missing; skipping")
                continue

            existing_locale_ids: Dict[str, str] = {l.get("attributes", {}).get("locale"): l.get("id") for l in locs if l.get("id")}
            existing_locale_attrs: Dict[str, Dict] = {l.get("attributes", {}).get("locale"): (l.get("attributes", {}) or {}) for l in locs if l.get("attributes")}
            locale_options, preferred_locales = _build_subscription_locale_plan(base_locale, existing_locale_ids)
            prepared_subs.append(
                {
                    "sub": sub,
                    "index": idx,
                    "label": label,
                    "base_locale": base_locale,
                    "base_name": base_name,
                    "base_desc": base_desc,
                    "existing_locale_ids": existing_locale_ids,
                    "existing_locale_attrs": existing_locale_attrs,
                    "locale_options": locale_options,
                    "preferred_locales": preferred_locales,
                    "selection_profile": _selection_profile_key(base_locale, locale_options),
                    "target_locales": [],
                }
            )

        grouped_subs: Dict[Tuple[str, Tuple[str, ...], Tuple[str, ...], Tuple[str, ...]], List[Dict]] = {}
        for ctx in prepared_subs:
            grouped_subs.setdefault(ctx["selection_profile"], []).append(ctx)

        for group in grouped_subs.values():
            first = group[0]
            if len(group) > 1:
                print()
                print_info(
                    f"Selected subscriptions share locale options; choosing target languages once for {len(group)} subscriptions"
                )
                scope_prompt = "Which locales do you want to include for these subscriptions?"
            else:
                scope_prompt = "Which locales do you want to include?"

            locale_scope = pick_locale_scope(ui, default="missing", prompt=scope_prompt)
            if locale_scope == "back":
                for ctx in group:
                    print()
                    print_info(f"({ctx['index']}/{len(subs)}) Processing {ctx['label']}")
                    print_info(f"Base language: {APP_STORE_LOCALES.get(ctx['base_locale'], ctx['base_locale'])} [{ctx['base_locale']}]")
                    print_warning("Cancelled; skipping this subscription")
                continue

            available_targets = first["locale_options"][locale_scope]
            if not available_targets:
                for ctx in group:
                    print()
                    print_info(f"({ctx['index']}/{len(subs)}) Processing {ctx['label']}")
                    print_info(f"Base language: {APP_STORE_LOCALES.get(ctx['base_locale'], ctx['base_locale'])} [{ctx['base_locale']}]")
                    print_warning("No locales available for that selection")
                continue

            target_prompt = "Select target languages for these subscriptions" if len(group) > 1 else "Select target languages"
            target_locales = choose_target_locales(
                ui,
                available_targets,
                first["base_locale"],
                preferred_locales=first["preferred_locales"][locale_scope],
                prompt=target_prompt,
            )
            if not target_locales:
                for ctx in group:
                    print()
                    print_info(f"({ctx['index']}/{len(subs)}) Processing {ctx['label']}")
                    print_info(f"Base language: {APP_STORE_LOCALES.get(ctx['base_locale'], ctx['base_locale'])} [{ctx['base_locale']}]")
                    print_warning("No target languages selected; skipping this subscription")
                continue

            for ctx in group:
                ctx["target_locales"] = [loc for loc in target_locales if loc != ctx["base_locale"]]
    else:
        for idx, group in enumerate(groups, 1):
            attrs = group.get("attributes", {})
            label = attrs.get("referenceName") or "Subscription Group"

            loc_resp = asc.get_subscription_group_localizations(group.get("id"))
            locs = loc_resp.get("data", []) if isinstance(loc_resp, dict) else []
            if not locs:
                print()
                print_info(f"({idx}/{len(groups)}) Processing {label}")
                print_warning("No existing localizations; skipping")
                continue

            base_locale = detect_base_language(locs)
            if not base_locale:
                print()
                print_info(f"({idx}/{len(groups)}) Processing {label}")
                print_error("Could not detect base language; skipping")
                continue

            base_attrs = next((l.get("attributes", {}) for l in locs if l.get("attributes", {}).get("locale") == base_locale), {})
            base_name = base_attrs.get("name", "")
            base_desc = base_attrs.get("customAppName", "")
            if not base_name:
                print()
                print_info(f"({idx}/{len(groups)}) Processing {label}")
                print_error("Base subscription name missing; skipping")
                continue

            existing_locale_ids = {l.get("attributes", {}).get("locale"): l.get("id") for l in locs if l.get("id")}
            existing_locale_attrs = {l.get("attributes", {}).get("locale"): (l.get("attributes", {}) or {}) for l in locs if l.get("attributes")}
            locale_options, preferred_locales = _build_subscription_locale_plan(base_locale, existing_locale_ids)
            prepared_groups.append(
                {
                    "group": group,
                    "index": idx,
                    "label": label,
                    "base_locale": base_locale,
                    "base_name": base_name,
                    "base_desc": base_desc,
                    "existing_locale_ids": existing_locale_ids,
                    "existing_locale_attrs": existing_locale_attrs,
                    "locale_options": locale_options,
                    "preferred_locales": preferred_locales,
                    "selection_profile": _selection_profile_key(base_locale, locale_options),
                    "target_locales": [],
                }
            )

        grouped_groups: Dict[Tuple[str, Tuple[str, ...], Tuple[str, ...], Tuple[str, ...]], List[Dict]] = {}
        for ctx in prepared_groups:
            grouped_groups.setdefault(ctx["selection_profile"], []).append(ctx)

        for group in grouped_groups.values():
            first = group[0]
            if len(group) > 1:
                print()
                print_info(
                    f"Selected subscription groups share locale options; choosing target languages once for {len(group)} groups"
                )
                scope_prompt = "Which locales do you want to include for these subscription groups?"
            else:
                scope_prompt = "Which locales do you want to include?"

            locale_scope = pick_locale_scope(ui, default="missing", prompt=scope_prompt)
            if locale_scope == "back":
                for ctx in group:
                    print()
                    print_info(f"({ctx['index']}/{len(groups)}) Processing {ctx['label']}")
                    print_info(f"Base language: {APP_STORE_LOCALES.get(ctx['base_locale'], ctx['base_locale'])} [{ctx['base_locale']}]")
                    print_warning("Cancelled; skipping this subscription")
                continue

            available_targets = first["locale_options"][locale_scope]
            if not available_targets:
                for ctx in group:
                    print()
                    print_info(f"({ctx['index']}/{len(groups)}) Processing {ctx['label']}")
                    print_info(f"Base language: {APP_STORE_LOCALES.get(ctx['base_locale'], ctx['base_locale'])} [{ctx['base_locale']}]")
                    print_warning("No locales available for that selection")
                continue

            target_prompt = "Select target languages for these subscription groups" if len(group) > 1 else "Select target languages"
            target_locales = choose_target_locales(
                ui,
                available_targets,
                first["base_locale"],
                preferred_locales=first["preferred_locales"][locale_scope],
                prompt=target_prompt,
            )
            if not target_locales:
                for ctx in group:
                    print()
                    print_info(f"({ctx['index']}/{len(groups)}) Processing {ctx['label']}")
                    print_info(f"Base language: {APP_STORE_LOCALES.get(ctx['base_locale'], ctx['base_locale'])} [{ctx['base_locale']}]")
                    print_warning("No target languages selected; skipping this subscription")
                continue

            for ctx in group:
                ctx["target_locales"] = [loc for loc in target_locales if loc != ctx["base_locale"]]

    for idx, sub in enumerate(targets, 1):
        if scope == "sub":
            ctx = next((item for item in prepared_subs if item["sub"].get("id") == sub.get("id")), None)
            if not ctx:
                continue
            label = ctx["label"]
            base_locale = ctx["base_locale"]
            base_name = ctx["base_name"]
            base_desc = ctx["base_desc"]
            existing_locale_ids = ctx["existing_locale_ids"]
            existing_locale_attrs = ctx["existing_locale_attrs"]
            target_locales = ctx["target_locales"]
        else:
            ctx = next((item for item in prepared_groups if item["group"].get("id") == sub.get("id")), None)
            if not ctx:
                continue
            label = ctx["label"]
            base_locale = ctx["base_locale"]
            base_name = ctx["base_name"]
            base_desc = ctx["base_desc"]
            existing_locale_ids = ctx["existing_locale_ids"]
            existing_locale_attrs = ctx["existing_locale_attrs"]
            target_locales = ctx["target_locales"]
        print()
        print_info(f"({idx}/{len(targets)}) Processing {label}")

        print_info(f"Base language: {APP_STORE_LOCALES.get(base_locale, base_locale)} [{base_locale}]")
        if not target_locales:
            print_warning("No target languages selected; skipping this subscription")
            continue

        name_limit = get_field_limit("subscription_name") if scope == "sub" else get_field_limit("subscription_group_name")
        desc_limit = get_field_limit("subscription_description") if scope == "sub" else get_field_limit("subscription_group_custom_app_name")

        def _task(loc: str):
            language_name = APP_STORE_LOCALES.get(loc, loc)
            translated = _translate_locale_fields(
                provider,
                base_name,
                base_desc,
                language_name,
                name_limit,
                desc_limit,
                seed,
                refine_phrase,
                group_scope=scope != "sub",
            )
            time.sleep(1)
            return translated

        results, errs = parallel_map_locales(target_locales, _task, progress_action="Translated", pacing_seconds=0.0)
        for failed_locale, error in errs.items():
            print_error(
                f"Failed to translate {APP_STORE_LOCALES.get(failed_locale, failed_locale)}: {error}"
            )

        success = 0
        total_targets = len(target_locales)
        completed = 0
        last_progress_len = 0
        try:
            line = format_progress(0, total_targets, "Saving locales...")
            print(line, end="\r")
            last_progress_len = len(line)
        except Exception:
            pass
        def _unique_root_match(loc_map: Dict[str, str], locale_code: str) -> str:
            # Never map region/script locales like en-AU to a different variant like en-US.
            # Only allow root matching when the requested locale has no region/script (e.g., fi vs fi-FI).
            if "-" in (locale_code or ""):
                return ""
            root = locale_code.split("-")[0].lower()
            matches = [lid for code, lid in loc_map.items() if code and code.split("-")[0].lower() == root]
            return matches[0] if len(matches) == 1 else ""

        for loc, data in results.items():
            loc_id = existing_locale_ids.get(loc)
            if not loc_id:
                # Attempt a pre-flight unique root match before creation (e.g., fi vs fi-FI)
                loc_id = _unique_root_match(existing_locale_ids, loc)

            # Skip update if current values already match desired ones
            if loc_id:
                current_attrs = existing_locale_attrs.get(loc, {})
                current_name = current_attrs.get("name")
                current_desc = current_attrs.get("description") if scope == "sub" else current_attrs.get("customAppName")
                desired_name = data.get("name")
                desired_desc = data.get("description") if scope == "sub" else data.get("customAppName")
                if current_name == desired_name and (desired_desc is None or current_desc == desired_desc):
                    success += 1
                    completed += 1
                    try:
                        line = format_progress(completed, total_targets, f"Saved {APP_STORE_LOCALES.get(loc, loc)}")
                        pad = max(0, last_progress_len - len(line))
                        print("\r" + line + (" " * pad), end="")
                        last_progress_len = len(line)
                    except Exception:
                        pass
                    continue
            try:
                if scope == "sub":
                    if loc_id:
                        saved = asc.update_subscription_localization(loc_id, data.get("name"), data.get("description"))
                    else:
                        time.sleep(0.25)
                        saved = asc.create_subscription_localization(sub.get("id"), loc, data.get("name", ""), data.get("description"))
                    saved_id = _require_saved_resource(saved, data, group_scope=False)
                    existing_locale_ids[loc] = saved_id
                    existing_locale_attrs[loc] = {"name": data.get("name"), "description": data.get("description")}
                else:
                    if loc_id:
                        saved = asc.update_subscription_group_localization(loc_id, data.get("name"), data.get("customAppName"))
                    else:
                        time.sleep(0.25)
                        saved = asc.create_subscription_group_localization(sub.get("id"), loc, data.get("name", ""), data.get("customAppName"))
                    saved_id = _require_saved_resource(saved, data, group_scope=True)
                    existing_locale_ids[loc] = saved_id
                    existing_locale_attrs[loc] = {"name": data.get("name"), "customAppName": data.get("customAppName")}
                success += 1
                completed += 1
                try:
                    line = format_progress(completed, total_targets, f"Saved {APP_STORE_LOCALES.get(loc, loc)}")
                    pad = max(0, last_progress_len - len(line))
                    print("\r" + line + (" " * pad), end="")
                    last_progress_len = len(line)
                except Exception:
                    pass
            except Exception as e:
                language_name = APP_STORE_LOCALES.get(loc, loc)
                if not _is_localization_validation_error(e):
                    print_error(f"Failed to save {language_name}: {_asc_error_summary(e)}")
                    continue
                original_error = _asc_error_summary(e)
                print_warning(
                    f"ASC rejected {language_name}; forcing one fresh translation ({original_error})"
                )
                try:
                    retry_seed = seed + 1 if isinstance(seed, int) else seed
                    retry_data = _translate_locale_fields(
                        provider,
                        base_name,
                        base_desc,
                        language_name,
                        name_limit,
                        desc_limit,
                        retry_seed,
                        refine_phrase,
                        group_scope=scope != "sub",
                        submission_retry=True,
                    )
                    if scope == "sub":
                        if loc_id:
                            saved = asc.update_subscription_localization(
                                loc_id, retry_data.get("name"), retry_data.get("description")
                            )
                        else:
                            saved = asc.create_subscription_localization(
                                sub.get("id"), loc, retry_data.get("name", ""), retry_data.get("description")
                            )
                        existing_locale_attrs[loc] = {
                            "name": retry_data.get("name"),
                            "description": retry_data.get("description"),
                        }
                    else:
                        if loc_id:
                            saved = asc.update_subscription_group_localization(
                                loc_id, retry_data.get("name"), retry_data.get("customAppName")
                            )
                        else:
                            saved = asc.create_subscription_group_localization(
                                sub.get("id"), loc, retry_data.get("name", ""), retry_data.get("customAppName")
                            )
                        existing_locale_attrs[loc] = {
                            "name": retry_data.get("name"),
                            "customAppName": retry_data.get("customAppName"),
                        }
                    saved_id = _require_saved_resource(saved, retry_data, group_scope=scope != "sub")
                    existing_locale_ids[loc] = saved_id
                    success += 1
                    completed += 1
                except Exception as retry_error:
                    print_error(
                        f"Failed to save {language_name} after forced retranslation: "
                        f"{_asc_error_summary(retry_error)} "
                        f"(original error: {original_error})"
                    )

        try:
            print("\r" + (" " * last_progress_len) + "\r", end="")
        except Exception:
            pass
        print_success(f"Saved {success}/{len(target_locales)} locales for {label}")

    input("\nPress Enter to continue...")
    return True
