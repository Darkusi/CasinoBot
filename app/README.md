<div align="center">
  <img src="docs/logo.webp" alt="Claims Casino" width="80">
  <h1>CasinoBot — Claims Casino Automation</h1>
  <p><strong>Desktop app for auto-claiming free Sweepstakes Cash from 80+ casinos.</strong></p>
  <p>
    <a href="https://github.com/glowrius/casino-bonus-monitor/releases">Download CasinoBot.exe</a>
    ·
    <a href="https://claimscasino.com">claimscasino.com</a>
  </p>
  <br>
</div>

## Download

[**⬇ Download CasinoBot.exe**](https://github.com/glowrius/casino-bonus-monitor/releases/latest) — Windows x64.

No Python, no dependencies, no browser setup. Just download, run, activate your license, and start claiming.

## Features

### Automated Daily Claims
Set up your casino accounts once. CasinoBot logs into each casino daily, claims your free Sweepscash, and tracks your total earnings. 80+ supported casinos.

### Real-Time Discord Alerts
Scans Reddit 24/7 for free SC, spins, and bonus offers. Posts instant alerts to your Discord server via webhooks so you never miss a drop.

### Streamer Link Sniping
Monitors Kick.com streams for promo code drops and exclusive giveaways in real-time.

### Manual Claim
Need to claim right now? Hit "Claim Now" on any account — the app opens a browser, logs in, and claims immediately.

### Schedule & Cooldown Tracking
Shows 24-hour cooldown for every casino. Color-coded status: ready, cooling, or error.

## Screenshots

*(Coming soon)*

## Getting a License

CasinoBot requires a valid license key to run.

1. Download `CasinoBot.exe` from [Releases](https://github.com/glowrius/casino-bonus-monitor/releases)
2. Launch the app — a license activation dialog appears
3. Enter your license key (format: `XXXX-XXXX-XXXX-XXXX`)
4. Access the full dashboard with all features

Don't have a license? Contact support on Discord.

## Quick Start

1. **Add accounts** — Go to the Accounts tab, click "+ Add Account", enter the domain (e.g., `chumbacasino.com`) and your login credentials
2. **Start monitoring** — In the Dashboard tab, click "Start Monitoring" to begin Reddit scanning and auto-claim scheduling
3. **Check the Monitor tab** — See live logs of claims, alerts, and system activity
4. **View your schedule** — The Schedule tab shows every casino's claim status and cooldown timer
5. **Configure webhooks** — Set your Discord webhook URLs in Settings to receive alerts

## Build from Source (maintainers only)

```powershell
pip install -r requirements.txt
pyinstaller --onefile --windowed --icon=assets/icon.ico --name CasinoBot --add-data "combined.py;." --add-data "sites.json;." --add-data "license_keys.json;." gui_app.py
```

## Auto-Build

Pushing a tag (`v1.0.0`, `v1.1.0`, etc.) triggers GitHub Actions to build `CasinoBot.exe` and attach it to the release.

```powershell
git tag v1.0.0
git push origin v1.0.0
```

## Tech Stack

- **GUI:** PyQt6 (Qt6 framework)
- **Automation:** Selenium + ChromeDriver
- **Monitoring:** Reddit JSON API, webhook-based Discord alerts
- **Packaging:** PyInstaller (single-file portable exe)
- **CI/CD:** GitHub Actions (Windows runner)

## License

MIT
