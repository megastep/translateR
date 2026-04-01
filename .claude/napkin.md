# Napkin

## Corrections
| Date | Source | What Went Wrong | What To Do Instead |
|------|--------|----------------|-------------------|
| 2026-02-13 | self | Started repository inspection before checking napkin state for this repo | Initialize/read `.claude/napkin.md` first at session start in this repo |

## User Preferences
- Use `create-plan` output format when requesting plans, then implement directly when asked.
- Prioritize complete implementation over partial scaffolding.

## Patterns That Work
- Stub workflow dependencies by constructing a lightweight fake `cli` object with `ui`, `asc_client`, `ai_manager`, and `config` fields.
- Use hermetic tests with monkeypatched `requests` and temp directories for config/filesystem behavior.

## Patterns That Don't Work
- Assuming this worktree has a branch name; verify and create a `codex/` branch when detached.

## Domain Notes
- 2026-04-01: Apple added 11 App Store metadata languages (50 total). Updated `APP_STORE_LOCALES` using ISO 639–1-style codes (`bn`, `gu`, …) to match existing `hi`; Apple’s “locale shortcodes” DocC article still lists 39 rows—verify in App Store Connect UI if API rejects a locale.
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
