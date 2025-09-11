# Repository Guidelines

## Project Structure & Module Organization

- `main.py`: CLI entrypoint and workflow orchestration.
- `app_store_client.py`: App Store Connect API wrapper (JWT auth, requests).
- `ai_providers.py`: Provider interfaces and concrete classes (Anthropic/OpenAI/Gemini).
- `config.py`: Loads/saves `config/` files (`api_keys.json`, `providers.json`, `instructions.txt`).
- `utils.py`: Shared helpers (limits, locales, logging helpers, exports).
- `ui.py`: Interactive UI wrapper used by workflows (TUI if available, falls back to stdin/stdout prompts).
- `ai_logger.py`: Helper for logging AI prompts/responses when enabled.
- `workflows/`: Task‑oriented commands invoked from `main.py`:
  - `workflows/release.py`: Create and translate What's New notes across platforms.
  - `workflows/translate.py`: Translate metadata fields for selected locales.
  - `workflows/update_localizations.py`: Fill missing localizations for existing versions.
  - `workflows/export_localizations.py`: Export current App Store metadata/localizations.
  - `workflows/copy.py`: Copy fields between locales/platforms.
  - `workflows/app_info.py`: Inspect app, versions, and localizations.
  - `workflows/full_setup.py`: First‑time setup helper for API keys and providers.
- `config/`: Created at first run; holds local configs (ignored by git).
- `logs/`, `existing_localizations/`: Generated artifacts; ignored by git.
- Tests (if added): place under `tests/`.

## Build, Test, and Development Commands

- Setup venv: `python3 -m venv .venv && source .venv/bin/activate`
- Install deps: `pip install -r requirements.txt`
- Run locally: `python3 main.py` (first run creates `config/` and prompts for keys)
- Optional tests: `pytest -q` (if `pytest` and `tests/` are added)

## Coding Style & Naming Conventions

- Python 3, 4‑space indentation; prefer type hints (`typing`) and docstrings.
- Naming: snake_case for functions/vars/files; PascalCase for classes; UPPER_SNAKE_CASE for constants.
- Keep modules small and focused; reuse utilities in `utils.py`.
- Follow existing CLI print helpers (`print_success/error/warning/info`).

## Workflows Overview

- Release: Select app and platforms, detect base language, choose source notes, select target locales, pick AI provider, translate, review, optionally re‑enter source and re‑translate, edit per‑locale, then apply to App Store Connect.
- Translate: Translate arbitrary metadata fields using the configured AI provider, enforcing per‑field limits from `utils.get_field_limit`.
- Update Localizations: Identify and fill missing fields for selected locales; similar flow to Translate, focused on gaps only.
- Export Localizations: Dump current metadata/localizations to files under `existing_localizations/`.
- Copy: Copy metadata fields across locales or platforms.
- App Info: Quick inspection of app, versions, and localization records.

## Release Workflow Details (workflows/release.py)

- Base detection: Determines base locale from existing version localizations and pre‑fills source notes with that locale’s What's New when present.
- Source selection: Use base notes, edit them, or enter custom source notes when base is empty.
- Target locales: Builds the union of locales missing What's New across selected platforms; user selects subset to fill.
- Provider selection: Uses configured provider from `ai_providers.py` (single provider auto‑selected).
- Translate loop: Generates translations with length cap (`whats_new` field limit; default 4000 chars) and shows a preview.
- Re‑enter source: New option lets you re‑enter the source release notes and re‑run translations if you’re not happy with the initial results (available in TUI and non‑TUI).
- Per‑locale edits: Optionally edit specific locales before applying.
- Apply + verify: Applies to each selected platform, also updating the base locale if it was empty; performs a best‑effort verification readback.

## TUI and Non‑TUI Behavior

- The `ui.py` layer provides checkbox/select/multiline prompts when available; otherwise falls back to standard input prompts with equivalent options:
  - Release “Next step” options: Apply all, Edit selected locales, Re‑enter source and re‑translate, Cancel.
  - Non‑TUI keys: `a` = apply, `e` = edit, `r` = re‑enter source, `c` = cancel.
  - Multiline editing uses your system editor (`$VISUAL`/`$EDITOR`) when possible, with sensible fallbacks (`nano`/`vi` on Unix, `notepad` on Windows). If both fail, a simple EOF‑terminated inline editor is used.

## Limits & Validation

- Field limits: `utils.get_field_limit` enforces max lengths (e.g., `whats_new`). Translated/edited text is truncated to the maximum length when needed.
- Locales: Human‑readable names resolved via `utils.APP_STORE_LOCALES`.

## Logs & Artifacts

- Logs: Under `logs/`, contain redacted runs and optional AI traces if enabled.
- Exports: `existing_localizations/` holds exported metadata; both folders are ignored by git.

## Configuration

- Files in `config/` control providers and keys:
  - `api_keys.json`: App Store Connect and AI provider API keys.
  - `providers.json`: Provider catalogue with `models`, `default_model`, optional `default_provider`, and optional `prompt_refinement` (a short phrase injected into translation prompts).
- In the CLI, open “⚙️  Configuration” to:
  - Reconfigure API keys.
  - Set the default AI provider (used as the suggested/one‑press choice in workflows).
  - Set the default model per provider (applied when initializing providers).
  - Set a global prompt refinement phrase used to guide translations.
- Workflows still allow picking a provider at runtime; when a default exists, you can confirm to use it or choose another.

## Prompt Refinement

- You can set a global refinement phrase in configuration; workflows also let you enter a per-run refinement. The phrase is appended to the system/prompt sent to providers (Anthropic/OpenAI/Gemini) as additional guidance.

## Testing Guidelines

- Framework: `pytest` recommended. Create `tests/test_*.py` covering workflows (translation, update, export) with mocked network.
- Avoid real API calls; stub `AppStoreConnectClient` and provider classes.
- Aim for coverage of limits (name/keywords length) and error paths.

## Commit & Pull Request Guidelines

- Commits: short, imperative subjects (e.g., "Add export feature", "Fix conflict handling"). Group related changes.
- PRs: include summary, motivation, before/after behavior, CLI output examples, and any screenshots if relevant. Link issues.
- Keep diffs focused; update README if user‑visible behavior changes.

## Security & Configuration Tips

- Never commit secrets: `config/api_keys.json`, `.p8` keys, `logs/`, and exports are already in `.gitignore` — keep them local.
- Do not paste API keys or app data into issues/PRs. Use redacted CLI output.
- Test against non‑production apps. Validate rate limits and handle 409 conflicts gracefully.
