"""
Release note presets storage and utilities.

Allows loading built-in presets bundled with the application as well as
user-defined presets stored under config/presets. Presets are simple JSON
files containing localized strings for all App Store locales.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from utils import APP_STORE_LOCALES


REPO_ROOT = Path(__file__).resolve().parent
BUILTIN_PRESETS_DIR = REPO_ROOT / "presets"
USER_PRESETS_DIR = REPO_ROOT / "config" / "presets"
PRESET_FILE_EXTENSION = ".json"


@dataclass
class ReleaseNotePreset:
    preset_id: str
    name: str
    translations: Dict[str, str]
    path: Path
    built_in: bool
    description: Optional[str] = None

    def get_translation(self, locale: str) -> str:
        """Return translation for locale, falling back to English variants."""
        if locale in self.translations:
            return self.translations[locale]
        for fallback in ("en-US", "en-GB", "en-AU", "en-CA"):
            val = self.translations.get(fallback)
            if val:
                return val
        # Fall back to first available translation or empty string
        return next(iter(self.translations.values()), "")


def _normalize_translations(raw: Dict[str, str]) -> Dict[str, str]:
    """Ensure every locale has a non-null translation using sensible fallbacks."""
    sanitized = {k: (v or "").strip() for k, v in raw.items() if isinstance(v, str)}
    primary_fallback = (
        sanitized.get("en-US")
        or sanitized.get("en-GB")
        or sanitized.get("en-AU")
        or sanitized.get("en-CA")
        or next(iter(sanitized.values()), "")
    )
    result: Dict[str, str] = {}
    for locale in APP_STORE_LOCALES.keys():
        if locale in sanitized and sanitized[locale]:
            result[locale] = sanitized[locale]
            continue
        fallback = sanitized.get("en-US") or sanitized.get("en-GB") or sanitized.get("en-AU") or sanitized.get("en-CA")
        result[locale] = fallback or primary_fallback or ""
    return result


def _slugify(value: str) -> str:
    """Generate filesystem-friendly identifier."""
    slug_chars: List[str] = []
    value = value.strip().lower()
    for ch in value:
        if ch.isalnum():
            slug_chars.append(ch)
        elif ch in (" ", "-", "_"):
            if not slug_chars or slug_chars[-1] != "-":
                slug_chars.append("-")
    slug = "".join(slug_chars).strip("-")
    return slug or "preset"


def ensure_user_directory() -> Path:
    USER_PRESETS_DIR.mkdir(parents=True, exist_ok=True)
    return USER_PRESETS_DIR


def _load_preset_from_path(path: Path, built_in: bool) -> Optional[ReleaseNotePreset]:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None

    translations_raw = data.get("translations")
    if not isinstance(translations_raw, dict):
        return None
    translations = _normalize_translations(translations_raw)

    preset_id = data.get("id") or path.stem
    name = data.get("name") or preset_id.replace("-", " ").title()
    description = data.get("description")

    return ReleaseNotePreset(
        preset_id=preset_id,
        name=name,
        translations=translations,
        path=path,
        built_in=built_in,
        description=description,
    )


def list_presets() -> List[ReleaseNotePreset]:
    """Return all available presets (built-in + user-defined)."""
    presets: Dict[str, ReleaseNotePreset] = {}
    for directory, built_in in (
        (BUILTIN_PRESETS_DIR, True),
        (USER_PRESETS_DIR, False),
    ):
        if not directory.exists():
            continue
        for path in sorted(directory.glob(f"*{PRESET_FILE_EXTENSION}")):
            preset = _load_preset_from_path(path, built_in=built_in)
            if not preset:
                continue
            presets[preset.preset_id] = preset
    return sorted(presets.values(), key=lambda p: (0 if p.built_in else 1, p.name.lower()))


def get_preset(preset_id: str) -> Optional[ReleaseNotePreset]:
    """Return preset by identifier."""
    for preset in list_presets():
        if preset.preset_id == preset_id:
            return preset
    return None


def preset_exists(preset_id: str) -> bool:
    return get_preset(preset_id) is not None


def _build_serializable_payload(
    preset_id: str,
    name: str,
    translations: Dict[str, str],
    description: Optional[str] = None,
) -> Dict[str, object]:
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    payload: Dict[str, object] = {
        "id": preset_id,
        "name": name,
        "created_at": now,
        "translations": translations,
    }
    if description:
        payload["description"] = description
    return payload


def save_user_preset(
    name: str,
    translations: Dict[str, str],
    description: Optional[str] = None,
    preset_id: Optional[str] = None,
) -> Tuple[ReleaseNotePreset, Path]:
    """Persist a user-defined preset and return it."""
    ensure_user_directory()
    if not preset_id:
        preset_id = _slugify(name)

    preset_path = USER_PRESETS_DIR / f"{preset_id}{PRESET_FILE_EXTENSION}"
    # Fill in missing locales explicitly before saving
    normalized_translations = _normalize_translations(translations)
    payload = _build_serializable_payload(preset_id, name, normalized_translations, description)
    with preset_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")

    preset = ReleaseNotePreset(
        preset_id=preset_id,
        name=name,
        translations=normalized_translations,
        path=preset_path,
        built_in=False,
        description=description,
    )
    return preset, preset_path


def delete_user_preset(preset_id: str) -> bool:
    """Delete a user-created preset."""
    ensure_user_directory()
    target = USER_PRESETS_DIR / f"{preset_id}{PRESET_FILE_EXTENSION}"
    if not target.is_file():
        return False
    try:
        target.unlink()
        return True
    except Exception:
        return False


def generate_preset_id(name: str) -> str:
    """Return slug/id for a preset name."""
    return _slugify(name)


def builtin_presets_available() -> bool:
    """Return True if at least one built-in preset exists."""
    return any(BUILTIN_PRESETS_DIR.glob(f"*{PRESET_FILE_EXTENSION}"))
