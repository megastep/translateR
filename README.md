# TranslateR

```text
████████ ██████   █████  ███   ██  ███████ ██       █████  ████████ ███████ ██████  
   ██    ██   ██ ██   ██ ████  ██  ██      ██      ██   ██    ██    ██      ██   ██ 
   ██    ██████  ███████ ██ ██ ██  ███████ ██      ███████    ██    █████   ██████  
   ██    ██   ██ ██   ██ ██  ████       ██ ██      ██   ██    ██    ██      ██   ██ 
   ██    ██   ██ ██   ██ ██   ███  ███████ ███████ ██   ██    ██    ███████ ██   ██ 
```

<div align="center">

**🌍 AI-Powered App Store Connect Localization Tool**

</div>

Automate App Store Connect localizations with AI translation. Transform your single-language app metadata into 38+ localized versions with just a few commands.

## What It Does

TranslateR connects to your App Store Connect account and automatically translates your app's metadata (description, keywords, promotional text, what's new) into multiple languages using AI providers like Claude, GPT, or Gemini.

**Before**: Manually translate and upload metadata for each language  
**After**: Select languages, choose AI provider, hit enter. Done.

## Quick Start

1. **Install**

   ```bash
   git clone https://github.com/emreertunc/translater.git
   cd translater
   pip install -r requirements.txt
   ```

2. **Setup** (one-time)

   ```bash
   python3 main.py
   ```

   - Add your App Store Connect API key (.p8 file)
   - Add at least one AI provider API key (Claude/GPT/Gemini)

3. **Use**

   ```bash
   python3 main.py
   ```

   Choose your workflow and follow prompts.

## What You Need

### App Store Connect API Key

1. Go to App Store Connect > Users and Access > Integrations
2. Create API key with **App Manager** role
3. Download the `.p8` file and place it under `~/.appstoreconnect/private_keys/` (recommended). The tool will also accept a custom path.
4. Note your Key ID and Issuer ID

### AI Provider (pick one or more)

