# Napkin

## Corrections
| Date | Source | What Went Wrong | What To Do Instead |
|------|--------|----------------|-------------------|
| 2026-02-13 | self | Started repository inspection before checking napkin state for this repo | Initialize/read `.claude/napkin.md` first at session start in this repo |
| 2026-04-02 | self | Interpreted ASC `ENTITY_ERROR.ATTRIBUTE.INVALID` for locale `sl` as “language unsupported” and started removing newer UI locales | When ASC UI and API disagree, first verify the API shortcode; Slovenian is available but the API expects `sl-SI`, not bare `sl` |

## User Preferences
- Use `create-plan` output format when requesting plans, then implement directly when asked.
- Prioritize complete implementation over partial scaffolding.

## Patterns That Work
- Stub workflow dependencies by constructing a lightweight fake `cli` object with `ui`, `asc_client`, `ai_manager`, and `config` fields.
- Use hermetic tests with monkeypatched `requests` and temp directories for config/filesystem behavior.
- Built-in preset JSON should use the canonical locale codes from `utils.APP_STORE_LOCALES`; when locale support adds region-qualified codes like `bn-BD` or `sl-SI`, update preset files and cover raw JSON keys with a test so bundled presets do not drift behind runtime normalization.
- App Store Connect `POST /v1/appStoreVersionLocalizations` treats `409` as a request-entity conflict; recover by refreshing version localizations and updating an existing locale instead of retrying the same POST.
- OpenAI translation retries must wrap every POST path, including the second pass after character-limit re-translation, or transient 429/5xx failures reappear on the retry path.
- ASC locale normalization should treat CLI aliases case-insensitively and null-safe any `attributes` access when building localization maps.
- For bulk IAP translation, share locale-scope and target-language prompts across IAPs only when their base locale and effective locale-option sets match; otherwise re-prompt per materially different group.
- For bulk subscription translation, use the same grouping rule as IAPs; never treat the first selected subscription as a proxy for all selected items when locale availability may differ.
- When a workflow is in “missing/new locales only” mode, preselect the full offered locale list rather than app-locales-only defaults so Enter/confirm applies to every newly creatable locale.
- In Release mode, preserve the default “fill missing notes only” path, but offer an explicit overwrite toggle so locales with existing `whatsNew` can be reselected and updated intentionally.
- In Release mode, applying a preset should always update the base locale text as well, even if the base already has notes and even if no non-base locale needs changes; cover both paths with workflow tests.
- In Release mode, preset preview should include the base locale row and show the base preset text before target-locale previews so users can verify exactly what will be written to `en-US`.

## Patterns That Don't Work
- Assuming this worktree has a branch name; verify and create a `codex/` branch when detached.

## Domain Notes
- Project is a Python CLI orchestrating many workflows via `run(cli)` entrypoints.
- Network dependencies are App Store Connect and AI provider HTTP APIs; tests must mock both.
| 2026-02-13 | self | Used `apply_patch` through `exec_command` wrapper | Use the dedicated `apply_patch` tool directly for patch hunks |
| 2026-02-13 | self | Assumed OpenAI request payload captured by tests stayed immutable across retries | Deep-copy captured payloads in mocks because provider mutates request dict (e.g., removes `seed`) |
| 2026-02-13 | self | Assumed localization update issues a direct PATCH only | Account for prefetch GET behavior in `update_app_store_version_localization` tests |
| 2026-02-13 | self | Assumed local environment would allow installing `pytest-cov` for coverage validation | Treat coverage command as CI-validated when local package install is permission-blocked |
| 2026-02-13 | self | Fake ASC client required explicit methods for every new workflow API call | Use `FakeASC.__getattr__` fallback to record/respond to arbitrary ASC methods in workflow tests |
| 2026-02-13 | self | Coverage runs repeatedly surfaced a deprecation warning from `release_presets.py` (`datetime.utcnow`) | Track warning cleanup separately; keep tests warning-tolerant unless warning policy changes |
| 2026-02-13 | self | Scoped coverage with `--cov=workflows/release.py` style module paths, which yields no data warnings | Use import-style module targets (e.g., `--cov=workflows.release`, `--cov=main`) or `--cov=.` |
| 2026-02-13 | self | Non-TUI workflow tests undercounted `input()` prompts and raised `StopIteration` | Provide a conservative extra trailing blank input in iterator-driven prompt mocks |
| 2026-02-13 | self | Non-TUI release tests forgot that platform-selection prompt runs before source/locale prompts | Model full prompt sequence in tests and supply enough ordered `input()` answers |

- 2026-02-13: In tests, avoid monkeypatching `sys.stdout.write` globally; gate failures to progress-line writes only (e.g., strings starting with ``) so print helpers still work.
- 2026-02-13: After excluding `tests/` from coverage, baseline project coverage was 88.22%; set CI `--cov-fail-under` to a realistic enforced floor based on measured non-test coverage, then iterate upward with new tests.
- 2026-02-13: CI can run a merged PR ref where module attributes differ from local branch import surface; for monkeypatched optional globals in tests, use `monkeypatch.setattr(..., raising=False)` to avoid false negatives.
- 2026-02-13: Keep long test modules under ~400 lines by splitting by workflow concern (e.g., base/release/promo/non-TUI variants) to reduce merge conflicts and improve maintainability.
- 2026-02-13: High-yield coverage gains can come from directly unit-testing prompt helper functions with small UI stubs instead of only end-to-end workflow runs.
- 2026-02-13: High-yield coverage gains can come from directly unit-testing prompt helper functions with small UI stubs instead of only end-to-end workflow runs.
- 2026-02-13: For release workflow coverage, target early source-selection branches (non-TUI `n/e/c/p` paths) to unlock multiple low-level condition lines with minimal fixture setup.
- 2026-02-13: For release workflow coverage, target early source-selection branches (non-TUI `n/e/c/p` paths) to unlock multiple low-level condition lines with minimal fixture setup.
