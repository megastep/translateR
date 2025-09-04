"""
UI Helpers for TUI and fallback prompts.

Provides InquirerPy-based selectors and fallbacks, plus common pickers
like the App selector. Designed for reuse across workflows.
"""

from typing import List, Optional, Any, Dict
import os
import sys


class UI:
    def __init__(self):
        self._last_tui_reason: Optional[str] = None

    # --- TUI primitives ---
    def available(self) -> bool:
        if os.environ.get("TRANSLATER_NO_TUI"):
            return False
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            return False
        try:
            from InquirerPy import inquirer  # noqa: F401
            return True
        except Exception:
            return False

    def select(self, message: str, choices: List[dict], add_back: bool = False) -> Optional[str]:
        try:
            from InquirerPy import inquirer
        except Exception:
            return None
        try:
            if add_back:
                choices = ([{"name": "← Back", "value": "__back__"}] + list(choices))
            result = inquirer.select(message=message, choices=choices).execute()
            if result == "__back__":
                return None
            return result
        except Exception:
            return None

    def checkbox(self, message: str, choices: List[dict], add_back: bool = False) -> Optional[List[str]]:
        try:
            from InquirerPy import inquirer
        except Exception:
            return None
        try:
            if add_back:
                choices = ([{"name": "← Back", "value": "__back__"}] + list(choices))
            result = inquirer.checkbox(message=message, choices=choices).execute()
            if isinstance(result, list):
                if "__back__" in result and len(result) == 1:
                    return None
                result = [v for v in result if v != "__back__"]
            return result
        except Exception:
            return None

    def confirm(self, message: str, default: bool = True) -> Optional[bool]:
        try:
            from InquirerPy import inquirer
        except Exception:
            return None
        try:
            return bool(inquirer.confirm(message=message, default=default).execute())
        except Exception:
            return None

    def text(self, message: str) -> Optional[str]:
        try:
            from InquirerPy import inquirer
        except Exception:
            return None
        try:
            return inquirer.text(message=message).execute()
        except Exception:
            return None

    def editor(self, message: str, default: str = "") -> Optional[str]:
        try:
            from InquirerPy import inquirer
        except Exception:
            return None
        try:
            return inquirer.editor(message=message, default=default).execute()
        except Exception:
            return None

    # --- Composite prompts ---
    def prompt_multiline(self, prompt: str, initial: str = "") -> Optional[str]:
        if self.available():
            edited = self.editor(prompt, default=initial)
            if edited is not None:
                return edited
        # Fallback console EOF mode
        print(prompt)
        if initial:
            print("(Initial text shown below; edit and re-enter if needed)")
            print("-" * 40)
            print(initial)
            print("-" * 40)
        print("Enter text. Finish with a line containing only 'EOF'.")
        lines: List[str] = []  # type: ignore
        while True:
            try:
                line = input()
            except EOFError:
                break
            if line.strip() == 'EOF':
                break
            lines.append(line)
        text = "\n".join(lines).strip()
        return text if text else None

    # --- App picker ---
    def _fuzzy_app_picker(self, apps: List[Dict[str, Any]]) -> Optional[str]:
        # Fuzzy prompt without back to avoid accidental cancel selections
        try:
            from InquirerPy import inquirer
        except Exception:
            return None
        try:
            choices: List[dict] = [
                {"name": "Paste App ID manually...", "value": "__manual__"},
            ]
            for app in apps:
                attrs = app.get("attributes", {})
                name = attrs.get("name", "<unknown>")
                bundle_id = attrs.get("bundleId", "")
                label = name if not bundle_id else f"{name}  [{bundle_id}]"
                choices.append({"name": label, "value": app.get("id")})
            result = inquirer.fuzzy(message="Select app (type to filter)", choices=choices).execute()
            if result == "__manual__":
                app_id = input("Enter your App ID: ").strip()
                return app_id or None
            return result
        except Exception:
            return None

    def prompt_app_id(self, asc_client) -> Optional[str]:
        # Reset last reason
        self._last_tui_reason = None
        # Try TUI fuzzy first
        if self.available():
            try:
                response = asc_client.get_apps(limit=200)
                apps = response.get("data", [])
            except Exception as e:
                self._last_tui_reason = f"failed to fetch apps list: {e}"
                apps = []
            if apps:
                res = self._fuzzy_app_picker(apps)
                if res is not None:
                    return res

        # Fallback to pager
        page_size = 25
        pages: List[Dict[str, Any]] = []
        page_index = 0
        cursor: Optional[str] = None
        try:
            while True:
                if page_index >= len(pages):
                    resp = asc_client.get_apps_page(limit=page_size, cursor=cursor)
                    data = resp.get("data", [])
                    next_cursor = resp.get("next_cursor")
                    items = []
                    for app in data:
                        attrs = app.get("attributes", {})
                        name = attrs.get("name", "<unknown>")
                        bundle_id = attrs.get("bundleId", "")
                        items.append((app.get("id"), name, bundle_id))
                    pages.append({"items": items, "next_cursor": next_cursor})
                    if page_index == 0 and not items:
                        print("No apps found in your App Store Connect account")
                        app_id = input("Enter your App ID: ").strip()
                        return app_id or None
                current = pages[page_index]
                items = current["items"]
                total_on_page = len(items)
                print()
                print(f"Your Apps (page {page_index + 1}):")
                for i, (_id, name, bundle_id) in enumerate(items, 1):
                    label = f"{i:2d}. {name}"
                    if bundle_id:
                        label += f"  [{bundle_id}]"
                    print(label)
                print()
                options = []
                if current.get("next_cursor"):
                    options.append("n=next")
                if page_index > 0:
                    options.append("p=prev")
                options.append("q=cancel")
                nav = " | ".join(options)
                prompt = f"Select app (1-{total_on_page}), paste App ID, or {nav}: "
                sel = input(prompt).strip()
                if not sel:
                    print("Please select a number, navigate, or paste an App ID.")
                    continue
                if sel.lower() == 'n' and current.get("next_cursor"):
                    cursor = current["next_cursor"]
                    page_index += 1
                    continue
                if sel.lower() == 'p' and page_index > 0:
                    page_index -= 1
                    continue
                if sel.lower() == 'q':
                    return None
                if sel.isdigit():
                    n = int(sel)
                    if 1 <= n <= total_on_page:
                        return items[n - 1][0]
                    print("Invalid selection number.")
                    continue
                return sel
        except Exception as e:
            print(f"Could not fetch apps list: {e}")
            app_id = input("Enter your App ID: ").strip()
            return app_id or None

