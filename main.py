#!/usr/bin/env python3
"""
TranslateR - App Store Connect Localization Automation Tool

A powerful CLI tool for automating App Store Connect localizations 
with multi-AI provider support.

Author: Emre Ertunç
Contact: emre@ertunc.com
Repository: https://github.com/emreertunc/translater
"""

import sys
import os
import time
import re
from typing import List, Optional, Any, Dict
from pathlib import Path

# Modularized UI and workflows
from ui import UI
from workflows.release import run as release_run
from workflows.translate import run as translate_run
from workflows.update_localizations import run as update_run
from workflows.copy import run as copy_run
from workflows.full_setup import run as full_setup_run
from workflows.app_info import run as app_info_run
from workflows.export_localizations import run as export_run

from config import ConfigManager
from app_store_client import AppStoreConnectClient
from ai_providers import AIProviderManager, AnthropicProvider, OpenAIProvider, GoogleGeminiProvider
from utils import (
    APP_STORE_LOCALES,
    detect_base_language,
    print_success, print_error, print_warning, print_info, format_progress,
    resolve_private_key_path, DEFAULT_APPSTORE_P8_DIR
)


class TranslateRCLI:
    """Main CLI interface for TranslateR application."""
    
    def __init__(self):
        self.config = ConfigManager()
        self.asc_client = None
        self.ai_manager = AIProviderManager()
        self.ui = UI()
        self.setup_ai_providers()
    
    def setup_ai_providers(self):
        """Initialize AI providers from configuration."""
        try:
            providers_config = self.config.load_providers()
            
            # Setup Anthropic
            anthropic_key = self.config.get_ai_provider_key("anthropic")
            if anthropic_key:
                default_model = providers_config.get("anthropic", {}).get("default_model", "claude-sonnet-4-20250514")
                anthropic = AnthropicProvider(anthropic_key, default_model)
                self.ai_manager.add_provider("anthropic", anthropic)
            
            # Setup OpenAI
            openai_key = self.config.get_ai_provider_key("openai")
            if openai_key:
                default_model = providers_config.get("openai", {}).get("default_model", "gpt-4.1")
                openai = OpenAIProvider(openai_key, default_model)
                self.ai_manager.add_provider("openai", openai)
            
            # Setup Google Gemini
            google_key = self.config.get_ai_provider_key("google")
            if google_key:
                default_model = providers_config.get("google", {}).get("default_model", "gemini-2.5-flash")
                google = GoogleGeminiProvider(google_key, default_model)
                self.ai_manager.add_provider("google", google)
                
        except Exception as e:
            print_error(f"Error setting up AI providers: {e}")
    
    def setup_app_store_client(self):
        """Initialize App Store Connect client."""
        asc_config = self.config.get_app_store_config()
        
        if not asc_config:
            print_error("App Store Connect configuration not found.")
            return self.setup_wizard()
        
        try:
            # Resolve and read private key file (supports ~/.appstoreconnect/private_keys)
            resolved_key_path = resolve_private_key_path(
                key_id=asc_config["key_id"],
                configured_path=asc_config.get("private_key_path")
            )
            with open(resolved_key_path, "r") as f:
                private_key = f.read()
            
            self.asc_client = AppStoreConnectClient(
                key_id=asc_config["key_id"],
                issuer_id=asc_config["issuer_id"],
                private_key=private_key
            )
            
            # Test the connection
            self.asc_client.get_apps()
            print_success("App Store Connect client initialized successfully")
            return True
            
        except Exception as e:
            print_error(f"Failed to initialize App Store Connect client: {e}")
            return self.setup_wizard()
    
    def setup_wizard(self):
        """Guide user through initial setup."""
        print_info("Setting up TranslateR for first time use...")
        print()
        
        # App Store Connect setup
        print("📱 App Store Connect Configuration")
        print("You need your API credentials from App Store Connect:")
        print("1. Go to App Store Connect > Users and Access > Integrations")
        print("2. Create a new API key with App Manager role")
        print("3. Download the .p8 private key file")
        print()
        
        # Discover existing keys in default directory
        keys_dir = DEFAULT_APPSTORE_P8_DIR
        existing_keys: List[Path] = []
        try:
            if keys_dir.exists():
                existing_keys = sorted(keys_dir.glob("*.p8"))
        except Exception:
            existing_keys = []

        selected_path: str = ""
        if existing_keys:
            print()
            print(f"Found {len(existing_keys)} key(s) in {keys_dir}:")
            for idx, p in enumerate(existing_keys, 1):
                print(f"  {idx}. {p.name}")
            print("  0. Enter a custom path")

            choice = input("Select a key (1-{}), 0 for custom, or Enter to skip: ".format(len(existing_keys))).strip()
            if choice.isdigit():
                n = int(choice)
                if 1 <= n <= len(existing_keys):
                    selected_path = str(existing_keys[n - 1])
                elif n == 0:
                    # Will prompt for custom below
                    pass
            elif choice:
                print_warning("Invalid selection; continuing with custom/default option.")

        # If no selection yet, allow manual entry with generic default hint
        default_hint = DEFAULT_APPSTORE_P8_DIR
        if not selected_path:
            entered = input(
                f"Enter path to your .p8 private key file (leave blank to use default in {default_hint}): "
            ).strip()
            selected_path = entered  # may be blank; resolver will handle

        # Try to guess Key ID from selected filename
        key_id_guess = None
        if selected_path:
            try:
                name = Path(os.path.expanduser(selected_path)).name
                m = re.match(r"AuthKey_([A-Za-z0-9]+)\.p8$", name)
                if m:
                    key_id_guess = m.group(1)
            except Exception:
                key_id_guess = None

        # Determine API Key ID (auto-detect from filename when possible)
        if key_id_guess:
            print_info(f"Detected API Key ID: {key_id_guess}")
            key_id = key_id_guess
        else:
            key_id = input("Enter your API Key ID: ").strip()
        if not key_id:
            print_error("API Key ID is required")
            return False

        # Prompt for Issuer ID
        issuer_id = input("Enter your Issuer ID: ").strip()
        if not issuer_id:
            print_error("Issuer ID is required")
            return False

        # Validate resolved key path (blank allowed if default exists)
        try:
            _ = resolve_private_key_path(key_id=key_id, configured_path=selected_path or None)
        except Exception as e:
            print_error(str(e))
            return False
        
        # Save App Store Connect config
        api_keys = self.config.load_api_keys()
        api_keys["app_store_connect"] = {
            "key_id": key_id,
            "issuer_id": issuer_id,
            "private_key_path": selected_path  # may be blank; resolved at runtime
        }
        
        print()
        print("🤖 AI Provider Configuration")
        print("Configure at least one AI provider for translations:")
        
        # AI providers setup
        providers = ["anthropic", "openai", "google"]
        provider_names = {
            "anthropic": "Anthropic Claude",
            "openai": "OpenAI GPT", 
            "google": "Google Gemini"
        }
        
        for provider in providers:
            response = input(f"Do you want to configure {provider_names[provider]}? (y/n): ").strip().lower()
            if response in ['y', 'yes']:
                api_key = input(f"Enter {provider_names[provider]} API key: ").strip()
                if api_key:
                    api_keys["ai_providers"][provider] = api_key
        
        # Check if at least one AI provider is configured
        if not any(api_keys["ai_providers"].values()):
            print_error("You must configure at least one AI provider!")
            return False
        
        # Save configuration
        self.config.save_api_keys(api_keys)
        print_success("Configuration saved successfully!")
        
        # Reinitialize clients
        self.setup_ai_providers()
        return self.setup_app_store_client()

    def prompt_app_id(self) -> Optional[str]:
        """List available apps and let the user pick one or paste an ID."""
        return self.ui.prompt_app_id(self.asc_client)

    def release_mode(self):
        """Release Mode wrapper."""
        return release_run(self)

    def show_main_menu(self):
        """Display main menu and handle user choice."""
        # TUI-based main menu when available
        if self.ui.available():
            choices = [
                {"name": "🌐 Translation Mode - Translate to new languages", "value": "1"},
                {"name": "📝 Release Mode - Create release notes for new version", "value": "2"},
                {"name": "🔄 Update Mode - Update existing localizations", "value": "3"},
                {"name": "📋 Copy Mode - Copy from previous version", "value": "4"},
                {"name": "🚀 Full Setup Mode - Complete localization setup", "value": "5"},
                {"name": "📱 App Name & Subtitle Mode - Translate app name and subtitle", "value": "6"},
                {"name": "📄 Export Localizations - Export existing localizations to file", "value": "7"},
                {"name": "⚙️  Configuration - Manage API keys and settings", "value": "8"},
                {"name": "❌ Exit", "value": "9"},
            ]
            choice = self.ui.select("TranslateR — Choose your workflow", choices) or ""
        else:
            print()
            print("🌍 TranslateR - Choose your workflow:")
            print("1. 🌐 Translation Mode - Translate to new languages")
            print("2. 📝 Release Mode - Create release notes for new version")
            print("3. 🔄 Update Mode - Update existing localizations")
            print("4. 📋 Copy Mode - Copy from previous version") 
            print("5. 🚀 Full Setup Mode - Complete localization setup")
            print("6. 📱 App Name & Subtitle Mode - Translate app name and subtitle")
            print("7. 📄 Export Localizations - Export existing localizations to file")
            print("8. ⚙️  Configuration - Manage API keys and settings")
            print("9. ❌ Exit")
            print()
            choice = input("Select an option (1-9): ").strip()

        if choice == "1":
            return translate_run(self)
        elif choice == "2":
            return release_run(self)
        elif choice == "3":
            return update_run(self)
        elif choice == "4":
            return copy_run(self)
        elif choice == "5":
            return full_setup_run(self)
        elif choice == "6":
            return app_info_run(self)
        elif choice == "7":
            return export_run(self)
        elif choice == "8":
            return self.configuration_mode()
        elif choice == "9":
            print_info("Thank you for using TranslateR!")
            return False
        else:
            print_error("Invalid choice. Please select 1-9.")
            return True
    
    def translation_mode(self):
        """Handle translation workflow."""
        return translate_run(self)

    def _translate_app_info(self, app_id: str, target_locales: List[str], provider):
        """Helper method to translate app name and subtitle for given locales."""
        try:
            # Find primary app info ID
            app_info_id = self.asc_client.find_primary_app_info_id(app_id)
            if not app_info_id:
                print_error("Could not find app info. App name & subtitle translation skipped.")
                return
            
            # Get existing localizations
            existing_localizations = self.asc_client.get_app_info_localizations(app_info_id)
            existing_locales = []
            localization_map = {}
            
            for loc in existing_localizations.get("data", []):
                locale = loc["attributes"]["locale"]
                existing_locales.append(locale)
                localization_map[locale] = loc["id"]
            
            # Get base language data
            base_locale = detect_base_language(existing_localizations.get("data", []))
            if not base_locale:
                print_error("No base language found for app info. Skipping app name & subtitle.")
                return
            
            base_localization_id = localization_map[base_locale]
            base_data = self.asc_client.get_app_info_localization(base_localization_id)
            base_attrs = base_data.get("data", {}).get("attributes", {})
            
            base_name = base_attrs.get("name", "")
            base_subtitle = base_attrs.get("subtitle", "")
            
            if not base_name and not base_subtitle:
                print_warning("No name or subtitle found in base language. Skipping app name & subtitle.")
                return
            
            print()
            print_info(f"Translating app name & subtitle from {APP_STORE_LOCALES.get(base_locale, base_locale)}")
            if base_name:
                print(f"📱 Name: {base_name}")
            if base_subtitle:
                print(f"📝 Subtitle: {base_subtitle}")
            
            success_count = 0
            
            for i, target_locale in enumerate(target_locales, 1):
                language_name = APP_STORE_LOCALES.get(target_locale, target_locale)
                print()
                print(format_progress(i, len(target_locales), f"Translating {language_name} app info"))
                
                try:
                    translated_data = {}
                    
                    # Translate name
                    if base_name:
                        print(f"  • Translating app name...")
                        translated_name = provider.translate(
                            base_name,
                            language_name,
                            max_length=30
                        )
                        if len(translated_name) > 30:
                            translated_name = translated_name[:30]
                        translated_data["name"] = translated_name
                    
                    # Translate subtitle
                    if base_subtitle:
                        print(f"  • Translating subtitle...")
                        translated_subtitle = provider.translate(
                            base_subtitle,
                            language_name,
                            max_length=30
                        )
                        if len(translated_subtitle) > 30:
                            translated_subtitle = translated_subtitle[:30]
                        translated_data["subtitle"] = translated_subtitle
                    
                    # Create or update app info localization
                    if target_locale in existing_locales:
                        # Update existing
                        self.asc_client.update_app_info_localization(
                            localization_map[target_locale],
                            **translated_data
                        )
                    else:
                        # Create new
                        self.asc_client.create_app_info_localization(
                            app_info_id,
                            target_locale,
                            **translated_data
                        )
                    
                    print_success(f"  ✅ {language_name} app info translation completed")
                    success_count += 1
                    time.sleep(1)  # Rate limiting
                    
                except Exception as e:
                    print_error(f"  ❌ Failed to translate {language_name} app info: {str(e)}")
                    continue
            
            print()
            print_success(f"App name & subtitle translation completed! {success_count}/{len(target_locales)} languages processed")
            
        except Exception as e:
            print_error(f"App info translation failed: {str(e)}")
    
    def update_mode(self):
        """Handle update existing localizations workflow."""
        return update_run(self)
    
    def copy_mode(self):
        """Handle copy workflow."""
        return copy_run(self)

    def full_setup_mode(self):
        """Handle full setup workflow."""
        return full_setup_run(self)
    
    def app_name_subtitle_mode(self):
        """Handle app name and subtitle translation workflow."""
        return app_info_run(self)
    
    def export_localizations_mode(self):
        """Handle export existing localizations workflow."""
        return export_run(self)
    
    def configuration_mode(self):
        """Handle configuration management."""
        print_info("Configuration Mode - Manage your settings")
        
        print()
        print("Available AI Providers:")
        providers = self.ai_manager.list_providers()
        if providers:
            for provider in providers:
                print(f"✅ {provider}")
        else:
            print("❌ No AI providers configured")
        
        print()
        print("App Store Connect:", "✅ Configured" if self.asc_client else "❌ Not configured")
        
        print()
        reconfigure = input("Do you want to reconfigure settings? (y/n): ").strip().lower()
        if reconfigure in ['y', 'yes']:
            return self.setup_wizard()
        
        return True
    
    def show_logo(self):
        """Display ASCII art logo."""
        print()
        print("  ╔════════════════════════════════════════════════════════╗")
        print("  ║                                                        ║")
        print("  ║      ████████ ██████   █████  ███   ██ ███████         ║")
        print("  ║         ██    ██   ██ ██   ██ ████  ██ ██              ║")
        print("  ║         ██    ██████  ███████ ██ ██ ██ ███████         ║")
        print("  ║         ██    ██   ██ ██   ██ ██  ████      ██         ║")
        print("  ║         ██    ██   ██ ██   ██ ██   ███ ███████         ║")
        print("  ║                                                        ║")
        print("  ║      ██       █████  ████████ ███████ \033[38;5;208m██████\033[0m           ║")
        print("  ║      ██      ██   ██    ██    ██      \033[38;5;208m██   ██\033[0m          ║")
        print("  ║      ██      ███████    ██    █████   \033[38;5;208m██████\033[0m           ║")
        print("  ║      ██      ██   ██    ██    ██      \033[38;5;208m██   ██\033[0m          ║")
        print("  ║      ███████ ██   ██    ██    ███████ \033[38;5;208m██   ██\033[0m          ║")
        print("  ║                                                        ║")
        print("  ║         🌍 App Store Connect Localization Tool         ║")
        print("  ║             Multi-AI Provider Translation              ║")
        print("  ║                                                        ║")
        print("  ╚════════════════════════════════════════════════════════╝")
        print()
    
    def run(self):
        """Main application loop."""
        self.show_logo()
        
        # Initialize App Store Connect client
        if not self.setup_app_store_client():
            return
        
        # Check if AI providers are available
        if not self.ai_manager.list_providers():
            print_error("No AI providers configured. Please run setup.")
            if not self.setup_wizard():
                return
        
        # Main application loop
        while True:
            try:
                if not self.show_main_menu():
                    break
            except KeyboardInterrupt:
                print()
                print_info("Exiting TranslateR...")
                break
            except Exception as e:
                print_error(f"An error occurred: {e}")
                input("Press Enter to continue...")


def main():
    """Main entry point for TranslateR application."""
    try:
        cli = TranslateRCLI()
        cli.run()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print_error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