- **Claude**: [Get key](https://console.anthropic.com/) - Best translation quality (recommended)
- **GPT**: [Get key](https://platform.openai.com/) - Most reliable
- **Gemini**: [Get key](https://makersuite.google.com/) - Fastest

### Environment Variables (optional)

You can provide AI provider keys via environment variables; these override values saved in `config/api_keys.json`:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GOOGLE_API_KEY` or `GEMINI_API_KEY` or `GOOGLE_GEMINI_API_KEY`

Editor preferences (for multiline edits):

- `VISUAL` or `EDITOR` (e.g., `export EDITOR="code -w"`, `vim`, `nano`)

Concurrency (advanced):

- `TRANSLATER_CONCURRENCY` controls how many locales are translated in parallel across workflows that perform translations. Default: number of CPU cores detected.

### Inspect ASC Locale Codes

If App Store Connect UI offers a language but the API rejects your shortcode, read back the exact codes Apple is returning for a version:

```bash
python3 inspect_version_locales.py <app-id>
python3 inspect_version_locales.py <app-id> --version-id <app-store-version-id> --json
```

By default the script resolves the latest App Store version for the app ID you pass, then prints the `attributes.locale` values from `GET /v1/appStoreVersions/{id}/appStoreVersionLocalizations`. Use `--version-id` if you want to inspect a specific version instead.

### Provider Defaults (optional)

- Set a default AI provider used in workflows: in the CLI, open “⚙️  Configuration” → “Set default AI provider”.
- Choose the default model per provider: “⚙️  Configuration” → “Set default model per provider”.
- You can still choose a different provider at runtime; when a default exists you’ll be prompted to confirm or pick another.

### Prompt Refinement (optional)

- Set a global translation guidance phrase: in the CLI, open “⚙️  Configuration” → “Set translation prompt refinement”.
- During workflows, you can enter a per-run refinement phrase; the tool appends it to the system/prompt sent to the AI.

## 9 Main Workflows

### 1. 🌐 Translation Mode

**Use when**: Adding new languages to your app

- Detects your base language (usually English)
- Shows untranslated languages
- Translates all metadata fields
- Creates new localizations

### 2. 📝 Release Mode

**Use when**: Creating release notes ("What's New") for a new version

- Select one or multiple platforms (iOS, macOS, tvOS, visionOS)
- Detects locales missing release notes and selects them by default
- Pull from reusable presets (built-in or custom) for frequently used notes
- Enter or edit source notes (English) if missing, or reuse base notes
- Batch-translates all target locales, shows a full preview, lets you edit per-locale, then applies updates per platform
- If you're not happy with the results, re‑enter the source release notes and re‑translate before applying (available in both TUI and non‑TUI flows)
- Editing opens your system editor (`$VISUAL`/`$EDITOR`) when available; otherwise a simple inline editor is provided
- Updates the base locale if it's empty for a chosen platform

### 3. ✨ Promo Mode

**Use when**: Refreshing Promotional Text for every locale at once

- Pick the platforms you want to update; TranslateR loads every existing localization automatically
- Reuse the base promotional text, edit it inline, or enter a brand-new 170‑character message
- Translate that source text into every selected locale (even ones that already had promotional text) and preview all results
- Edit any locale manually before applying, or re-enter the source text and re-run translations until you're happy
- Applies updates to every platform in one pass, including the base locale, so your worldwide marketing message stays in sync

### 4. 🔄 Update Mode

**Use when**: Updating existing translations (e.g., new "What's New" content)

- Updates specific fields in existing languages
- Choose which languages and fields to update
- Perfect for version updates

### 5. 📋 Copy Mode

**Use when**: New app version with similar content

- Copy content from previous version
- No translation needed
- Fast setup for new versions

### 6. 🚀 Full Setup Mode  

**Use when**: Complete localization for new apps

- Translate into ALL 38+ supported languages
- Maximum global reach
- One-command setup

### 7. 📱 App Name & Subtitle Mode

**Use when**: Translating app name and subtitle

- Separate workflow for branding elements
- 30-character limits enforced
- Brand-focused translations

### 8. 🛒 IAP Translations

**Use when**: Localizing in-app purchase display name and description

- Pick one or more IAP products tied to the selected app
- Detects the base locale from existing IAP localizations
- Translates name (30 chars) and description (45 chars) into missing locales
- Saves each locale automatically, reusing your chosen AI provider and refinement phrase

### 9. 💳 Subscription Translations

**Use when**: Localizing subscription name and description

- Choose a subscription group for the app, then pick specific subscriptions
- Detects base locale from existing subscription localizations
- Prefills target languages with the app’s existing locales
- Translates name and description for missing locales and saves updates automatically

### 8. 📄 Export Localizations

**Use when**: Backing up or analyzing existing localizations

- Export all existing localizations to timestamped file
- Choose latest version or specific version
- Complete backup with all metadata fields
- Creates organized JSON export with app details

### 9. 🗂️ Manage Presets

**Use when**: Maintaining reusable release note snippets

- Browse the built-in preset library and your custom additions
- Create new presets from an English note; TranslateR generates translations for every App Store locale automatically
- Remove presets you no longer need (built-in presets are read-only)

## Supported Fields & Languages

**Fields**: Description (4000 chars), Keywords (100 chars), Promotional Text (170 chars), What's New (4000 chars), App Name (30 chars), Subtitle (30 chars)

**Languages**: All 38 App Store locales including German, French, Spanish, Chinese, Japanese, Korean, Arabic, and more.

## Example Workflow

```bash
$ python3 main.py

TranslateR - App Store Localization Tool
1. 🌐 Translation Mode
2. 📝 Release Mode
3. ✨ Promo Mode
4. 🔄 Update Mode
5. 📋 Copy Mode
6. 🚀 Full Setup Mode
7. 📱 App Name & Subtitle Mode
8. 📄 Export Localizations
9. 🗂️ Manage Presets
10. ⚙️  Configuration
11. ❌ Exit

Choose: 1

Apps found:
1. My Awesome App (v2.1)

Select app: 1
Base language detected: English (US)

Available target languages:
1. German  2. French  3. Spanish  4. Chinese (Simplified)
[... 34 more languages]

Select languages (comma-separated or 'all'): 1,2,3
AI Provider: Claude 4 Sonnet (recommended)

Translating German... ✓
Translating French... ✓  
Translating Spanish... ✓

✅ Translation completed! 3/3 languages successful
```

## Configuration Files

After first run, config files are created in `config/`:

**`api_keys.json`** - Your API keys and credentials  
**`providers.json`** - AI provider settings (models, defaults)  
**`instructions.txt`** - Translation guidelines for AI

## Developer Skill: App Store Connect API

For endpoint discovery and API contract checks, use the in-repo skill at `.codex/skills/app-store-connect-api/`.

- OpenAPI artifact: `.codex/skills/app-store-connect-api/references/openapi.oas.json`
- Operation index (generated): `.codex/skills/app-store-connect-api/references/operation-index.json`
- Query script: `python .codex/skills/app-store-connect-api/scripts/query_spec.py summary`
- Search operations: `python .codex/skills/app-store-connect-api/scripts/query_spec.py search "subscriptions" --limit 20`
- Inspect one operation: `python .codex/skills/app-store-connect-api/scripts/query_spec.py show GET /v1/apps`
- Rebuild compact index: `python .codex/skills/app-store-connect-api/scripts/build_operation_index.py`

## Logging & Debugging

All AI requests and responses are automatically logged for debugging and quality control:

**Location**: `logs/ai_requests_YYYYMMDD_HHMMSS.log`

**What's logged**:

- All translation requests with original text and parameters
- AI responses with translated text and character counts
- Error details when translations fail
- Character limit retry attempts
- Timestamps for performance analysis

**Log format example**:

```text
[2025-08-05 10:30:15] REQUEST
Provider: Anthropic Claude
Model: claude-sonnet-4-20250514
Target Language: German
Max Length: 100
Original Text (45 chars):
--------------------------------------------------
Transform your ideas into beautiful apps
--------------------------------------------------

[2025-08-05 10:30:18] RESPONSE - SUCCESS
Provider: Anthropic Claude
Translated Text (42 chars):
--------------------------------------------------
Verwandeln Sie Ihre Ideen in schöne Apps
--------------------------------------------------
```

**Benefits**:

- **Debug translation issues** - See exactly what was sent and received
- **Compare AI providers** - Track which providers work best for your content
- **Quality control** - Review translations before publishing
- **Performance monitoring** - Identify slow or failing requests

**Privacy**: API keys are never logged. Log files stay on your machine (not in git).

## Troubleshooting

**Error: "App Store Connect configuration not found"**  
→ Check your .p8 file path and API credentials

**Error: "No AI providers configured"**  
→ Add at least one valid AI provider API key

**Error: "Translation failed"**  
→ Check API quotas/limits, try different provider

## Contributing

1. Fork the repo
2. Create feature branch
3. Follow patterns in existing code
4. Test with real App Store data
5. Submit PR

## License

**MIT License**

Copyright (c) 2025 Emre Ertunç

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

**Author**: Emre Ertunç  
**Contact**: <emre@ertunc.com>  
**Repository**: <https://github.com/emreertunc/translater>

---

⚠️ **Important**: Always review AI translations before publishing. Test with non-production apps first.

💡 **Tip**: Start with major markets (English, Spanish, German, Chinese) before expanding to all languages.
