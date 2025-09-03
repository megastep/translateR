# Repository Guidelines

## Project Structure & Module Organization

- `main.py`: CLI entrypoint and workflow orchestration.
- `app_store_client.py`: App Store Connect API wrapper (JWT auth, requests).
- `ai_providers.py`: Provider interfaces and concrete classes (Anthropic/OpenAI/Gemini).
- `config.py`: Loads/saves `config/` files (`api_keys.json`, `providers.json`, `instructions.txt`).
- `utils.py`: Shared helpers (limits, locales, logging helpers, exports).
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
