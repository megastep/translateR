"""Shared helper utilities for app event localization translation workflow."""

from __future__ import annotations

import time
from typing import Callable, Dict

from utils import APP_STORE_LOCALES, format_progress, print_error


def get_event_localizations_with_fallback(asc, event_id: str):
    """Fetch app event localizations with an include fallback when needed."""
    loc_resp = asc.get_app_event_localizations(event_id)
    localizations = loc_resp.get("data", []) if isinstance(loc_resp, dict) else []
    if localizations:
        return localizations

    # Some accounts intermittently omit attributes on /localizations;
    # include=localizations is capped at 50 but enough for supported locales.
    try:
        fallback = asc.get_app_event(event_id, include_localizations=True)
        return [
            item
            for item in (fallback.get("included", []) if isinstance(fallback, dict) else [])
            if item.get("type") == "appEventLocalizations"
        ]
    except Exception:
        return []


def build_event_locale_id_map(localizations) -> Dict[str, str]:
    """Build locale->localization_id map from app event localization payloads."""
    locale_ids: Dict[str, str] = {}
    for localization in localizations:
        attrs = localization.get("attributes", {}) or {}
        loc_code = (attrs.get("locale") or "").strip()
        loc_id = localization.get("id")
        if loc_code and loc_id:
            locale_ids[loc_code] = loc_id
    return locale_ids


def save_app_event_localizations(
    asc,
    event_id: str,
    results: Dict[str, Dict[str, str]],
    target_locales,
    existing_locale_ids: Dict[str, str],
    find_existing_locale_id: Callable[[Dict[str, str], str], str],
    has_validation_error: Callable[[Exception], bool],
    debug: Callable[[str], None],
    debug_http_error: Callable[[str, Exception], None],
) -> int:
    """Persist translated app event localizations with 409 recovery behavior."""

    total_targets = len(target_locales)
    completed = 0
    saved = 0
    last_progress_len = 0

    def _render_progress(done: int, label: str) -> None:
        nonlocal last_progress_len
        try:
            line = format_progress(done, total_targets, label)
            pad = max(0, last_progress_len - len(line))
            print("\r" + line + (" " * pad), end="")
            last_progress_len = len(line)
        except Exception:
            pass

    try:
        line = format_progress(0, total_targets, "Saving locales...")
        print(line, end="\r")
        last_progress_len = len(line)
    except Exception:
        pass

    def _refresh_locale_ids() -> Dict[str, str]:
        try:
            refreshed_map: Dict[str, str] = {}
            refreshed = asc.get_app_event_localizations(event_id)
            refreshed_list = refreshed.get("data", []) if isinstance(refreshed, dict) else []
            refreshed_map.update(build_event_locale_id_map(refreshed_list))
            if not refreshed_map:
                fallback = asc.get_app_event(event_id, include_localizations=True)
                fallback_list = [
                    item
                    for item in (fallback.get("included", []) if isinstance(fallback, dict) else [])
                    if item.get("type") == "appEventLocalizations"
                ]
                refreshed_map.update(build_event_locale_id_map(fallback_list))
            existing_locale_ids.clear()
            existing_locale_ids.update(refreshed_map)
            debug(f"refresh event_id={event_id} locales={sorted(refreshed_map.keys())}")
            return refreshed_map
        except Exception:
            return existing_locale_ids

    for locale, data in results.items():
        loc_id = find_existing_locale_id(existing_locale_ids, locale)
        debug(f"save locale={locale} loc_id={loc_id or '(none)'}")
        saved_this_locale = False

        try:
            if loc_id:
                asc.update_app_event_localization(
                    loc_id,
                    name=data.get("name"),
                    short_description=data.get("shortDescription"),
                    long_description=data.get("longDescription"),
                )
            else:
                time.sleep(0.25)
                asc.create_app_event_localization(
                    event_id,
                    locale,
                    name=data.get("name"),
                    short_description=data.get("shortDescription"),
                    long_description=data.get("longDescription"),
                )
                _refresh_locale_ids()

            saved += 1
            completed += 1
            saved_this_locale = True
            if loc_id:
                existing_locale_ids[locale] = loc_id
            _render_progress(completed, f"Saved {APP_STORE_LOCALES.get(locale, locale)}")
        except Exception as err:
            if "409" in str(err) and not has_validation_error(err):
                debug_http_error(f"409 while saving locale={locale}", err)
                recovered = False
                for attempt in range(4):
                    try:
                        refreshed_map = _refresh_locale_ids()
                        new_id = find_existing_locale_id(refreshed_map, locale)
                        debug(
                            f"recovery attempt={attempt + 1} locale={locale} new_id={new_id or '(none)'}"
                        )
                        if new_id:
                            try:
                                asc.update_app_event_localization(
                                    new_id,
                                    name=data.get("name"),
                                    short_description=data.get("shortDescription"),
                                    long_description=data.get("longDescription"),
                                )
                                saved += 1
                                completed += 1
                                existing_locale_ids[locale] = new_id
                                _render_progress(
                                    completed,
                                    f"Saved {APP_STORE_LOCALES.get(locale, locale)}",
                                )
                                recovered = True
                                break
                            except Exception as upd_err:
                                if "409" in str(upd_err):
                                    debug_http_error(
                                        f"409 while updating locale={locale} id={new_id}",
                                        upd_err,
                                    )
                                    try:
                                        fetched = asc.get_app_event_localization(new_id)
                                        fetched_attrs = (
                                            fetched.get("data", {}).get("attributes", {})
                                            if isinstance(fetched, dict)
                                            else {}
                                        )
                                        if (
                                            fetched_attrs.get("name") == data.get("name")
                                            and fetched_attrs.get("shortDescription")
                                            == data.get("shortDescription")
                                            and fetched_attrs.get("longDescription")
                                            == data.get("longDescription")
                                        ):
                                            saved += 1
                                            completed += 1
                                            existing_locale_ids[locale] = new_id
                                            _render_progress(
                                                completed,
                                                f"Saved {APP_STORE_LOCALES.get(locale, locale)}",
                                            )
                                            recovered = True
                                            break
                                    except Exception:
                                        pass
                        time.sleep(0.4 * (attempt + 1))
                    except Exception:
                        time.sleep(0.4 * (attempt + 1))

                if recovered:
                    saved_this_locale = True

            if saved_this_locale:
                continue

            language_name = APP_STORE_LOCALES.get(locale, locale)
            debug_http_error(f"failed locale={locale}", err)
            print_error(f"  ❌ Failed to save {language_name}: {err}")

    try:
        print("\r" + (" " * last_progress_len) + "\r", end="")
    except Exception:
        pass

    return saved
