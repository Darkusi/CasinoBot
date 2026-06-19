# Session Summary

## Goal
Desktop GUI app ("Claims Casino - Automation Suite") for auto-claiming sweepstakes casino bonuses, with license-key activation, HWID-bound licensing, cloud updater via update.json, Selenium-based link automation, Reddit monitoring with Discord webhooks.

## What's Built (Core Changes)

### Desktop App (`gui_app.py`)
- **AnimatedButton class**: `QVariantAnimation`-powered QPushButton with 180ms hover/press fade, supports `variant` param: "default", "gold", "success", "danger". All buttons now use AnimatedButton.
- **Title bar centering**: Brand labels (CLAIMS CASINO + Automation Suite) vertically centered in 64px bar via QWidget wrapper with top/bottom padding.
- **Summary box spacing**: Daily SC stat columns have `setSpacing(4)` between number and label, `setSpacing(16)` between columns.
- **Toolbar layout**: + Add / Claim All / Stop All on left, stretch, Import / Refresh on right.
- **Bottom frames**: All tabs have consistent `setContentsMargins(8,8,8,8)` with `setSpacing(6)` in bottom group boxes.
- **Expandable window**: `setMinimumSize(900,600)` + `resize(1200,780)`
- **SSO login**: `CasinoAutomation.login()` accepts `login_method` ("email"/"google"/"apple") with auto-fill
- **Add Account dialog**: Login Method dropdown (Email/Google/Apple), `vals()` returns 4-tuple
- **Login Method column**: Daily SC table shows colored method badges (purple=Google, red=Apple, grey=Email)
- **Link Automation**: Casino dropdown from `sites.json` next to URL input, button renamed "+ Add Link"
- **Visual progress panel**: QProgressBar + status label replaces Monitor Feed table; Log is collapsible (QGroupBox checkable)
- **ProcessQueueWorker QThread**: Background queue processing with progress signals, keeps UI responsive
- **Discord Watcher**: Configurable bot token + channel ID, polls Discord API for links and auto-queues them
- **Cloud updater**: Fetches `update.json` manifest from `claimscasino.com` instead of GitHub API
- **Online activation**: LicenseDialog tries online activation first, falls back to local `license_keys.json`
- **Anti-debug startup**: `check_anti_debug()` runs at startup, kills if debugger detected
- **String obfuscation**: API URLs XOR+base64 encoded to prevent trivial string-search cracking
- **License re-validation**: At startup, re-validates existing license online
- **Version**: `v1.1.0`

### Core Logic (`combined.py`)
- **Flask optional**: try/except ImportError with stub classes — EXE no longer needs Flask bundled
- **HWID**: `get_hwid()` generates 32-char SHA-256 fingerprint (CPU ID + disk serial + MAC + hostname)
- **Anti-debug**: Detects debuggers (x64dbg, IDA, ProcessHacker), sandbox artifacts, VM indicators
- **Obfuscation helpers**: `_obfuscate()` / `_deobfuscate()` with XOR+base64
- **`process_link()` rewrite**: Full Selenium-based claiming — extracts domain, looks up credentials, logs in, claims, updates SC total (replaced simple HTTP GET)
- **`discord_watch_loop()`**: Polls Discord channel via REST API, extracts URLs, auto-adds to link queue
- **`site_xpaths.json`**: Per-domain XPath overrides for cookie acceptance, login, wallet, claim button, etc.
- **`monitor_feed` deque**: `deque(maxlen=50)` populated in `monitor_loop` for Reddit post tracking
- **`/api/activate` endpoint**: Flask activation endpoint for online key validation

### Activation Server (`activation_server.py`)
- Standalone Flask server: `/api/activate` (key+HWID), `/api/validate`, `/api/revoke`, `/api/add-key`, `/api/list-keys`, `/api/status`
- Licenses stored in `licenses.json`
- Admin key via `ACTIVATION_ADMIN_KEY` env var

### Build
- **CasinoBot.spec**: PyInstaller config with hidden imports (`flask`, `selenium`, `webdriver_manager`), excludes (`wmi`), datas (`activation_server.py`, `site_xpaths.json`, `license_keys.json`, `logo.png`)
- **scripts/setup.iss**: Inno Setup v1.1.0, no launch checkbox (Flags: nowait skipifsilent), auto-launches on finish, cert auto-install
- **CI**: `.github/workflows/build.yml` uses `CasinoBot.spec`
- **EXE**: ~48-50 MB one-file build

### Config Files
- `site_xpaths.json` — Per-domain XPath selectors for claim automation (DEFAULT + 10 major casinos)
- `sites.json` — 81 sweepstakes casino definitions (S/A/B tiers)

## Next Steps
1. Upload `CasinoBot-Setup-1.1.0.exe` to Discord channel `#1493302662974935072`
2. Edit `docs/update.json` with Discord CDN URL and correct byte size
3. Deploy `activation_server.py` to cloud host (Render/Railway/VPS)
4. Add more per-site XPaths to `site_xpaths.json` for better claim coverage
5. Build browser step recorder for sites where generic XPaths fail

## Key Constraints
- `gui_app.py` line 34: `APP_VERSION = "v1.1.0"`
- Obfuscated URLs use key `bytes([0x47, 0x8B, 0x1A, 0xD4, 0x66, 0x2F, 0x93, 0x01])`
- Flask is optional — bundled stubs when not installed
- Windows PowerShell path quoting issues: use `-workdir` or single quotes for paths with spaces
