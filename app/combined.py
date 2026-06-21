import json
import os
import sys
import threading
import time
import socket
import hashlib
import secrets
import random
import traceback
from collections import deque
from datetime import datetime
from pathlib import Path

import re
import base64
import subprocess
import requests
try:
    from flask import Flask, jsonify, request, send_from_directory, make_response, session, redirect, url_for
except ImportError:
    class _FlaskStub:
        def __init__(self, name):
            self.secret_key = None
            self.after_request = lambda f: f
        def route(self, rule, **options):
            return lambda f: f
        def run(self, *a, **kw): pass
    Flask = _FlaskStub
    def jsonify(*a, **kw):
        return type("_Resp", (), {"status_code": 200, "headers": {}, "set_cookie": lambda *a, **kw: None})()
    class _Req:
        method = "GET"
        args = {}
        form = {}
        cookies = {}
        @staticmethod
        def get_json(silent=False):
            return {}
        @staticmethod
        def headers():
            return {}
    request = _Req()
    def send_from_directory(*a, **kw): return ""
    def make_response(*a, **kw): return ""
    class _Session(dict):
        def get(self, k, d=None):
            return super().get(k, d)
    session = _Session()
    def redirect(*a, **kw): return ""
    def url_for(*a, **kw): return ""

# ================== CONFIGURATION ==================
SCRIPT_DIR = Path(__file__).parent

USERS = {
    "953177450391683082": {"name": "Glow", "license": "8K3X-M9P1-Q2R7-V5N2", "admin": True},
    "695697021868310669": {"name": "andyttc", "license": "J4W6-B8T2-C1D9-F3H5", "admin": False},
    "186105992252096512": {"name": "Nazistu", "license": "A7S3-D5F6-G8H2-J9K4", "admin": False},
    "222898514789662721": {"name": "No Leg Leny", "license": "L1Q2-W3E4-R5T6-Y7U8", "admin": False},
    "741378521460637773": {"name": "pxsymbol", "license": "Z9X8-C7V6-B5N4-M3L2", "admin": False},
    "1389284552442253352": {"name": "Braeden Nigley", "license": "P1O2-I3U4-Y5T6-R7E8", "admin": False}
}
ADMIN_KEY = "A1B2-C3D4-E5F6-G7H8"
MEMBERSHIP_DIR = SCRIPT_DIR / "membership-site"
CLAIMS_CASINO_DIR = Path(os.environ.get("CLAIMS_CASINO_DIR", str(SCRIPT_DIR.parent / "Claims Casino")))
ADMIN_USERS_FILE = SCRIPT_DIR / "admin_users.json"
APPROVED_USERS_FILE = SCRIPT_DIR / "approved_users.json"
SESSION_SECRET = secrets.token_hex(32)
# Load .env file manually for Discord token
_env_path = SCRIPT_DIR / ".env"
if _env_path.exists():
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip())

DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
DISCORD_CHANNEL_ID = "1493303378065883237"

FLASK_PORT = 5001
CHECK_INTERVAL = 60
SUBREDDITS = ["SweepStakeSideHustle"]
USER_AGENT = "python:ClaimsCasino:1.0 (by /u/Glow)"

# Shared session with cookie persistence for Reddit fetches
_reddit_session = requests.Session()
_reddit_session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})

def _reddit_get(url, retries=3):
    """GET a Reddit JSON endpoint with jitter delay + exponential backoff on 429/403."""
    time.sleep(random.uniform(1.0, 2.5))
    for attempt in range(retries):
        resp = _reddit_session.get(url, timeout=15)
        if resp.status_code == 200:
            return resp
        if resp.status_code in (429, 403) and attempt < retries - 1:
            wait = (2 ** attempt) + random.uniform(0, 1)
            print(f"[Reddit] {resp.status_code} on {url[:60]} — retrying in {wait:.1f}s (attempt {attempt+1}/{retries})")
            time.sleep(wait)
            continue
        resp.raise_for_status()
    return resp

# Discord webhooks
FLOOD_WEBHOOK = "https://canary.discord.com/api/webhooks/1498489497032196158/E5ay3hVqPyEkqojKCLmFyCAiM1MGkop5plEsSclMMbP35KDiwHnBPhgjwVmoKzSozOB7"
LIVE_WEBHOOK = "https://canary.discord.com/api/webhooks/1498489497032196158/E5ay3hVqPyEkqojKCLmFyCAiM1MGkop5plEsSclMMbP35KDiwHnBPhgjwVmoKzSozOB7"
FREECASH_WEBHOOK = "https://canary.discord.com/api/webhooks/1494388689135210557/7RFiJUe05dG1jEoiUXp7zbXqXHOd13gg_LnEXDuUUq5davtJEzgSIqx2MAKUsIqOkZF6"
CLAIMS_WEBHOOK = "https://canary.discord.com/api/webhooks/1493303378065883237/PLACEHOLDER_TOKEN"

# Headless mode (True = invisible, False = visible for testing)
HEADLESS_MODE = True

# Claim schedule data file
CLAIM_SCHEDULE_FILE = SCRIPT_DIR / "claim_schedule.json"
STREAMERS_FILE = SCRIPT_DIR / "streamers.json"
LINK_QUEUE_FILE = SCRIPT_DIR / "link_queue.json"

# Profile pictures directory
PROFILE_PICS_DIR = SCRIPT_DIR / "profile_pics"
PROFILE_PICS_DIR.mkdir(exist_ok=True)

# License key configuration
LICENSE_KEYS_FILE = SCRIPT_DIR / "license_keys.json"
DEFAULT_LICENSE_KEY = "SPIN-2024-LIVE"
LEGACY_LICENSE_KEYS = ("2026",)

def normalize_license_key(value):
    return (value or "").strip().upper().replace("-", "").replace(" ", "")

def generate_license_key():
    """Generate a new license key in format XXXX-XXXX-XXXX-XXXX"""
    import random, string
    chars = string.ascii_uppercase + string.digits
    groups = []
    for _ in range(4):
        groups.append(''.join(random.choices(chars, k=4)))
    return '-'.join(groups)

def load_license_keys():
    if LICENSE_KEYS_FILE.exists():
        with open(LICENSE_KEYS_FILE, 'r') as f:
            return json.load(f)
    # Initialize with default key
    keys = {
        "SPIN-2024-LIVE": {"status": "active", "tier": "premium", "created": time.time()},
        "2026": {"status": "active", "tier": "premium", "created": time.time()}
    }
    save_license_keys(keys)
    return keys

def save_license_keys(keys):
    with open(LICENSE_KEYS_FILE, 'w') as f:
        json.dump(keys, f, indent=2)

def validate_license_key(raw_key):
    """Check if a license key is valid and active"""
    normalized = normalize_license_key(raw_key)
    if not normalized:
        return {"valid": False}
    keys = load_license_keys()
    # Try exact match first
    for stored_key, data in keys.items():
        if normalize_license_key(stored_key) == normalized:
            if data.get("status") == "active":
                return {"valid": True, "tier": data.get("tier", "basic"), "key": stored_key}
            return {"valid": False, "reason": "revoked"}
    # Try legacy hardcoded keys
    for legacy in LEGACY_LICENSE_KEYS:
        if normalize_license_key(legacy) == normalized:
            return {"valid": True, "tier": "basic", "key": legacy}
    return {"valid": False}

# ================== HWID & ANTI-DEBUG ==================

def get_hwid():
    """Generate a hardware-bound machine identifier."""
    try:
        import hashlib, uuid
        # Collect various hardware identifiers
        parts = []
        try:
            import wmi
            c = wmi.WMI()
            for cpu in c.Win32_Processor()[:1]:
                parts.append(str(cpu.ProcessorId))
            for disk in c.Win32_DiskDrive()[:1]:
                parts.append(str(disk.SerialNumber))
        except:
            pass
        # Fallback to hashed MAC + machine name
        mac = uuid.getnode()
        host = socket.gethostname()
        parts.append(str(mac))
        parts.append(host)
        raw = "|".join(parts)
        return hashlib.sha256(raw.encode()).hexdigest()[:32]
    except:
        return hashlib.sha256(socket.gethostname().encode()).hexdigest()[:32]

def check_anti_debug():
    """Check for debuggers, sandboxes, and VMs. Returns True if safe."""
    try:
        # Detect debugger processes
        debug_procs = ["x64dbg.exe", "x32dbg.exe", "ollydbg.exe", "ida.exe",
                       "ida64.exe", "windbg.exe", "ProcessHacker.exe", "procmon.exe",
                       "procexp.exe", "cheatengine.exe", "httpanalyzer.exe", "fiddler.exe"]
        try:
            output = subprocess.check_output("tasklist /FO CSV", shell=True, timeout=3, stderr=subprocess.DEVNULL).decode("utf-8", errors="ignore")
            for proc in debug_procs:
                if proc.lower() in output.lower():
                    print(f"[SEC] Debugger detected: {proc}")
                    return False
        except:
            pass
        # Detect common sandbox artifacts
        import os
        sb_indicators = [
            "C:\\ProgramData\\Microsoft\\Windows\\Start Menu\\Programs\\StartUp\\agent.py",
            "C:\\windows\\TEMP\\vbox",
            "C:\\windows\\TEMP\\xorange",
        ]
        for ind in sb_indicators:
            if os.path.exists(ind):
                return False
        return True
    except:
        return True  # If check fails, let it run

# ================== OBFUSCATION HELPERS ==================
_OBFUSCATION_KEY = bytes([0x47, 0x8B, 0x1A, 0xD4, 0x66, 0x2F, 0x93, 0x01])

def _obfuscate(s):
    """Simple XOR obfuscation for strings (NOT real encryption, just anti-string-search)."""
    return base64.b64encode(bytearray([ord(c) ^ _OBFUSCATION_KEY[i % len(_OBFUSCATION_KEY)] for i, c in enumerate(s)])).decode()

def _deobfuscate(encoded):
    """Reverse XOR obfuscation."""
    raw = base64.b64decode(encoded.encode())
    return "".join(chr(b ^ _OBFUSCATION_KEY[i % len(_OBFUSCATION_KEY)]) for i, b in enumerate(raw))

# Generic XPaths (fallback if site not in site_xpaths.json)
GENERIC_XPATHS = {
    "cookie_accept": "//button[contains(text(),'Accept') or contains(text(),'Agree')]",
    "login_button": "//a[contains(text(),'Login') or contains(text(),'Log In')] | //button[contains(text(),'Login')]",
    "email_field": "//input[@type='email' or @name='email' or @placeholder='Email']",
    "password_field": "//input[@type='password']",
    "submit_button": "//button[@type='submit'] | //button[contains(text(),'Login')]",
    "wallet_url": "/wallet",
    "daily_claim_button": "//button[contains(text(),'Daily') or contains(text(),'Claim') or contains(text(),'Bonus')]",
    "success_indicator": "//div[contains(@class,'balance') or contains(@class,'user')]",
    "confirm_button": "",
    "otp_field": "",
    "otp_verify_button": "",
    "sso_google": "//button[contains(@aria-label,'Google') or contains(text(),'Google')] | //div[contains(@aria-label,'Google')] | //a[contains(@title,'Google')]",
    "sso_apple": "//button[contains(@aria-label,'Apple') or contains(text(),'Apple')] | //div[contains(@aria-label,'Apple')] | //a[contains(@title,'Apple')]"
}

# ================== DISCORD WEBHOOK ==================
def extract_link_from_body(body):
    """Extract first casino link from post body"""
    import re
    if not body:
        return None
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(url_pattern, body)
    for url in urls:
        if 'reddit.com' not in url.lower() and url.startswith('http'):
            return url
    return None

def is_valid_free_post(title, body=""):
    """Check if post is valid Free SC/Spin offer - excludes 'new casinos' etc"""
    title_lower = title.lower()
    
    # Must contain free keywords
    free_keywords = ["free spin", "free sc", "free sweeps", "free coins", "free bonus",
                     "daily spin", "daily sc", "daily bonus", "login bonus", "claim bonus",
                     "freebie", "no deposit", "free play", "bonus spin", "bonus sc"]
    has_free = any(kw in title_lower for kw in free_keywords)
    
    if not has_free:
        return False
    
    # Must NOT contain exclude keywords
    exclude_keywords = ["new casino", "casinos added", "icymi", "new casinos",
                       "casino added", "added to", "launch", "introducing",
                       "welcome to", "announcing", "now live", "grand opening",
                       "sign up bonus", "registration bonus"]
    has_exclude = any(kw in title_lower for kw in exclude_keywords)
    
    return not has_exclude

def is_free_sc_post(title, body=""):
    """Check if post matches 'Free X SC' pattern and extract amount"""
    import re
    match = re.search(r'free\s+(\d+(?:\.\d+)?)\s*sc', title.lower())
    if match:
        return {"valid": True, "sc_amount": float(match.group(1))}
    return {"valid": False}

def post_freecash_discord(title, extracted_link, created_utc, sc_amount):
    """Post a clean 'Free X SC' alert to the freecash Discord channel"""
    try:
        from datetime import datetime, timezone, timedelta
        if created_utc:
            cst = timezone(timedelta(hours=-6))
            dt = datetime.fromtimestamp(created_utc, tz=cst)
            post_time = dt.strftime("%b %d, %Y %I:%M:%S %p CST")
        else:
            post_time = "Recent"
        
        # Clean the title - remove prefix before dash if present
        clean_title = title.split(' - ')[1] if ' - ' in title else title
        # Extract casino name from title (remove "Free X SC" part)
        casino_name = re.sub(r'free\s+\d+(?:\.\d+)?\s*sc\s*[:\-]?\s*', '', clean_title, flags=re.IGNORECASE).strip()
        if not casino_name:
            casino_name = clean_title
        
        embed = {
            "title": f"Free {sc_amount} SC",
            "url": extracted_link if extracted_link else "https://reddit.com/r/SweepStakeSideHustle",
            "description": f"**{casino_name}**\nClick the link above to claim your free {sc_amount} SC.",
            "color": 0x00FF00,
            "footer": {"text": f"\u00a9 Claim City 2026 \u2022 {post_time}"},
        }
        
        payload = {
            "username": "Free SC Monitor",
            "avatar_url": "https://i.imgur.com/AfFp7pu.png",
            "embeds": [embed]
        }
        
        requests.post(FREECASH_WEBHOOK, json=payload, timeout=10)
        print(f"[{datetime.now()}] Posted freecash to Discord: {title[:50]}")
        return True
    except Exception as e:
        print(f"[{datetime.now()}] Freecash webhook error: {e}")
        return False

def post_to_discord(title, extracted_link, created_utc, is_live=True, sc_amount=None):
    """Post a free SC/spin alert to Discord webhook"""
    try:
        from datetime import datetime, timezone, timedelta
        webhook = LIVE_WEBHOOK if is_live else FLOOD_WEBHOOK
        
        # Use the actual Reddit post timestamp
        if created_utc:
            cst = timezone(timedelta(hours=-6))
            dt = datetime.fromtimestamp(created_utc, tz=cst)
            post_time = dt.strftime("%b %d, %Y %I:%M:%S %p CST")
        else:
            post_time = "Recently posted"
        
        if sc_amount:
            embed_title = f"Free {sc_amount} SC"
            embed_desc = f"Click above to claim your free {sc_amount} SC!"
        else:
            embed_title = f"\U0001f3b0 {title.split(' - ')[0] if ' - ' in title else title}"
            embed_desc = "\U0001f381 Click above for your free bonus!"
        
        embed = {
            "title": embed_title,
            "url": extracted_link if extracted_link else "https://reddit.com/r/SweepStakeSideHustle",
            "description": embed_desc,
            "color": 0x00FF00,
            "footer": {
                "text": f"\u00a9 Claim City 2026 \u2022 {post_time}",
            },
        }
        
        payload = {
            "username": "Sweepstakes Monitor",
            "avatar_url": "https://i.imgur.com/AfFp7pu.png",
            "embeds": [embed]
        }
        
        requests.post(webhook, json=payload, timeout=10)
        print(f"[{datetime.now()}] Posted to Discord: {title[:50]}")
        return True
    except Exception as e:
        print(f"[{datetime.now()}] Discord webhook error: {e}")
        return False

def post_to_claims_discord(title, extracted_link, created_utc, sc_amount=None):
    """Post a free SC/spin alert to the claims Discord channel"""
    try:
        from datetime import datetime, timezone, timedelta
        if created_utc:
            cst = timezone(timedelta(hours=-6))
            dt = datetime.fromtimestamp(created_utc, tz=cst)
            post_time = dt.strftime("%b %d, %Y %I:%M:%S %p CST")
        else:
            post_time = "Recently posted"
        
        if sc_amount:
            embed_title = f"Free {sc_amount} SC"
            embed_desc = f"Click above to claim your free {sc_amount} SC!"
        else:
            embed_title = f"\U0001f3b0 {title.split(' - ')[0] if ' - ' in title else title}"
            embed_desc = "\U0001f381 Click above for your free bonus!"
        
        embed = {
            "title": embed_title,
            "url": extracted_link if extracted_link else "https://reddit.com/r/SweepStakeSideHustle",
            "description": embed_desc,
            "color": 0x00FF00,
            "footer": {"text": f"\u00a9 Claim City 2026 \u2022 {post_time}"},
        }
        payload = {
            "username": "Claims Monitor",
            "avatar_url": "https://i.imgur.com/AfFp7pu.png",
            "embeds": [embed]
        }
        requests.post(CLAIMS_WEBHOOK, json=payload, timeout=10)
        print(f"[{datetime.now()}] Posted claims to Discord: {title[:50]}")
        return True
    except Exception as e:
        print(f"[{datetime.now()}] Claims webhook error: {e}")
        return False

def post_guide_webhook():
    """Send the user guide announcement to the claims Discord channel."""
    try:
        embed = {
            "title": "\U0001f4d6 \u2502 User Guide Available",
            "description": "A full user guide is now available online covering all casino features:",
            "color": 0x9B4DAE,
            "fields": [
                {
                    "name": "\U0001f4cb \u2502 What's Inside",
                    "value": (
                        "\u2022 Command reference (`/status`, `/claim`, `/setcookie`)\n"
                        "\u2022 Cookie-based claiming setup\n"
                        "\u2022 Streamer alerts configuration\n"
                        "\u2022 Auto-claim schedule & history\n"
                        "\u2022 FAQ & troubleshooting"
                    ),
                    "inline": False,
                }
            ],
            "url": "https://claimscasino.com/guide",
            "footer": {"text": "Claim City 2026 \u00a9"},
        }
        payload = {
            "username": "Casino Bonus Monitor",
            "avatar_url": "https://i.imgur.com/AfFp7pu.png",
            "embeds": [embed],
        }
        requests.post(CLAIMS_WEBHOOK, json=payload, timeout=10)
        print(f"[{datetime.now()}] Posted guide announcement webhook")
        return True
    except Exception as e:
        print(f"[{datetime.now()}] Guide webhook error: {e}")
        return False

def load_claim_schedule():
    if CLAIM_SCHEDULE_FILE.exists():
        with open(CLAIM_SCHEDULE_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_claim_schedule(data):
    with open(CLAIM_SCHEDULE_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# ================== STREAMER SNIPER ==================

def load_streamers():
    if STREAMERS_FILE.exists():
        with open(STREAMERS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_streamers(data):
    with open(STREAMERS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def monitor_streamer_loop():
    """Background thread that checks streamers' online status via HTTP reachability."""
    while True:
        try:
            streamers = load_streamers()
            changed = False
            for s in streamers:
                username = s.get("username", "")
                platform = s.get("platform", "Kick")
                if not username:
                    continue
                url = f"https://kick.com/api/v2/channels/{username}" if platform.lower() == "kick" else f"https://api.twitch.tv/helix/streams?user_login={username}"
                old_status = s.get("status", "idle")
                try:
                    resp = requests.get(url, timeout=8, headers={"User-Agent": USER_AGENT})
                    if resp.status_code == 200:
                        s["status"] = "live"
                        s["last_seen"] = "Just now"
                    else:
                        s["status"] = "offline"
                except:
                    s["status"] = "offline"
                if s["status"] != old_status:
                    changed = True
            if changed:
                save_streamers(streamers)
        except:
            pass
        time.sleep(60)

# ================== LINK AUTOMATION ==================

def load_link_queue():
    if LINK_QUEUE_FILE.exists():
        with open(LINK_QUEUE_FILE, 'r') as f:
            return json.load(f)
    return []

def save_link_queue(data):
    with open(LINK_QUEUE_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def process_link(url, progress_callback=None):
    """Process a single sweepstakes link using Selenium.
    Extracts domain, looks up stored credentials, logs in, and claims daily bonus.
    Returns dict with success/message and optional sc_amount.
    """
    def _progress(msg, pct=None):
        if progress_callback:
            progress_callback(msg, pct)

    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")

        # Look up site config
        sites = load_sites()
        site = next((s for s in sites if s["domain"] == domain or domain.endswith(s["domain"])), None)
        casino_name = site["name"] if site else domain
        _progress(f"Processing {casino_name}...", 5)

        # Look up credentials
        accounts = load_accounts()
        acct_domain = None
        for d in accounts:
            if d in domain or domain in d:
                acct_domain = d
                break
        if not acct_domain:
            return {"success": False, "message": f"No credentials for {casino_name}", "casino": domain}

        account = accounts[acct_domain]
        _progress(f"Logging into {casino_name}...", 20)

        auto = CasinoAutomation(headless=HEADLESS_MODE)
        if not auto.start():
            return {"success": False, "message": "Browser failed to start", "casino": domain}

        if not auto.login(acct_domain, account["username"], account["password"], account.get("login_method", "email")):
            auto.close()
            return {"success": False, "message": f"Login failed for {casino_name}", "casino": domain}

        _progress(f"Claiming at {casino_name}...", 60)
        sc = auto.claim_daily_bonus(acct_domain)
        auto.close()

        if sc > 0:
            accts = load_accounts()
            if acct_domain in accts:
                accts[acct_domain]["sc_total"] = round(accts[acct_domain].get("sc_total", 0) + sc, 2)
                save_accounts(accts)
            with state_lock:
                state["claimed"] += 1
                state["sc_total"] = round(state["sc_total"] + sc, 2)
            _progress(f"Claimed {sc} SC at {casino_name} \u2713", 100)
            return {"success": True, "message": f"Claimed {sc} SC", "casino": domain, "sc_amount": sc}
        else:
            _progress(f"No SC available at {casino_name}", 100)
            return {"success": False, "message": "No SC available", "casino": domain}

    except Exception as e:
        _progress(f"Error: {e}", 100)
        return {"success": False, "message": str(e), "casino": "unknown"}

def discord_watch_loop(bot_token, channel_id, log_callback=None):
    """Poll a Discord channel for new messages containing sweepstakes links and add to queue."""
    def _log(msg):
        if log_callback: log_callback(msg)
    seen_ids = set()
    api_url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {"Authorization": f"Bot {bot_token}", "Content-Type": "application/json"}
    while True:
        try:
            resp = requests.get(api_url, headers=headers, params={"limit": 10}, timeout=10)
            if resp.status_code == 200:
                messages = resp.json()
                for msg in messages:
                    mid = msg.get("id")
                    if mid in seen_ids:
                        continue
                    seen_ids.add(mid)
                    content = msg.get("content", "")
                    # Extract URLs from message
                    urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', content)
                    for url in urls:
                        if any(dom in url.lower() for dom in ["casino", "sweep", "spin", "bonus", "claim", "pulsz", "chumba", "stake", "sportzino", "mcluck", "wowvegas", "luckyland", "high5"]):
                            queue = load_link_queue()
                            if not any(q["url"] == url for q in queue):
                                queue.append({"url": url, "added": datetime.now().strftime("%m/%d %H:%M"), "status": "pending", "result": "", "casino": "discord"})
                                save_link_queue(queue)
                                _log(f"Added from Discord: {url[:50]}...")
            else:
                _log(f"Discord API error: HTTP {resp.status_code}")
        except Exception as e:
            _log(f"Discord poll error: {e}")
        time.sleep(30)

def daily_sc_monitor_loop(stop_flag, log_callback=None):
    """Monitor Discord for free drops and auto-claim for accounts with stored credentials."""
    seen = set()
    while not stop_flag.is_set():
        try:
            accounts = load_accounts()
            url = f"https://discord.com/api/v10/channels/{DISCORD_CHANNEL_ID}/messages"
            headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
            resp = requests.get(url, headers=headers, params={"limit": 20}, timeout=10)
            if resp.status_code == 200:
                for msg in resp.json():
                    mid = msg.get("id")
                    if mid in seen: continue
                    seen.add(mid)
                    content = msg.get("content", "")
                    import re
                    urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', content)
                    for link_url in urls:
                        for dom in accounts:
                            if dom in link_url.lower():
                                if log_callback: log_callback(f"Auto-claiming {dom}...")
                                result = process_link(link_url)
                                if log_callback: log_callback(f"{dom}: {result.get('message','')}")
                                break
            else:
                if log_callback: log_callback(f"Discord API error: HTTP {resp.status_code}")
        except Exception as e:
            if log_callback: log_callback(f"Monitor error: {e}")
        stop_flag.wait(30)

def process_queue_loop():
    """Background thread that continuously processes pending links in the queue."""
    while True:
        try:
            queue = load_link_queue()
            pending = [i for i, q in enumerate(queue) if q.get("status") == "pending"]
            if pending:
                for idx in pending[:5]:
                    item = queue[idx]
                    item["status"] = "processing"
                    save_link_queue(queue)
                    result = process_link(item["url"])
                    item["status"] = "done" if result.get("success") else "failed"
                    item["result"] = result.get("message", "Unknown")
                    item["casino"] = result.get("casino", "unknown")
                    save_link_queue(queue)
        except:
            pass
        time.sleep(30)

# ── Local IPC server (Chrome step recorder input) ──
def start_ipc_server(host="127.0.0.1", port=9999):
    """Accept JSON commands from Chrome step recorder or other local tools.
    Supported actions: add_account, claim, trigger_claim, update_credentials.
    Runs as daemon thread — call once at app startup."""
    import socket, json, threading
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((host, port))
    s.listen(5)
    s.settimeout(1.0)
    def _handle(cmd):
        try:
            action = cmd.get("action","")
            if action == "add_account":
                accts = load_accounts()
                dom = cmd["domain"]
                accts[dom] = {"username": cmd.get("username",""), "password": cmd.get("password",""),
                    "sc_total": cmd.get("sc_total",0), "login_method": cmd.get("login_method","email")}
                if cmd.get("cookies"): accts[dom]["cookies"] = cmd["cookies"]
                save_accounts(accts)
                return {"ok": True, "msg": f"Added {dom}"}
            elif action == "claim":
                from urllib.parse import urlparse
                url = cmd.get("url","")
                if url:
                    return process_link(url)
                dom = cmd.get("domain","")
                if dom and dom in load_accounts():
                    accts = load_accounts()
                    info = accts[dom]
                    auto = CasinoAutomation(headless=HEADLESS_MODE)
                    if not auto.start(): return {"ok": False, "msg": "Browser failed"}
                    ok = auto.login(dom, info["username"], info["password"], info.get("login_method","email"))
                    if not ok: auto.close(); return {"ok": False, "msg": "Login failed"}
                    sc = auto.claim_daily_bonus(dom)
                    auto.close()
                    if sc > 0:
                        info["sc_total"] = round(info.get("sc_total",0)+sc,2)
                        save_accounts(load_accounts() | {dom: info})
                        return {"ok": True, "msg": f"Claimed {sc} SC", "sc": sc}
                    return {"ok": False, "msg": "No SC available"}
                return {"ok": False, "msg": "No credentials"}
            elif action == "update_credentials":
                accts = load_accounts()
                dom = cmd["domain"]
                if dom in accts:
                    if "password" in cmd: accts[dom]["password"] = cmd["password"]
                    if "cookies" in cmd: accts[dom]["cookies"] = cmd["cookies"]
                    save_accounts(accts)
                    return {"ok": True, "msg": f"Updated {dom}"}
                return {"ok": False, "msg": f"{dom} not found"}
            return {"ok": False, "msg": f"Unknown action: {action}"}
        except Exception as e:
            return {"ok": False, "msg": str(e)}
    def _loop():
        while True:
            try:
                conn, _ = s.accept()
                data = conn.recv(65536).decode("utf-8")
                conn.sendall((json.dumps(_handle(json.loads(data)))+"\n").encode("utf-8"))
                conn.close()
            except socket.timeout: pass
            except: pass
    t = threading.Thread(target=_loop, daemon=True)
    t.start()

def fetch_daily_freebies():
    """Fetch all free SC/spin posts from last 24h for dashboard display (no Reddit references)"""
    try:
        import traceback
        all_posts = []
        for sr in SUBREDDITS:
            for sort in ["hot", "new", "top"]:
                url = f"https://old.reddit.com/r/{sr}/{sort}.json?limit=100"
                try:
                    resp = _reddit_get(url)
                    if resp.status_code == 200:
                        data = resp.json()
                        if "data" in data and "children" in data["data"]:
                            for child in data["data"]["children"]:
                                p = child["data"]
                                if p.get("stickied"):
                                    continue
                                post_time = p.get("created_utc", 0)
                                title = p.get("title", "")
                                body = p.get("selftext", "")
                                if time.time() - post_time <= 86400:
                                    free_sc = is_free_sc_post(title, body)
                                    if free_sc["valid"] or is_valid_free_post(title, body):
                                        sc_amount = free_sc["sc_amount"] if free_sc["valid"] else None
                                        casino_name = None
                                        title_lower = title.lower()
                                        for site in DEFAULT_SITES:
                                            if site["name"].lower() in title_lower:
                                                casino_name = site["name"]
                                                break
                                        if not casino_name:
                                            casino_name = title.split(' - ')[0].strip() if ' - ' in title else title[:40]
                                        extracted_link = extract_link_from_body(body)
                                        all_posts.append({
                                            "casino_name": casino_name,
                                            "sc_amount": sc_amount,
                                            "url": extracted_link if extracted_link else "",
                                            "created_utc": post_time,
                                            "is_free_spin": sc_amount is None
                                        })
                except requests.exceptions.Timeout:
                    print(f"[Reddit] Timeout fetching daily freebies {sr}/{sort}")
                except requests.exceptions.ConnectionError:
                    print(f"[Reddit] Connection error fetching daily freebies {sr}/{sort}")
                except Exception as e:
                    print(f"[Reddit] Error fetching daily freebies {sr}/{sort}: {e}")
        seen = set()
        unique = []
        for post in all_posts:
            pid = hashlib.md5((post["url"] or str(post["created_utc"])).encode()).hexdigest()
            if pid not in seen:
                seen.add(pid)
                unique.append(post)
        unique.sort(key=lambda x: x.get("created_utc", 0), reverse=True)
        return unique[:50]
    except Exception as e:
        print(f"[Reddit] fetch_daily_freebies failed: {e}")
        traceback.print_exc()
        return []

def fetch_discord_freebies(channel_id=None):
    """Fetch the last 50 messages from a Discord channel and format as daily_posts entries."""
    try:
        cid = channel_id or DISCORD_CHANNEL_ID
        url = f"https://discord.com/api/v10/channels/{cid}/messages"
        headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}", "Content-Type": "application/json"}
        resp = requests.get(url, headers=headers, params={"limit": 50}, timeout=10)
        if resp.status_code != 200:
            return []
        posts = []
        for msg in resp.json():
            ts = msg.get("timestamp", "")
            created = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() if ts else time.time()
            # Collect URLs from content text, embeds, and attachments
            urls = []
            content = msg.get("content", "")
            urls += re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', content)
            for e in msg.get("embeds", []):
                eu = e.get("url", "")
                if eu:
                    urls.append(eu)
            for a in msg.get("attachments", []):
                au = a.get("url", "")
                if au:
                    urls.append(au)
            # Deduplicate and pick first valid URL
            seen_urls = set()
            target_url = None
            for u in urls:
                if u not in seen_urls:
                    seen_urls.add(u)
                    if target_url is None:
                        target_url = u
            if not target_url:
                continue
            # Identify casino from URL or content
            casino_name = "Unknown"
            url_lower = target_url.lower()
            content_lower = content.lower()
            combined_text = content_lower + " " + url_lower
            sites = load_sites()
            for site in sites:
                sn = site["name"].lower()
                sd = site["domain"].lower()
                if sn in combined_text or sd in combined_text or sn.replace(" ","") in url_lower or sd.replace("www.","") in target_url.lower():
                    casino_name = site["name"]
                    break
            posts.append({
                "casino_name": casino_name,
                "sc_amount": None,
                "url": target_url,
                "created_utc": created,
                "is_free_spin": True
            })
        posts.sort(key=lambda x: x.get("created_utc", 0), reverse=True)
        return posts[:50]
    except:
        return []

def daily_freebies_loop():
    while True:
        try:
            reddit_posts = fetch_daily_freebies()
            discord_posts = fetch_discord_freebies()
            seen_urls = set()
            merged = []
            for post in reddit_posts + discord_posts:
                uid = post.get("url", "") or str(post.get("created_utc", ""))
                if uid not in seen_urls:
                    seen_urls.add(uid)
                    merged.append(post)
            merged.sort(key=lambda x: x.get("created_utc", 0), reverse=True)
            with state_lock:
                state["daily_posts"] = merged[:50]
        except:
            pass
        time.sleep(300)

def claim_scheduler_loop():
    """Background thread that auto-claims daily bonuses when 24h cooldown has elapsed"""
    while True:
        try:
            schedule = load_claim_schedule()
            accounts = load_accounts()
            now = time.time()
            changed = False
            for domain, info in schedule.items():
                if info.get("status") == "claiming":
                    continue
                if info.get("status") == "error":
                    continue
                if domain not in accounts:
                    continue
                last_claim = info.get("last_claim", 0)
                if now - last_claim >= 86400:
                    info["status"] = "claiming"
                    save_claim_schedule(schedule)
                    def do_claim(d, s):
                        try:
                            accts = load_accounts()
                            if d not in accts:
                                s["status"] = "error"
                                save_claim_schedule(s)
                                return
                            auto = CasinoAutomation(headless=HEADLESS_MODE)
                            if auto.start():
                                if auto.login(d, accts[d]["username"], accts[d]["password"]):
                                    sc = auto.claim_daily_bonus(d)
                                    if sc > 0:
                                        s["last_claim"] = time.time()
                                        s["status"] = "done"
                                        with state_lock:
                                            state["claimed"] += 1
                                            state["sc_total"] = round(state["sc_total"] + sc, 2)
                                        accts = load_accounts()
                                        accts[d]["sc_total"] = round(accts[d].get("sc_total", 0) + sc, 2)
                                        save_accounts(accts)
                                    else:
                                        s["status"] = "error"
                                else:
                                    s["status"] = "error"
                                auto.close()
                            else:
                                s["status"] = "error"
                        except:
                            s["status"] = "error"
                        save_claim_schedule(s)
                    t = threading.Thread(target=do_claim, args=(domain, info), daemon=True)
                    t.start()
                    changed = True
            if changed:
                save_claim_schedule(schedule)
        except:
            pass
        time.sleep(60)

def flood_discord_last_24h():
    """Fetch and post all Free SC/Spins from last 24 hours to Discord"""
    try:
        from datetime import datetime
        print(f"[{datetime.now()}] Starting Discord flood for last 24 hours...")
        
        all_posts = []
        for sr in SUBREDDITS:
            for sort in ["hot", "new", "top"]:
                url = f"https://www.reddit.com/r/{sr}/{sort}.json?limit=100"
                try:
                    resp = requests.get(url, headers={
                        "User-Agent": USER_AGENT,
                        "Accept": "application/json"
                    }, timeout=15)
                    if resp.status_code == 200:
                        data = resp.json()
                        if "data" in data and "children" in data["data"]:
                            for child in data["data"]["children"]:
                                p = child["data"]
                                post_time = p.get("created_utc", 0)
                                title = p.get("title", "")
                                body = p.get("selftext", "")
                                
                                if time.time() - post_time <= 86400:
                                    free_sc = is_free_sc_post(title, body)
                                    if free_sc["valid"] or is_valid_free_post(title, body):
                                        all_posts.append({
                                            "title": title,
                                            "url": "https://reddit.com" + p.get("permalink"),
                                            "body": body,
                                            "author": p.get("author"),
                                            "subreddit": p.get("subreddit", sr),
                                            "created_utc": post_time,
                                            "free_sc_amount": free_sc.get("sc_amount") if free_sc["valid"] else None
                                        })
                except Exception as e:
                    print(f"[{datetime.now()}] Error fetching {sort}: {e}")
                    continue
        
        seen_ids = set()
        unique_posts = []
        for post in all_posts:
            pid = hashlib.md5(post["url"].encode()).hexdigest()
            if pid not in seen_ids:
                seen_ids.add(pid)
                unique_posts.append(post)
        
        unique_posts.sort(key=lambda x: x.get("created_utc", 0), reverse=True)
        
        print(f"[{datetime.now()}] Found {len(unique_posts)} unique Free SC/Spin posts")
        
        posted = 0
        freecash_posted = 0
        for post in unique_posts:
            extracted_link = extract_link_from_body(post.get("body", ""))
            sc_amount = post.get("free_sc_amount")
            if sc_amount:
                success = post_freecash_discord(
                    post["title"],
                    extracted_link,
                    post.get("created_utc", 0),
                    sc_amount
                )
                if success:
                    freecash_posted += 1
            else:
                success = post_to_discord(
                    post["title"],
                    extracted_link,
                    post.get("created_utc", 0),
                    is_live=False  # Use flood webhook
                )
                if success:
                    posted += 1
            time.sleep(1.5)
        
        print(f"[{datetime.now()}] Flood complete! Posted {posted} alerts to flood channel, {freecash_posted} to freecash channel")
        return posted
    except Exception as e:
        print(f"[{datetime.now()}] Flood error: {e}")
        return 0

# ================== DATA STORAGE ==================
state = {
    "scanned": 0,
    "found": 0,
    "claimed": 0,
    "sc_total": 0.0,
    "links": [],
    "runtime": 0,
    "status": "offline",
    "last_alert": None,
    "bot_status": "offline",
    "server_start": time.time(),
    "daily_posts": [],
    "claim_schedule": {},
}
monitor_feed = deque(maxlen=50)
state_lock = threading.Lock()
tracked_users = {}
tracked_lock = threading.Lock()

# Load or create admin users
def load_admin_users():
    if ADMIN_USERS_FILE.exists():
        with open(ADMIN_USERS_FILE, 'r') as f:
            return json.load(f)
    return {"admins": [], "sessions": {}}

def save_admin_users(data):
    with open(ADMIN_USERS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# Load or create approved users
def load_approved_users():
    if APPROVED_USERS_FILE.exists():
        with open(APPROVED_USERS_FILE, 'r') as f:
            return json.load(f)
    return {"discord_ids": [], "emails": {}}

def save_approved_users(data):
    with open(APPROVED_USERS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

admin_data = load_admin_users()
approved_data = load_approved_users()

# ================== SITES DATABASE ==================
SITES_FILE = SCRIPT_DIR / "sites.json"
ACCOUNTS_FILE = SCRIPT_DIR / "accounts.json"

# Default sweepstakes sites
DEFAULT_SITES = [
    # S TIER (28)
    {"name": "Crown Coins", "domain": "crowncoinscasino.com", "url": "https://www.crowncoinscasino.com", "sc_per_day": 1, "has_spins": True},
    {"name": "McLuck", "domain": "mcluck.com", "url": "https://www.mcluck.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Spree", "domain": "spree.com", "url": "https://www.spree.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Pulsz", "domain": "pulsz.com", "url": "https://www.pulsz.com", "sc_per_day": 1, "has_spins": True},
    {"name": "PlayFame", "domain": "playfame.com", "url": "https://www.playfame.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Jackpota", "domain": "jackpota.com", "url": "https://www.jackpota.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Stake.us", "domain": "stake.us", "url": "https://stake.us", "sc_per_day": 1, "has_spins": True},
    {"name": "Hello Millions", "domain": "hellomillions.com", "url": "https://www.hellomillions.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Shuffle", "domain": "shuffle.com", "url": "https://www.shuffle.com", "sc_per_day": 1, "has_spins": True},
    {"name": "MyPrize", "domain": "myprize.com", "url": "https://www.myprize.com", "sc_per_day": 1, "has_spins": True},
    {"name": "LoneStar Casino", "domain": "lonestarcasino.com", "url": "https://www.lonestarcasino.com", "sc_per_day": 1, "has_spins": True},
    {"name": "RealPrize", "domain": "realprize.com", "url": "https://www.realprize.com", "sc_per_day": 1, "has_spins": True},
    {"name": "WOW Vegas", "domain": "wowvegas.com", "url": "https://www.wowvegas.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Modo", "domain": "modocasino.com", "url": "https://www.modocasino.com", "sc_per_day": 1, "has_spins": True},
    {"name": "SpinBlitz", "domain": "spinblitz.com", "url": "https://www.spinblitz.com", "sc_per_day": 1, "has_spins": True},
    {"name": "ReBet", "domain": "rebet.com", "url": "https://www.rebet.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Pulsz Bingo", "domain": "pulszbingo.com", "url": "https://www.pulszbingo.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Legendz", "domain": "legendz.com", "url": "https://www.legendz.com", "sc_per_day": 1, "has_spins": True},
    {"name": "LuckyHands", "domain": "luckyhands.com", "url": "https://www.luckyhands.com", "sc_per_day": 1, "has_spins": True},
    {"name": "MegaBonanza", "domain": "megabonanza.com", "url": "https://www.megabonanza.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Card Crush", "domain": "cardcrush.com", "url": "https://www.cardcrush.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Dogg House", "domain": "dogghousecasino.com", "url": "https://www.dogghousecasino.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Zula Casino", "domain": "zulacasino.com", "url": "https://www.zulacasino.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Fortune Wins", "domain": "fortunecoins.com", "url": "https://www.fortunecoins.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Sportzino", "domain": "sportzino.com", "url": "https://www.sportzino.com", "sc_per_day": 1, "has_spins": True},
    {"name": "LuckyLand Slots", "domain": "luckylandslots.com", "url": "https://www.luckylandslots.com", "sc_per_day": 1, "has_spins": True},
    {"name": "LuckyLand Casino", "domain": "luckylandcasino.com", "url": "https://www.luckylandcasino.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Chumba Casino", "domain": "chumbacasino.com", "url": "https://www.chumbacasino.com", "sc_per_day": 1, "has_spins": True},
    # A TIER (31)
    {"name": "CoinsBack Casino", "domain": "coinsback.com", "url": "https://www.coinsback.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Coin Wizard", "domain": "coinwizard.com", "url": "https://www.coinwizard.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Clash5", "domain": "clash5.com", "url": "https://www.clash5.com", "sc_per_day": 1, "has_spins": True},
    {"name": "ThrillCoins", "domain": "thrillcoins.com", "url": "https://www.thrillcoins.com", "sc_per_day": 1, "has_spins": True},
    {"name": "SweetSweeps", "domain": "sweetsweeps.com", "url": "https://www.sweetsweeps.com", "sc_per_day": 1, "has_spins": True},
    {"name": "LuckyRush", "domain": "luckyrush.com", "url": "https://www.luckyrush.com", "sc_per_day": 1, "has_spins": True},
    {"name": "FortunaRush", "domain": "fortunarush.com", "url": "https://www.fortunarush.com", "sc_per_day": 1, "has_spins": True},
    {"name": "BangCoins", "domain": "bangcoins.com", "url": "https://www.bangcoins.com", "sc_per_day": 1, "has_spins": True},
    {"name": "DimeSweeps", "domain": "dimesweeps.com", "url": "https://www.dimesweeps.com", "sc_per_day": 1, "has_spins": True},
    {"name": "SweepsRoyal", "domain": "sweepsroyal.com", "url": "https://www.sweepsroyal.com", "sc_per_day": 1, "has_spins": True},
    {"name": "RichSweeps", "domain": "richsweeps.com", "url": "https://www.richsweeps.com", "sc_per_day": 1, "has_spins": True},
    {"name": "SpeedSweeps", "domain": "speedsweeps.com", "url": "https://www.speedsweeps.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Ace", "domain": "acecasino.com", "url": "https://www.acecasino.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Jackpot Go", "domain": "jackpotgo.com", "url": "https://www.jackpotgo.com", "sc_per_day": 1, "has_spins": True},
    {"name": "WinBonanza", "domain": "winbonanza.com", "url": "https://www.winbonanza.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Stackr", "domain": "stackr.com", "url": "https://www.stackr.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Novig", "domain": "novig.com", "url": "https://www.novig.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Dara", "domain": "daracasino.com", "url": "https://www.daracasino.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Chanced", "domain": "chanced.com", "url": "https://www.chanced.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Rolla", "domain": "rolla.com", "url": "https://www.rolla.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Clubs", "domain": "clubs.casino", "url": "https://www.clubs.casino", "sc_per_day": 1, "has_spins": True},
    {"name": "ChipNWin", "domain": "chipnwin.com", "url": "https://www.chipnwin.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Legacy Arcade", "domain": "legacyarcade.com", "url": "https://www.legacyarcade.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Golden Hearts", "domain": "goldenheartsgames.com", "url": "https://www.goldenheartsgames.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Fliff", "domain": "fliff.com", "url": "https://www.fliff.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Thrillz", "domain": "thrillz.com", "url": "https://www.thrillz.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Global Poker", "domain": "globalpoker.com", "url": "https://www.globalpoker.com", "sc_per_day": 1, "has_spins": True},
    {"name": "American Luck", "domain": "americanluck.com", "url": "https://www.americanluck.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Moozi", "domain": "moozi.com", "url": "https://www.moozi.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Punt", "domain": "punt.com", "url": "https://www.punt.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Yay", "domain": "yaycasino.com", "url": "https://www.yaycasino.com", "sc_per_day": 1, "has_spins": True},
    # B TIER (22)
    {"name": "TaoSweeps", "domain": "taosweeps.com", "url": "https://www.taosweeps.com", "sc_per_day": 1, "has_spins": True},
    {"name": "OceanKing", "domain": "oceankingcasino.com", "url": "https://www.oceankingcasino.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Scoop", "domain": "scoopcasino.com", "url": "https://www.scoopcasino.com", "sc_per_day": 1, "has_spins": True},
    {"name": "SweepsUSA", "domain": "sweepsusa.com", "url": "https://www.sweepsusa.com", "sc_per_day": 1, "has_spins": True},
    {"name": "SweepNext", "domain": "sweepnext.com", "url": "https://www.sweepnext.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Wild", "domain": "wild.io", "url": "https://www.wild.io", "sc_per_day": 1, "has_spins": True},
    {"name": "Baba", "domain": "babacasino.com", "url": "https://www.babacasino.com", "sc_per_day": 1, "has_spins": True},
    {"name": "High5", "domain": "high5casino.com", "url": "https://www.high5casino.com", "sc_per_day": 1, "has_spins": True},
    {"name": "LuckyBits Vegas", "domain": "luckybitsvegas.com", "url": "https://www.luckybitsvegas.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Lavish Luck", "domain": "lavishluck.com", "url": "https://www.lavishluck.com", "sc_per_day": 1, "has_spins": True},
    {"name": "AcornFun", "domain": "acornfun.com", "url": "https://www.acornfun.com", "sc_per_day": 1, "has_spins": True},
    {"name": "LunaLand", "domain": "lunaland.com", "url": "https://www.lunaland.com", "sc_per_day": 1, "has_spins": True},
    {"name": "LuckParty", "domain": "luckparty.com", "url": "https://www.luckparty.com", "sc_per_day": 1, "has_spins": True},
    {"name": "PeakPlay", "domain": "peakplay.com", "url": "https://www.peakplay.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Ruby Sweeps", "domain": "rubysweeps.com", "url": "https://www.rubysweeps.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Cluck", "domain": "cluck.com", "url": "https://www.cluck.com", "sc_per_day": 1, "has_spins": True},
    {"name": "SpinSaga", "domain": "spinsaga.com", "url": "https://www.spinsaga.com", "sc_per_day": 1, "has_spins": True},
    {"name": "SorceryReels", "domain": "sorceryreels.com", "url": "https://www.sorceryreels.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Betr", "domain": "betr.com", "url": "https://www.betr.com", "sc_per_day": 1, "has_spins": True},
    {"name": "SpinPals", "domain": "spinpals.com", "url": "https://www.spinpals.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Sidepot", "domain": "sidepot.com", "url": "https://www.sidepot.com", "sc_per_day": 1, "has_spins": True},
    {"name": "Scrooge", "domain": "scroogecasino.com", "url": "https://www.scroogecasino.com", "sc_per_day": 1, "has_spins": True},
    {"name": "BetOnline", "domain": "betonline.ag", "url": "https://www.betonline.ag", "sc_per_day": 1, "has_spins": False},
]

def load_sites():
    if SITES_FILE.exists():
        with open(SITES_FILE, 'r') as f:
            data = json.load(f)
        # Merge any missing DEFAULT_SITES entries (e.g. newly added casinos)
        existing = {s["domain"] for s in data}
        merged = list(data)
        for s in DEFAULT_SITES:
            if s["domain"] not in existing:
                merged.append(s)
                existing.add(s["domain"])
        if len(merged) > len(data):
            save_sites(merged)
        return merged
    return DEFAULT_SITES

def save_sites(data):
    with open(SITES_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def load_accounts():
    if ACCOUNTS_FILE.exists():
        with open(ACCOUNTS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_accounts(data):
    with open(ACCOUNTS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# Initialize sites if not exists
if not SITES_FILE.exists():
    save_sites(DEFAULT_SITES)

# ================== DASHBOARD CSS ==================
DASHBOARD_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Righteous&family=Outfit:wght@400;500;600;700;800&display=swap');

* { margin: 0; padding: 0; box-sizing: border-box; }

:root {
    --bg: #0a0a0a;
    --bg2: #111111;
    --bg3: #1a1a1a;
    --surface: #1a1a1a;
    --surface-hover: #222;
    --border: #2a2a2a;
    --border-light: rgba(255,255,255,0.1);
    --text: #e0e0e0;
    --text-dim: #888;
    --text-bright: #ffffff;
    --text-muted: #555;
    --accent: #a855f7;
    --accent-dim: #9333ea;
    --accent-glow: rgba(168,85,247,0.25);
    --glass-bg: rgba(16,16,16,0.85);
    --glass-border: rgba(168,85,247,0.15);
    --glass-shadow: 0 8px 32px rgba(0,0,0,0.4);
    --scrollbar-bg: #1a1a1a;
    --scrollbar-thumb: #a855f7;
    --shadow: 0 4px 20px rgba(0,0,0,0.5);
}

[data-theme="light"] {
    --bg: #f5f5f5;
    --bg2: #eeeeee;
    --bg3: #e4e4e4;
    --surface: #ffffff;
    --surface-hover: #f0f0f0;
    --border: #d0d0d0;
    --border-light: rgba(0,0,0,0.1);
    --text: #222222;
    --text-dim: #777;
    --text-bright: #000000;
    --text-muted: #999;
    --accent: #a855f7;
    --accent-dim: #9333ea;
    --glass-bg: rgba(255,255,255,0.85);
    --glass-border: rgba(168,85,247,0.2);
    --glass-shadow: 0 8px 32px rgba(0,0,0,0.1);
    --scrollbar-bg: #e0e0e0;
    --scrollbar-thumb: #a855f7;
    --shadow: 0 4px 20px rgba(0,0,0,0.1);
}

body {
    font-family: 'Outfit', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: var(--bg);
    animation: pageFadeIn 0.4s ease-out;
    color: var(--text);
    min-height: 100vh;
    position: relative;
    overflow-x: hidden;
    transition: background 0.3s, color 0.3s;
}

/* Dashboard Sidebar */
.dashboard-sidebar {
    position: fixed;
    top: 0;
    left: -260px;
    width: 260px;
    height: 100vh;
    background: var(--glass-bg);
    backdrop-filter: blur(20px);
    border-right: 1px solid var(--glass-border);
    z-index: 1000;
    transition: left 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    display: flex;
    flex-direction: column;
    box-shadow: 4px 0 30px rgba(0, 0, 0, 0.3);
}

.dashboard-sidebar.open {
    left: 0;
}

.sidebar-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100vh;
    background: rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(8px);
    z-index: 999;
    opacity: 0;
    visibility: hidden;
    transition: all 0.4s ease;
    pointer-events: none;
}

.sidebar-overlay.active {
    opacity: 1;
    visibility: visible;
    pointer-events: auto;
}

.sidebar-header {
    padding: 24px 20px;
    border-bottom: 1px solid var(--glass-border);
}

.sidebar-header h2 {
    font-family: 'Outfit', sans-serif;
    font-weight: 800;
    font-size: 1.3rem;
    color: var(--text-bright);
    letter-spacing: 3px;
    margin: 0;
}

.sidebar-nav {
    flex: 1;
    padding: 16px 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.sidebar-link {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 14px 16px;
    border-radius: 12px;
    color: var(--text-dim);
    text-decoration: none;
    font-weight: 600;
    transition: all 0.3s ease;
}

.sidebar-link svg {
    opacity: 0.6;
    transition: all 0.3s ease;
}

.sidebar-link:hover {
    background: var(--surface-hover);
    color: var(--text-bright);
}

.sidebar-link:hover svg {
    opacity: 1;
}

.sidebar-link.active {
    background: rgba(168,85,247,0.12);
    color: var(--accent);
}

.sidebar-link.active svg {
    opacity: 1;
    color: var(--accent);
}

.sidebar-footer {
    padding: 16px 12px;
    border-top: 1px solid var(--glass-border);
}

.settings-link {
    margin-top: auto;
}

.header {
    background: var(--bg2);
    border-bottom: 1px solid var(--border);
    padding: 16px 40px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    backdrop-filter: blur(10px);
    position: relative;
    z-index: 50;
    box-shadow: 0 1px 0 rgba(168,85,247,0.08);
}

.header-left {
    display: flex;
    align-items: center;
    gap: 16px;
}

.theme-toggle {
    background: none;
    border: 1px solid var(--border);
    border-radius: 50%;
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    color: var(--text);
    font-size: 1.1rem;
    transition: all 0.3s ease;
    background: var(--surface);
}

.theme-toggle:hover {
    border-color: var(--accent);
    transform: scale(1.1);
}

.status-dot {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #ff4444;
    margin-right: 8px;
    transition: background 0.3s;
}

.status-dot.online {
    background: #00ff88;
    animation: pulse 2s infinite;
}

.status-dot.checking {
    background: #FFD700;
    animation: pulse 1s infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(0, 255, 136, 0.7); }
    50% { opacity: 0.7; box-shadow: 0 0 8px 4px rgba(0, 255, 136, 0.3); }
}

.status-badge {
    display: flex;
    align-items: center;
    gap: 8px;
}

/* Sidebar trigger (fixed position on left edge) */
.sidebar-trigger {
    position: fixed;
    left: 0;
    top: 50%;
    transform: translateY(-50%);
    width: 32px;
    height: 64px;
    background: var(--glass-bg);
    backdrop-filter: blur(20px);
    border: 1px solid var(--glass-border);
    border-left: none;
    border-radius: 0 8px 8px 0;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    color: var(--text-dim);
    transition: all 0.3s ease;
    z-index: 1001;
}
.sidebar-trigger:hover {
    color: var(--accent);
    border-color: var(--accent);
}
.sidebar-trigger svg {
    transition: transform 0.3s ease;
}
.sidebar-trigger.open svg {
    transform: rotate(180deg);
}

@keyframes pageFadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}

/* Entrance Animations */
@keyframes slideInUp {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
}

@keyframes fadeInSlide {
    from { opacity: 0; transform: translateX(-20px); }
    to { opacity: 1; transform: translateX(0); }
}

/* Container */
.container { 
    max-width: 1400px; 
    margin: 0 auto; 
    padding: 30px 20px;
    padding-left: 80px;
}

/* Stats Grid */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 20px;
    margin-bottom: 40px;
}

.stat-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 24px;
    text-align: center;
    transition: all 0.3s ease;
    animation: slideInUp 0.5s ease-out;
}

.stat-card:hover {
    border-color: var(--accent);
    transform: translateY(-4px);
    box-shadow: 0 12px 24px rgba(0, 0, 0, 0.15), 0 0 20px var(--accent-glow);
}

.stat-card .icon { font-size: 2rem; margin-bottom: 12px; opacity: 0.7; }

.stat-card .value {
    font-size: 2.5rem;
    font-weight: 800;
    color: var(--text-bright);
    margin-bottom: 8px;
    font-family: 'Outfit', sans-serif;
}

.stat-card .label {
    color: var(--text-dim);
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 1px;
}

.stat-card .progress-bar {
    margin-top: 12px;
    height: 4px;
    background: var(--bg);
    border-radius: 2px;
    overflow: hidden;
}

.stat-card .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--accent), #d946ef);
    border-radius: 2px;
    transition: width 0.5s ease;
}

/* Section Title */
.section-title {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 28px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--border-light);
}

.section-title span:first-child {
    font-family: 'Outfit', sans-serif;
    font-weight: 700;
    font-size: 1.2rem;
    color: var(--text-bright);
    letter-spacing: 2px;
}

/* Links List */
.links-list {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    overflow: hidden;
    max-height: 500px;
}

.links-list.scrollable {
    overflow-y: auto;
    scrollbar-width: thin;
    scrollbar-color: var(--scrollbar-thumb) var(--scrollbar-bg);
}

.links-list.scrollable::-webkit-scrollbar {
    width: 8px;
}

.links-list.scrollable::-webkit-scrollbar-track {
    background: var(--scrollbar-bg);
    border-radius: 4px;
}

.links-list.scrollable::-webkit-scrollbar-thumb {
    background: var(--scrollbar-thumb);
    border-radius: 4px;
}

.links-list.scrollable::-webkit-scrollbar-thumb:hover {
    background: var(--accent-dim);
}

.link-item {
    padding: 18px 22px;
    border-bottom: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: center;
    transition: all 0.3s ease;
    animation: fadeInSlide 0.6s ease-out;
}

.link-item:hover { 
    background: var(--surface-hover);
    border-left: 3px solid var(--accent);
}

.link-item:last-child { border-bottom: none; }

.link-item .title {
    font-weight: 600;
    color: var(--text-bright);
    margin-bottom: 6px;
    font-size: 0.95rem;
}

.link-item .meta { color: var(--text-muted); font-size: 0.8rem; font-family: 'Outfit', sans-serif; }

.link-item .btn {
    padding: 8px 20px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    text-decoration: none;
    font-size: 0.85rem;
    font-weight: 600;
    transition: all 0.3s ease;
    white-space: nowrap;
}

.link-item .btn:hover { 
    background: var(--accent);
    color: #fff;
    border-color: var(--accent);
    transform: translateX(4px);
    box-shadow: 0 0 16px var(--accent-glow);
}

/* Status Badge */
.status-badge {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 20px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 600;
}

.live-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #ff4444;
    animation: pulse 2s infinite;
}

/* User Profile */
.user-profile {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    border: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    font-size: 1.2rem;
    transition: all 0.3s ease;
}

.user-profile:hover {
    border-color: var(--accent);
    background: var(--surface-hover);
}

.user-avatar {
    display: flex;
    align-items: center;
    justify-content: center;
}

/* Empty State */
.empty-state {
    padding: 60px 20px;
    text-align: center;
    color: var(--text-muted);
    font-size: 0.95rem;
}

/* Refresh Button */
.refresh-btn {
    position: fixed;
    bottom: 24px;
    right: 24px;
    width: 56px;
    height: 56px;
    border-radius: 50%;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--text);
    font-size: 1.2rem;
    cursor: pointer;
    box-shadow: var(--shadow);
    font-family: 'Outfit', sans-serif;
    font-weight: 700;
    transition: all 0.3s ease;
}

.refresh-btn:hover {
    background: var(--accent);
    color: #fff;
    border-color: var(--accent);
    transform: scale(1.1);
    box-shadow: 0 0 20px var(--accent-glow);
}

/* Post time */
.post-time {
    color: var(--accent-dim);
    font-size: 0.8rem;
}

/* Accounts Sidebar */
.accounts-tab {
    position: fixed;
    top: 50%;
    left: 0;
    transform: translateY(-50%);
    background: var(--glass-bg);
    backdrop-filter: blur(10px);
    border: 1px solid var(--glass-border);
    border-radius: 0 12px 12px 0;
    padding: 16px 12px;
    cursor: pointer;
    z-index: 99;
    transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: var(--glass-shadow);
}

.accounts-tab:hover {
    left: 4px;
    transform: translateY(-50%) scale(1.02);
}

.accounts-lines {
    display: flex;
    flex-direction: column;
    gap: 6px;
    width: 20px;
}

.accounts-line {
    width: 100%;
    height: 2px;
    background: var(--text);
    border-radius: 2px;
    transition: all 0.3s ease;
}

.accounts-line:nth-child(2) {
    width: 70%;
}

.accounts-line:nth-child(3) {
    width: 50%;
}

.accounts-tab:hover .accounts-line {
    width: 100%;
}

.accounts-tab:hover .accounts-line:nth-child(2) {
    width: 80%;
}

.accounts-sidebar {
    position: fixed;
    top: 0;
    left: -320px;
    width: 300px;
    height: 100vh;
    background: var(--glass-bg);
    backdrop-filter: blur(20px);
    border-right: 1px solid var(--glass-border);
    box-shadow: var(--glass-shadow);
    padding: 32px 24px;
    display: flex;
    flex-direction: column;
    z-index: 98;
    transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
    overflow-y: auto;
}

.accounts-sidebar.open {
    left: 0;
}

/* Profiles Page */
.profiles-container {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: 20px;
    margin-bottom: 40px;
}

.profile-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 24px;
    transition: all 0.3s ease;
}

.profile-card:hover {
    border-color: var(--accent);
    box-shadow: 0 8px 24px rgba(0,0,0,0.12);
}

.profile-card h3 {
    font-family: 'Outfit', sans-serif;
    font-weight: 700;
    color: var(--text-bright);
    margin-bottom: 16px;
    font-size: 1.1rem;
    letter-spacing: 1px;
}

.profile-field {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-bottom: 12px;
}

.profile-field label {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--text-dim);
}

.profile-field input {
    padding: 10px 14px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    font-family: 'Outfit', sans-serif;
    font-size: 0.95rem;
}

.profile-field input:focus {
    outline: none;
    border-color: var(--accent);
}

.profile-actions {
    display: flex;
    gap: 8px;
    margin-top: 16px;
}

.profile-actions button {
    flex: 1;
    padding: 10px;
    border: 1px solid var(--border);
    border-radius: 8px;
    font-family: 'Outfit', sans-serif;
    font-weight: 600;
    font-size: 0.85rem;
    cursor: pointer;
    transition: all 0.3s ease;
    background: var(--surface);
    color: var(--text);
}

.profile-actions button:hover {
    background: var(--accent);
    color: #fff;
    border-color: var(--accent);
}

.profile-actions .delete-btn:hover {
    background: #ff4444;
    color: #fff;
    border-color: #ff4444;
}

/* Add Casino Modal */
.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100vh;
    background: rgba(0,0,0,0.6);
    backdrop-filter: blur(6px);
    z-index: 200;
    display: none;
    justify-content: center;
    align-items: center;
}

.modal-overlay.active {
    display: flex;
}

.modal-box {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    width: 90%;
    max-width: 500px;
    max-height: 80vh;
    overflow-y: auto;
    padding: 32px;
}

.modal-box h2 {
    font-family: 'Outfit', sans-serif;
    font-weight: 700;
    color: var(--text-bright);
    margin-bottom: 20px;
    font-size: 1.3rem;
    letter-spacing: 1px;
}

.modal-search {
    width: 100%;
    padding: 12px 16px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    color: var(--text);
    font-family: 'Outfit', sans-serif;
    font-size: 0.95rem;
    margin-bottom: 16px;
}

.modal-search:focus {
    outline: none;
    border-color: var(--accent);
}

.casino-list-item {
    padding: 12px 16px;
    border: 1px solid var(--border);
    border-radius: 10px;
    margin-bottom: 8px;
    cursor: pointer;
    transition: all 0.3s ease;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.casino-list-item:hover {
    background: var(--surface-hover);
    border-color: var(--accent);
}

.casino-list-item span {
    color: var(--text);
    font-weight: 600;
}

.casino-list-item .add-icon {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    border: 2px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1rem;
    color: var(--text-dim);
    transition: all 0.3s ease;
}

.casino-list-item:hover .add-icon {
    border-color: var(--accent);
    color: var(--accent);
}

.modal-close {
    position: absolute;
    top: 16px;
    right: 16px;
    background: none;
    border: none;
    color: var(--text-dim);
    font-size: 1.5rem;
    cursor: pointer;
}

/* Add Casino FAB */
.add-casino-btn {
    position: fixed;
    bottom: 90px;
    right: 24px;
    width: 56px;
    height: 56px;
    border-radius: 50%;
    border: 2px dashed var(--border);
    background: var(--surface);
    color: var(--text-dim);
    font-size: 1.5rem;
    cursor: pointer;
    box-shadow: var(--shadow);
    transition: all 0.3s ease;
    display: flex;
    align-items: center;
    justify-content: center;
}

.add-casino-btn:hover {
    border-style: solid;
    border-color: var(--accent);
    color: var(--accent);
    transform: scale(1.1);
}

/* Login Setup Form */
.login-setup {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 20px;
}

.login-setup h3 {
    font-family: 'Righteous', cursive;
    color: var(--text-bright);
    margin-bottom: 16px;
    font-size: 1rem;
    letter-spacing: 1px;
}

.login-fields {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.login-field {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.login-field label {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--text-dim);
}

.login-field input {
    padding: 10px 14px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    font-family: 'Outfit', sans-serif;
    font-size: 0.95rem;
}

.login-field input:focus {
    outline: none;
    border-color: var(--accent);
}

.login-methods {
    display: flex;
    gap: 10px;
    margin-top: 12px;
}

.login-methods .google-btn {
    width: 44px;
    height: 44px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--surface);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.3s ease;
    font-size: 1.2rem;
}

.login-methods .google-btn:hover {
    border-color: var(--accent);
    background: var(--surface-hover);
}

.login-save-btn {
    padding: 10px 20px;
    border: 1px solid var(--border);
    border-radius: 8px;
    font-family: 'Outfit', sans-serif;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s ease;
    background: var(--surface);
    color: var(--text);
}

.login-save-btn:hover {
    background: var(--accent);
    color: var(--bg);
    border-color: var(--accent);
}

/* Mobile Responsive */
@media (max-width: 768px) {
    .container {
        padding: 20px 15px;
        padding-top: 80px;
    }
    
    .header {
        padding: 16px 15px;
    }
    
    .stats-grid {
        grid-template-columns: 1fr;
    }
    
    .sidebar-link {
        padding: 12px 14px;
    }
    
    .link-item {
        flex-direction: column;
        align-items: flex-start;
        gap: 10px;
    }
    
    .link-item .btn {
        align-self: flex-end;
    }

    .profiles-container {
        grid-template-columns: 1fr;
    }
}

/* Profile Dropdown */
.user-profile {
    position: relative;
}
.profile-dropdown {
    position: absolute;
    top: 48px;
    right: 0;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    min-width: 180px;
    box-shadow: 0 12px 40px rgba(0,0,0,0.4);
    opacity: 0;
    visibility: hidden;
    transform: translateY(-8px);
    transition: all 0.25s ease;
    z-index: 200;
    overflow: hidden;
}
.profile-dropdown.show {
    opacity: 1;
    visibility: visible;
    transform: translateY(0);
}
.profile-dropdown a {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 14px 18px;
    color: var(--text);
    text-decoration: none;
    font-size: 0.9rem;
    font-weight: 500;
    transition: background 0.2s;
}
.profile-dropdown a:hover {
    background: var(--surface-hover);
    color: var(--text-bright);
}
.profile-dropdown a:not(:last-child) {
    border-bottom: 1px solid var(--border);
}

/* Daily Bar Chart */
.daily-bar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px 18px;
    border-bottom: 1px solid var(--border);
    cursor: pointer;
    transition: all 0.3s ease;
    animation: fadeInSlide 0.6s ease-out;
}
.daily-bar:hover {
    background: var(--surface-hover);
    border-left: 3px solid var(--accent);
}
.daily-bar:last-child {
    border-bottom: none;
}
.bar-casino {
    min-width: 140px;
    font-weight: 600;
    font-size: 0.9rem;
    color: var(--text-bright);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.bar-track {
    flex: 1;
    height: 24px;
    background: var(--bg);
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid var(--border);
}
.bar-fill {
    height: 100%;
    border-radius: 12px;
    transition: width 0.6s ease;
    min-width: 4px;
}
.bar-amount {
    min-width: 80px;
    text-align: right;
    font-weight: 700;
    font-size: 0.85rem;
    white-space: nowrap;
}
.bar-time {
    min-width: 180px;
    text-align: right;
    font-size: 0.75rem;
    color: var(--text-muted);
    white-space: nowrap;
}
</style>
"""

# ================== VERIFICATION POPUP ==================
VERIFY_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sweepstakes Monitor</title>
    <style>
* { margin: 0; padding: 0; box-sizing: border-box; }

::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--scrollbar-bg); }
::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--accent-dim); }
* { scrollbar-width: thin; scrollbar-color: var(--scrollbar-thumb) var(--scrollbar-bg); }

:focus-visible { outline: none; box-shadow: 0 0 0 2px var(--accent); }
        body {
            font-family: 'Outfit', sans-serif;
            background: linear-gradient(135deg, #0a0a0a 0%, #000000 100%);
            color: #e0e0e0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .login-box {
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 12px;
            padding: 40px;
            width: 350px;
            text-align: center;
        }
        .login-box h1 {
            font-family: 'Righteous', cursive;
            color: #8B5CF6;
            margin-bottom: 10px;
            font-size: 1.8rem;
        }
        .login-box p { color: #888; margin-bottom: 25px; font-size: 0.9rem; }
        .login-box input {
            width: 100%;
            padding: 12px;
            font-size: 1rem;
            background: #0a0a0a;
            border: 1px solid #333;
            border-radius: 8px;
            color: #fff;
            margin-bottom: 15px;
        }
        .login-box input:focus { outline: none; border-color: #8B5CF6; }
        .login-box button {
            width: 100%;
            padding: 12px;
            font-size: 1rem;
            background: #8B5CF6;
            border: none;
            border-radius: 8px;
            color: #fff;
            cursor: pointer;
            font-weight: 700;
            text-transform: uppercase;
        }
        .login-box button:hover { background: #7C3AED; }
        .error { color: #ff4444; margin-top: 15px; display: none; }
        .helper { font-size: 0.8rem; color: #555; margin-top: 20px; }
@import url('https://fonts.googleapis.com/css2?family=Righteous&family=Outfit:wght@400;500;600;700;800&display=swap');
    </style>
</head>
<body>
    <div class="login-box">
        <h1>SWEEPSTAKES</h1>
        <p>Enter your Discord ID to continue</p>
        <input type="text" id="discord_id" placeholder="Discord ID" maxlength="18">
        <button onclick="verifyDiscord()">ENTER</button>
        <div class="error" id="err">Invalid ID. Try again.</div>
        <div class="helper">Enable Developer Mode in Discord → Right-click → Copy ID</div>
    </div>
<script>
function verifyDiscord() {
    const id = document.getElementById('discord_id').value.trim();
    if (!id) return;
    fetch('/api/verify-discord', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({discord_id: id})
    })
    .then(r => r.json())
    .then(data => {
        if (data.ok) { window.location.href = '/'; }
        else { document.getElementById('err').style.display = 'block'; }
    });
}
document.getElementById('discord_id').addEventListener('keyup', e => {
    if(e.key === 'Enter') verifyDiscord();
});
</script>
</body>
</html>"""

# ================== LICENSE PAGE ==================
LICENSE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>License Required</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Righteous&family=Outfit:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body {
            font-family: 'Outfit', system-ui, sans-serif;
            min-height: 100vh; display: flex; justify-content: center; align-items: center;
            padding: 24px; color: #fafafa;
            background: linear-gradient(135deg, #0a0a0a 0%, #000000 100%);
            background-image:
                radial-gradient(ellipse 120% 80% at 50% -20%, rgba(139,92,246,0.12), transparent 55%),
                linear-gradient(180deg, #0a0a0a 0%, #050505 40%);
        }
        .license-box {
            width: 100%; max-width: 440px;
            background: #1a1a1a; border: 1px solid #333;
            padding: clamp(32px,5vw,44px) clamp(28px,4vw,40px);
            border-radius: 16px; text-align: center;
            box-shadow: 0 24px 60px rgba(0,0,0,0.55);
        }
        .license-box .icon { font-size: 2.5rem; margin-bottom: 12px; }
        .license-box h1 {
            font-family: 'Righteous', cursive;
            font-size: clamp(1.35rem,4vw,1.75rem);
            color: #fff; margin-bottom: 8px;
        }
        .license-box h1 span { color: #8B5CF6; }
        .license-box p { color: #888; margin-bottom: 28px; line-height: 1.5; font-size: 0.95rem; }
        .license-box input {
            width: 100%; padding: 14px 18px; font-size: 1rem; font-family: inherit;
            background: #0a0a0a; border: 1px solid #333; border-radius: 10px;
            color: #fff; text-align: center; margin-bottom: 16px;
            text-transform: uppercase; letter-spacing: 0.12em;
        }
        .license-box input:focus { outline: none; border-color: #8B5CF6; box-shadow: 0 0 0 1px rgba(139,92,246,0.25); }
        .license-box button {
            width: 100%; padding: 14px; font-size: 1rem; font-family: inherit; font-weight: 700;
            background: linear-gradient(90deg, #7C3AED, #8B5CF6);
            border: none; border-radius: 10px; color: #fff; cursor: pointer;
            transition: transform .2s, filter .2s, box-shadow .2s;
        }
        .license-box button:hover { transform: translateY(-1px); filter: brightness(1.1); box-shadow: 0 10px 28px rgba(139,92,246,0.25); }
        .error { color: #f87171; margin-top: 14px; font-size: 0.875rem; display: none; }
        .error.show { display: block; }
        .footer-text { color: #555; font-size: 0.75rem; margin-top: 24px; }
    </style>
</head>
<body>
    <div class="license-box">
        <div class="icon">🔒</div>
        <h1><span>License</span> Required</h1>
        <p>Enter your license key to access the dashboard</p>
        <input type="text" id="license" placeholder="XXXX-XXXX-XXXX-XXXX" maxlength="19" autocomplete="off">
        <button type="button" onclick="checkLicense()">ACCESS DASHBOARD</button>
        <div class="error" id="error">Invalid license key. Please try again.</div>
        <div class="footer-text">Claim City 2026</div>
    </div>
    <script>
        function formatKey(input) {
            var value = input.toUpperCase().replace(/[^A-Z0-9]/g, '');
            var formatted = '';
            for (var i = 0; i < value.length && i < 16; i++) {
                if (i > 0 && i % 4 === 0) { formatted += '-'; }
                formatted += value[i];
            }
            return formatted;
        }
        document.getElementById('license').addEventListener('input', function(e) { e.target.value = formatKey(e.target.value); });
        document.getElementById('license').addEventListener('keypress', function(e) { if (e.key === 'Enter') { checkLicense(); } });
        function normalizeKey(s) { return (s || '').replace(/[^A-Za-z0-9]/g, '').toUpperCase(); }
        function checkLicense() {
            var err = document.getElementById('error');
            err.classList.remove('show');
            var key = normalizeKey(document.getElementById('license').value);
            if (!key) { err.textContent = 'Enter your license key.'; err.classList.add('show'); return; }
            fetch('/api/license', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({key: key})
            })
            .then(function(res) { if (!res.ok) throw new Error('bad status'); return res.json(); })
            .then(function(data) {
                if (data.valid) { window.location.href = '/'; }
                else { err.textContent = 'Invalid license key. Please try again.'; err.classList.add('show'); }
            })
            .catch(function() { err.textContent = 'Could not reach the server.'; err.classList.add('show'); });
        }
    </script>
</body>
</html>"""

# ================== ACCOUNTS PAGE ==================
ACCOUNTS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Accounts - Sweepstakes Monitor</title>
    """ + DASHBOARD_CSS + """
    <style>
        .accounts-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .site-card {
            background: linear-gradient(145deg, #1a1a1a, #141414);
            border: 1px solid #2a2a2a;
            border-radius: 16px;
            padding: 20px;
            transition: all 0.3s ease;
        }
        .site-card:hover {
            border-color: #8B5CF6;
            transform: translateY(-2px);
        }
        .site-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        .site-name {
            font-family: 'Righteous', cursive;
            font-size: 1.2rem;
            color: #fff;
        }
        .site-status {
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 600;
        }
        .status-active {
            background: rgba(0, 255, 136, 0.15);
            color: #00ff88;
        }
        .status-inactive {
            background: rgba(255, 68, 68, 0.15);
            color: #ff4444;
        }
        .site-info {
            color: #888;
            font-size: 0.9rem;
            margin-bottom: 15px;
        }
        .account-form {
            display: none;
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #2a2a2a;
        }
        .account-form.active {
            display: block;
        }
        .form-group {
            margin-bottom: 12px;
        }
        .form-group label {
            display: block;
            color: #888;
            font-size: 0.85rem;
            margin-bottom: 5px;
        }
        .form-group input {
            width: 100%;
            padding: 10px;
            background: #0a0a0a;
            border: 1px solid #2a2a2a;
            border-radius: 8px;
            color: #fff;
            font-size: 0.9rem;
        }
        .form-group input:focus {
            outline: none;
            border-color: #8B5CF6;
        }
        .btn-claim {
            width: 100%;
            padding: 12px;
            background: linear-gradient(135deg, #8B5CF6, #7C3AED);
            border: none;
            border-radius: 10px;
            color: #fff;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            margin-top: 10px;
        }
        .btn-claim:hover {
            transform: translateY(-1px);
            box-shadow: 0 8px 20px rgba(139, 92, 246, 0.3);
        }
        .btn-claim:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        .sc-total {
            font-size: 1.5rem;
            font-weight: 700;
            color: #8B5CF6;
            margin-top: 10px;
        }
    </style>
</head>
<body>
<div class="dashboard-sidebar" id="dashboard-sidebar">
    <div class="sidebar-header"><h2>MENU</h2></div>
<nav class="sidebar-nav">
        <a href="/" class="sidebar-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="3" width="7" height="7"></rect>
                <rect x="14" y="3" width="7" height="7"></rect>
                <rect x="14" y="14" width="7" height="7"></rect>
                <rect x="3" y="14" width="7" height="7"></rect>
            </svg>
            Main
        </a>
        <a href="/accounts" class="sidebar-link active">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                <circle cx="12" cy="7" r="4"></circle>
            </svg>
            Accounts
        </a>
        <a href="/daily-claim" class="sidebar-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0-3.5 3.5h-5A3.5 3.5 0 0 1 5 5h7"></path>
                <path d="M12 2a4 4 0 0 1 4 4v12a4 4 0 0 1-4 4 4 4 0 0 1-4-4V6a4 4 0 0 1 4-4z"></path>
            </svg>
            Daily Claim
        </a>
        <a href="/daily-claims" class="sidebar-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <polyline points="12 6 12 12 16 14"></polyline>
            </svg>
            Daily Claims
        </a>
        <a href="/profiles" class="sidebar-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                <circle cx="9" cy="7" r="4"></circle>
                <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
                <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
            </svg>
            Profiles
        </a>
        <a href="/proxies" class="sidebar-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
            </svg>
            Proxies
        </a>
        <a href="/membership" class="sidebar-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
                <path d="M2 17l10 5 10-5"></path>
                <path d="M2 12l10 5 10-5"></path>
            </svg>
            Membership
        </a>
    </nav>
    <div class="sidebar-footer">
        <a href="/logout" class="sidebar-link settings-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                <polyline points="16 17 21 12 16 7"></polyline>
                <line x1="21" y1="12" x2="9" y2="12"></line>
            </svg>
            Logout
        </a>
        <a href="/settings" class="sidebar-link settings-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="3"></circle>
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
            </svg>
            Settings
        </a>
    </div>
</div>
<div class="sidebar-trigger" id="sidebarTrigger" onclick="toggleSidebar()" title="Toggle Menu">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
</div>
<div class="sidebar-overlay" id="sidebar-overlay" onclick="closeSidebar()"></div>

<header class="header">
<div style="display:flex;align-items:center;justify-content:center;gap:16px;position:relative;flex:1">
    <h1 style="text-align:center;margin:0 auto;padding:0 20px;">ACCOUNTS</h1>
</div>
<div style="display:flex;align-items:center;gap:12px;">
    <button class="theme-toggle" onclick="toggleTheme()" title="Toggle Theme" id="themeBtn">🌙</button>
</div>
</header>

<div class="container">
    <div class="section-title">
        <span>SWEEPSTAKES SITES</span>
        <button class="btn-claim" style="width:auto;padding:10px 20px;margin-left:auto;" onclick="showAddSite()">+ ADD SITE</button>
    </div>
    <div class="accounts-grid" id="sites-grid"></div>
    
    <!-- Add Site Modal -->
    <div id="addSiteModal" style="display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.8);z-index:1000;align-items:center;justify-content:center;">
        <div style="background:linear-gradient(145deg, #1a1a1a, #141414);border:1px solid #2a2a2a;border-radius:16px;padding:30px;max-width:400px;width:90%;">
            <h2 style="font-family:'Righteous',cursive;color:#fff;margin-bottom:20px;">ADD NEW SITE</h2>
            <div class="form-group">
                <label>Site Name</label>
                <input type="text" id="new-site-name" placeholder="e.g., My Casino">
            </div>
            <div class="form-group">
                <label>Domain</label>
                <input type="text" id="new-site-domain" placeholder="e.g., mycasino.com">
            </div>
            <div class="form-group">
                <label>URL</label>
                <input type="text" id="new-site-url" placeholder="https://www.mycasino.com">
            </div>
            <div class="form-group">
                <label>SC per Day</label>
                <input type="number" id="new-site-sc" placeholder="1" step="0.1">
            </div>
            <div style="display:flex;gap:10px;margin-top:20px;">
                <button class="btn-claim" onclick="addNewSite()">ADD SITE</button>
                <button class="btn-claim" style="background:rgba(255,255,255,0.1);" onclick="hideAddSite()">CANCEL</button>
            </div>
        </div>
    </div>
</div>

<script>
let sites = ___SITES___;
let accounts = ___ACCOUNTS___;

function renderSites() {
    const grid = document.getElementById('sites-grid');
    grid.innerHTML = sites.map(site => {
        const account = accounts[site.domain] || {};
        const hasCreds = account.username && account.password;
        return `
        <div class="site-card">
            <div class="site-header">
                <div class="site-name">${site.name}</div>
                <div class="site-status ${hasCreds ? 'status-active' : 'status-inactive'}">
                    ${hasCreds ? 'READY' : 'SETUP'}
                </div>
            </div>
            <div class="site-info">
                <div>SC per day: ${site.sc_per_day}</div>
                <div>Spins: ${site.has_spins ? 'Yes' : 'No'}</div>
                ${account.sc_total ? `<div class="sc-total">${account.sc_total.toFixed(2)} SC</div>` : ''}
            </div>
            <button class="btn-claim" onclick="toggleForm('${site.domain}')">${hasCreds ? 'CLAIM NOW' : 'SETUP'}</button>
            <div class="account-form" id="form-${site.domain}">
                <div class="form-group">
                    <label>Username/Email</label>
                    <input type="text" id="user-${site.domain}" value="${account.username || ''}" placeholder="Enter username">
                </div>
                <div class="form-group">
                    <label>Password</label>
                    <input type="password" id="pass-${site.domain}" placeholder="Enter password">
                </div>
                <button class="btn-claim" onclick="saveAccount('${site.domain}', '${site.url}')">SAVE & CLAIM</button>
            </div>
        </div>
        `;
    }).join('');
}

function toggleForm(domain) {
    const form = document.getElementById('form-' + domain);
    form.classList.toggle('active');
}

function saveAccount(domain, url) {
    const username = document.getElementById('user-' + domain).value;
    const password = document.getElementById('pass-' + domain).value;
    
    if (!username || !password) {
        alert('Please enter username and password');
        return;
    }
    
    fetch('/api/save-account', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({domain, username, password})
    })
    .then(r => r.json())
    .then(data => {
        if (data.ok) {
            alert('Account saved! Starting claim process...');
            accounts[domain] = {username, password};
            renderSites();
            fetch('/api/claim', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({domain, url})
            });
        }
    });
}

function showAddSite() {
    document.getElementById('addSiteModal').style.display = 'flex';
}
function hideAddSite() {
    document.getElementById('addSiteModal').style.display = 'none';
}
function addNewSite() {
    const name = document.getElementById('new-site-name').value.trim();
    const domain = document.getElementById('new-site-domain').value.trim();
    const url = document.getElementById('new-site-url').value.trim();
    const sc = parseFloat(document.getElementById('new-site-sc').value) || 1;
    
    if (!name || !domain || !url) {
        alert('Please fill in all required fields');
        return;
    }
    
    fetch('/api/add-site', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name, domain, url, sc_per_day: sc, has_spins: true})
    })
    .then(r => r.json())
    .then(data => {
        if (data.ok) {
            alert('Site added!');
            location.reload();
        }
    });
}

renderSites();
function toggleSidebar() {
    const sidebar = document.getElementById('dashboard-sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    const trigger = document.getElementById('sidebarTrigger');
    sidebar.classList.toggle('open');
    overlay.classList.toggle('active');
    if (trigger) trigger.classList.toggle('open');
}
function closeSidebar() {
    const sidebar = document.getElementById('dashboard-sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    const trigger = document.getElementById('sidebarTrigger');
    sidebar.classList.remove('open');
    overlay.classList.remove('active');
    if (trigger) trigger.classList.remove('open');
}
function toggleTheme() {
    const html = document.documentElement;
    const btn = document.getElementById('themeBtn');
    if (html.getAttribute('data-theme') === 'light') {
        html.removeAttribute('data-theme');
        btn.textContent = '🌙';
        localStorage.setItem('theme', 'dark');
    } else {
        html.setAttribute('data-theme', 'light');
        btn.textContent = '☀️';
        localStorage.setItem('theme', 'light');
    }
}
(function() {
    const saved = localStorage.getItem('theme');
    if (saved === 'light') {
        document.documentElement.setAttribute('data-theme', 'light');
        const btn = document.getElementById('themeBtn');
        if (btn) btn.textContent = '☀️';
    }
})();
</script>
</body>
</html>"""

# ================== DAILY CLAIM PAGE ==================
DAILY_CLAIM_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daily SC Claim - Sweepstakes Monitor</title>
    """ + DASHBOARD_CSS + """
    <style>
        .claim-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .claim-card {
            background: linear-gradient(145deg, #1a1a1a, #141414);
            border: 1px solid #2a2a2a;
            border-radius: 16px;
            padding: 24px;
            transition: all 0.3s ease;
        }
        .claim-card:hover {
            border-color: #8B5CF6;
            transform: translateY(-2px);
        }
        .claim-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        .claim-site-name {
            font-family: 'Righteous', cursive;
            font-size: 1.2rem;
            color: #fff;
        }
        .claim-status {
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 600;
        }
        .status-ready {
            background: rgba(0, 255, 136, 0.15);
            color: #00ff88;
        }
        .status-no-account {
            background: rgba(255, 68, 68, 0.15);
            color: #ff4444;
        }
        .claim-info {
            color: #888;
            font-size: 0.9rem;
            margin-bottom: 15px;
        }
        .sc-amount {
            font-size: 2rem;
            font-weight: 700;
            color: #8B5CF6;
            margin: 15px 0;
        }
        .btn-claim-all {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #8B5CF6, #7C3AED);
            border: none;
            border-radius: 10px;
            color: #fff;
            font-weight: 600;
            font-size: 1.1rem;
            cursor: pointer;
            transition: all 0.3s ease;
            margin-top: 20px;
        }
        .btn-claim-all:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(139, 92, 246, 0.3);
        }
        .btn-claim-all:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        .last-claim {
            font-size: 0.8rem;
            color: #666;
            margin-top: 10px;
        }
        .total-section {
            background: linear-gradient(145deg, #1a1a1a, #141414);
            border: 1px solid #8B5CF6;
            border-radius: 16px;
            padding: 30px;
            text-align: center;
            margin-bottom: 30px;
        }
        .total-label {
            font-size: 0.9rem;
            color: #888;
            margin-bottom: 10px;
        }
        .total-amount {
            font-size: 3rem;
            font-weight: 700;
            color: #8B5CF6;
        }
    </style>
</head>
<body>
<div class="dashboard-sidebar" id="dashboard-sidebar">
    <div class="sidebar-header"><h2>MENU</h2></div>
<nav class="sidebar-nav">
        <a href="/" class="sidebar-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="3" width="7" height="7"></rect>
                <rect x="14" y="3" width="7" height="7"></rect>
                <rect x="14" y="14" width="7" height="7"></rect>
                <rect x="3" y="14" width="7" height="7"></rect>
            </svg>
            Main
        </a>
        <a href="/accounts" class="sidebar-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                <circle cx="12" cy="7" r="4"></circle>
            </svg>
            Accounts
        </a>
        <a href="/daily-claim" class="sidebar-link active">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0-3.5 3.5h-5A3.5 3.5 0 0 1 5 5h7"></path>
                <path d="M12 2a4 4 0 0 1 4 4v12a4 4 0 0 1-4 4 4 4 0 0 1-4-4V6a4 4 0 0 1 4-4z"></path>
            </svg>
            Daily Claim
        </a>
        <a href="/daily-claims" class="sidebar-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <polyline points="12 6 12 12 16 14"></polyline>
            </svg>
            Daily Claims
        </a>
        <a href="/profiles" class="sidebar-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                <circle cx="9" cy="7" r="4"></circle>
                <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
                <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
            </svg>
            Profiles
        </a>
        <a href="/proxies" class="sidebar-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
            </svg>
            Proxies
        </a>
        <a href="/membership" class="sidebar-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
                <path d="M2 17l10 5 10-5"></path>
                <path d="M2 12l10 5 10-5"></path>
            </svg>
            Membership
        </a>
    </nav>
    <div class="sidebar-footer">
        <a href="/logout" class="sidebar-link settings-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                <polyline points="16 17 21 12 16 7"></polyline>
                <line x1="21" y1="12" x2="9" y2="12"></line>
            </svg>
            Logout
        </a>
        <a href="/settings" class="sidebar-link settings-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="3"></circle>
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
            </svg>
            Settings
        </a>
    </div>
</div>
<div class="sidebar-trigger" id="sidebarTrigger" onclick="toggleSidebar()" title="Toggle Menu">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
</div>
<div class="sidebar-overlay" id="sidebar-overlay" onclick="closeSidebar()"></div>

<header class="header">
<div style="display:flex;align-items:center;justify-content:center;gap:16px;position:relative;flex:1">
    <h1 style="text-align:center;margin:0 auto;padding:0 20px;">DAILY SC CLAIM</h1>
</div>
<div style="display:flex;align-items:center;gap:12px;">
    <button class="theme-toggle" onclick="toggleTheme()" title="Toggle Theme" id="themeBtn">🌙</button>
</div>
</header>

<div class="container">
    <div class="total-section">
        <div class="total-label">TODAY'S TOTAL SC CLAIMED</div>
        <div class="total-amount" id="total-sc">0.00 SC</div>
    </div>
    
    <div class="section-title"><span>CLAIM FROM SITES</span></div>
    <div class="claim-grid" id="claim-grid"></div>
    
    <button class="btn-claim-all" id="claim-all-btn" onclick="claimAll()">CLAIM ALL SITES</button>
</div>

<script>
let sites = ___SITES___;
let accounts = ___ACCOUNTS___;
let totalSC = 0;

function renderClaimGrid() {
    const grid = document.getElementById('claim-grid');
    totalSC = 0;
    
    grid.innerHTML = sites.map(site => {
        const account = accounts[site.domain] || {};
        const hasCreds = account.username && account.password;
        const scAmount = site.sc_per_day || 1;
        const lastClaim = account.last_claim || 'Never';
        
        if (hasCreds) totalSC += scAmount;
        
        return `
        <div class="claim-card">
            <div class="claim-header">
                <div class="claim-site-name">${site.name}</div>
                <div class="claim-status ${hasCreds ? 'status-ready' : 'status-no-account'}">
                    ${hasCreds ? 'READY' : 'NO ACCOUNT'}
                </div>
            </div>
            <div class="claim-info">
                <div>SC per claim: ${scAmount}</div>
                <div class="last-claim">Last claim: ${lastClaim}</div>
            </div>
            <div class="sc-amount">${scAmount} SC</div>
            <button class="btn-claim" 
                    onclick="claimSite('${site.domain}', '${site.url}', ${scAmount})">
                    ${hasCreds ? 'CLAIM NOW' : 'SETUP REQUIRED'}
            </button>
        </div>
        `;
    }).join('');
    
    document.getElementById('total-sc').textContent = totalSC.toFixed(2) + ' SC';
}

function claimSite(domain, url, scAmount) {
    fetch('/api/claim', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({domain, url})
    })
    .then(r => r.json())
    .then(data => {
        if (data.ok) {
            alert('Claim started for ' + domain + '!');
            accounts[domain] = accounts[domain] || {};
            accounts[domain].last_claim = new Date().toLocaleString();
            renderClaimGrid();
        }
    });
}

function claimAll() {
    const btn = document.getElementById('claim-all-btn');
    btn.disabled = true;
    btn.textContent = 'CLAIMING...';
    
    sites.forEach(site => {
        const account = accounts[site.domain];
        if (account && account.username) {
            claimSite(site.domain, site.url, site.sc_per_day);
        }
    });
    
    setTimeout(() => {
        btn.disabled = false;
        btn.textContent = 'CLAIM ALL SITES';
    }, 5000);
}

renderClaimGrid();
function toggleSidebar() {
    const sidebar = document.getElementById('dashboard-sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    const trigger = document.getElementById('sidebarTrigger');
    sidebar.classList.toggle('open');
    overlay.classList.toggle('active');
    if (trigger) trigger.classList.toggle('open');
}
function closeSidebar() {
    const sidebar = document.getElementById('dashboard-sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    const trigger = document.getElementById('sidebarTrigger');
    sidebar.classList.remove('open');
    overlay.classList.remove('active');
    if (trigger) trigger.classList.remove('open');
}
function toggleTheme() {
    const html = document.documentElement;
    const btn = document.getElementById('themeBtn');
    if (html.getAttribute('data-theme') === 'light') {
        html.removeAttribute('data-theme');
        btn.textContent = '🌙';
        localStorage.setItem('theme', 'dark');
    } else {
        html.setAttribute('data-theme', 'light');
        btn.textContent = '☀️';
        localStorage.setItem('theme', 'light');
    }
}
(function() {
    const saved = localStorage.getItem('theme');
    if (saved === 'light') {
        document.documentElement.setAttribute('data-theme', 'light');
        const btn = document.getElementById('themeBtn');
        if (btn) btn.textContent = '☀️';
    }
})();
</script>
</body>
</html>"""

# ================== ADMIN LOGIN ==================
ADMIN_LOGIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Access</title>
    """ + DASHBOARD_CSS + """
    <style>
        .login-container {
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .login-box {
            background: linear-gradient(145deg, #1a1a1a, #141414);
            border: 1px solid #2a2a2a;
            border-radius: 20px;
            padding: 50px;
            max-width: 450px;
            width: 100%;
            text-align: center;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
        }
        .login-box h1 {
            font-family: 'Righteous', cursive;
            color: #ffffff;
            margin-bottom: 10px;
            letter-spacing: 2px;
        }
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 28px;
        }
        .tab {
            flex: 1;
            padding: 12px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            color: #888;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        .tab.active {
            background: rgba(139, 92, 246, 0.2);
            color: #8B5CF6;
            border-color: #8B5CF6;
        }
        .form-group {
            margin-bottom: 20px;
            text-align: left;
        }
        .form-group label {
            display: block;
            color: #888;
            margin-bottom: 8px;
            font-size: 0.9rem;
        }
        .form-group input {
            width: 100%;
            padding: 12px 15px;
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            color: #fff;
            font-size: 1rem;
        }
        .form-group input:focus {
            outline: none;
            border-color: #8B5CF6;
        }
        .submit-btn {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #8B5CF6, #7C3AED);
            border: none;
            border-radius: 10px;
            color: #fff;
            font-weight: 700;
            font-size: 1.1rem;
            cursor: pointer;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .submit-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(139, 92, 246, 0.3);
        }
        .error {
            color: #ff4444;
            margin-top: 15px;
            display: none;
            font-size: 0.9rem;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="login-box">
            <h1>ADMIN ACCESS</h1>
            <div class="tabs">
                <div class="tab active" onclick="showTab('discord')">Discord ID</div>
                <div class="tab" onclick="showTab('email')">Email</div>
            </div>
            
            <div id="discord-tab">
                <div class="form-group">
                    <label>Discord ID</label>
                    <input type="text" id="admin_discord_id" placeholder="123456789012345678">
                </div>
                <button class="submit-btn" onclick="loginDiscord()">ACCESS</button>
            </div>
            
            <div id="email-tab" style="display:none">
                <div class="form-group">
                    <label>Email</label>
                    <input type="email" id="admin_email" placeholder="admin@example.com">
                </div>
                <div class="form-group">
                    <label>Password</label>
                    <input type="password" id="admin_password" placeholder="••••••••">
                </div>
                <button class="submit-btn" onclick="loginEmail()">LOGIN</button>
            </div>
            
            <div class="error" id="err">Invalid credentials.</div>
        </div>
    </div>

<script>
let currentTab = 'discord';
function showTab(tab) {
    currentTab = tab;
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    event.target.classList.add('active');
    document.getElementById('discord-tab').style.display = tab === 'discord' ? 'block' : 'none';
    document.getElementById('email-tab').style.display = tab === 'email' ? 'block' : 'none';
}
function loginDiscord() {
    const id = document.getElementById('admin_discord_id').value.trim();
    fetch('/admin-login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({method: 'discord', id: id})
    }).then(r => r.json()).then(d => {
        if (d.ok) window.location.href = '/admin';
        else document.getElementById('err').style.display = 'block';
    });
}
function loginEmail() {
    const email = document.getElementById('admin_email').value;
    const password = document.getElementById('admin_password').value;
    fetch('/admin-login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({method: 'email', email: email, password: password})
    }).then(r => r.json()).then(d => {
        if (d.ok) window.location.href = '/admin';
        else document.getElementById('err').style.display = 'block';
    });
}
</script>
</body>
</html>"""

# ================== ADMIN PANEL ==================
ADMIN_PANEL_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Claims Casino Admin Panel</title>
    """ + DASHBOARD_CSS + """
    <style>
        .admin-layout { display: flex; min-height: 100vh; }
        .admin-sidebar {
            width: 250px;
            background: var(--surface);
            border-right: 1px solid var(--border);
            padding: 24px;
            display: flex;
            flex-direction: column;
        }
        .admin-sidebar h2 {
            font-family: 'Righteous', cursive;
            color: var(--text-bright);
            letter-spacing: 2px;
            margin-bottom: 30px;
            font-size: 1.1rem;
        }
        .nav-item {
            padding: 14px 16px;
            color: var(--text);
            cursor: pointer;
            border-radius: 10px;
            margin-bottom: 4px;
            font-weight: 500;
            transition: all 0.2s;
        }
        .nav-item:hover, .nav-item.active {
            background: var(--surface-hover);
            color: var(--text-bright);
            border-left: 3px solid var(--accent);
        }
        .admin-main { flex: 1; padding: 30px; overflow-y: auto; }
        .panel-title {
            font-family: 'Righteous', cursive;
            font-size: 1.4rem;
            color: var(--text-bright);
            margin-bottom: 24px;
            letter-spacing: 1px;
        }
        .stats-row { display: flex; gap: 16px; margin-bottom: 30px; flex-wrap: wrap; }
        .stat-box {
            flex: 1;
            min-width: 150px;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
        }
        .stat-value { font-size: 2rem; font-weight: 700; color: var(--accent); }
        .stat-label { color: var(--text-muted); font-size: 0.85rem; margin-top: 4px; }
        .user-list { margin-top: 16px; }
        .user-item {
            padding: 14px 18px;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .btn-remove {
            padding: 8px 16px;
            background: rgba(255,68,68,0.15);
            border: 1px solid #ff4444;
            border-radius: 8px;
            color: #ff4444;
            cursor: pointer;
            font-weight: 600;
            font-size: 0.8rem;
        }
        .btn-remove:hover { background: rgba(255,68,68,0.25); }
        .btn-generate {
            padding: 10px 20px;
            background: var(--accent);
            border: none;
            border-radius: 8px;
            color: #fff;
            cursor: pointer;
            font-weight: 600;
        }
        .btn-generate:hover { opacity: 0.9; }
        .key-item {
            padding: 12px 16px;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .key-item .key-code { font-family: monospace; font-size: 0.95rem; color: var(--accent); letter-spacing: 1px; }
        .key-item .key-meta { font-size: 0.8rem; color: var(--text-muted); }
        .key-item .badge-tier { padding: 2px 10px; border-radius: 10px; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; }
        .badge-premium { background: rgba(139,92,246,0.2); color: var(--accent); }
        .badge-basic { background: rgba(255,255,255,0.1); color: var(--text-muted); }
        .key-item .badge-revoked { color: #f87171; font-size: 0.75rem; }
        .section-hidden { display: none; }
        .license-actions { display: flex; gap: 10px; margin-bottom: 20px; align-items: center; flex-wrap: wrap; }
        .license-actions select {
            padding: 10px 14px;
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text);
            font-family: inherit;
        }
        .copied-msg { color: #4ade80; font-size: 0.85rem; display: none; }
        .admin-login-indicator {
            margin-top: auto;
            padding: 16px;
            border-top: 1px solid var(--border);
            display: flex;
            align-items: center;
            gap: 10px;
            color: var(--text-muted);
            font-size: 0.85rem;
        }
        .admin-login-indicator .arrow { color: var(--accent); font-size: 1.1rem; }
        .user-mgmt-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }
        .mgmt-box {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 20px;
        }
        .mgmt-box h3 {
            font-family: 'Righteous', cursive;
            font-size: 0.95rem;
            color: var(--text-bright);
            margin-bottom: 12px;
            letter-spacing: 0.5px;
        }
        .mgmt-box input, .mgmt-box textarea {
            width: 100%;
            padding: 10px 12px;
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text);
            font-family: inherit;
            font-size: 0.85rem;
            margin-bottom: 10px;
            box-sizing: border-box;
        }
        .mgmt-box textarea { min-height: 60px; resize: vertical; }
        .mgmt-box .btn-action {
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            font-size: 0.85rem;
            transition: all 0.2s;
        }
        .btn-approve { background: rgba(0,255,136,0.15); color: #00ff88; border: 1px solid #00ff88; }
        .btn-approve:hover { background: rgba(0,255,136,0.25); }
        .btn-decline { background: rgba(255,68,68,0.15); color: #ff4444; border: 1px solid #ff4444; }
        .btn-decline:hover { background: rgba(255,68,68,0.25); }
        .btn-invite { background: rgba(255,215,0,0.15); color: #ffd700; border: 1px solid #ffd700; }
        .btn-invite:hover { background: rgba(255,215,0,0.25); }
        .mgmt-result { font-size: 0.8rem; margin-top: 8px; color: var(--text-muted); }
    </style>
</head>
<body>
<div class="admin-layout">
    <div class="admin-sidebar">
        <h2>CLAIMS ADMIN</h2>
        <div class="nav-item active" onclick="showSection('dashboard')">Dashboard</div>
        <div class="nav-item" onclick="showSection('users')">User Management</div>
        <div class="nav-item" onclick="showSection('licenses')">Licenses</div>
        <div class="admin-login-indicator">
            <span class="arrow">▶</span>
            <span>Admin Login</span>
        </div>
    </div>
    <div class="admin-main">
        <!-- Dashboard Section -->
        <div id="section-dashboard">
            <div class="panel-title">Claims Casino Admin Panel</div>
            <div class="stats-row">
                <div class="stat-box">
                    <div class="stat-value" id="user-count">0</div>
                    <div class="stat-label">Approved Users</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value" id="alert-count">0</div>
                    <div class="stat-label">Active Alerts</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value" id="sc-claimed">0</div>
                    <div class="stat-label">Total SC Claimed</div>
                </div>
            </div>
        </div>
        <!-- User Management Section -->
        <div id="section-users" class="section-hidden">
            <div class="panel-title">User Management</div>
            <div class="user-mgmt-grid">
                <div class="mgmt-box">
                    <h3>✓ Approve User</h3>
                    <input type="text" id="approveId" placeholder="Discord ID">
                    <button class="btn-action btn-approve" onclick="approveUser()">APPROVE</button>
                    <div class="mgmt-result" id="approveResult"></div>
                </div>
                <div class="mgmt-box">
                    <h3>✗ Decline User</h3>
                    <input type="text" id="declineId" placeholder="Discord ID">
                    <button class="btn-action btn-decline" onclick="declineUser()">DECLINE</button>
                    <div class="mgmt-result" id="declineResult"></div>
                </div>
                <div class="mgmt-box">
                    <h3>✉ Send Interview Invite</h3>
                    <input type="text" id="inviteId" placeholder="Discord ID">
                    <textarea id="inviteMsg" placeholder="Invite message...">You have been invited for an interview to join Claim City.</textarea>
                    <button class="btn-action btn-invite" onclick="sendInvite()">SEND INVITE</button>
                    <div class="mgmt-result" id="inviteResult"></div>
                </div>
            </div>
            <div class="panel-title" style="font-size:1rem;margin-top:24px;">Approved Users</div>
            <div class="user-list" id="user-list"></div>
        </div>
        <!-- Licenses Section -->
        <div id="section-licenses" class="section-hidden">
            <div class="panel-title">License Keys</div>
            <div class="license-actions">
                <select id="tier-select">
                    <option value="basic">Basic</option>
                    <option value="premium">Premium</option>
                </select>
                <button class="btn-generate" onclick="generateLicense()">GENERATE KEY</button>
            </div>
            <div class="copied-msg" id="copied-msg">Key copied to clipboard!</div>
            <div class="user-list" id="license-list"></div>
        </div>
    </div>
</div>

<script>
function showSection(section) {
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    event.target.classList.add('active');
    document.querySelectorAll('[id^="section-"]').forEach(s => s.classList.add('section-hidden'));
    document.getElementById('section-' + section).classList.remove('section-hidden');
    if (section === 'licenses') { loadLicenses(); }
    if (section === 'users') { loadUsers(); }
}
function approveUser() {
    const id = document.getElementById('approveId').value.trim();
    if (!id) return;
    document.getElementById('approveResult').textContent = 'Processing...';
    fetch('/add-user', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({discord_id: id})
    }).then(r => r.json()).then(d => {
        document.getElementById('approveResult').textContent = d.ok ? '✓ User approved!' : '✗ Error: ' + (d.error || 'Unknown');
        if (d.ok) { document.getElementById('approveId').value = ''; refreshStats(); loadUsers(); }
    });
}
function declineUser() {
    const id = document.getElementById('declineId').value.trim();
    if (!id) return;
    document.getElementById('declineResult').textContent = 'Processing...';
    fetch('/remove-user', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({discord_id: id})
    }).then(r => r.json()).then(d => {
        document.getElementById('declineResult').textContent = d.ok ? '✗ User declined/removed!' : '✗ Error';
        if (d.ok) { document.getElementById('declineId').value = ''; refreshStats(); loadUsers(); }
    });
}
function sendInvite() {
    const id = document.getElementById('inviteId').value.trim();
    const msg = document.getElementById('inviteMsg').value.trim();
    if (!id) return;
    document.getElementById('inviteResult').textContent = 'Sending...';
    fetch('/api/admin-invite', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({discord_id: id, message: msg})
    }).then(r => r.json()).then(d => {
        document.getElementById('inviteResult').textContent = d.ok ? '✉ Invite sent!' : '✗ Error';
        if (d.ok) { document.getElementById('inviteId').value = ''; }
    });
}
function refreshStats() {
    fetch('/api/admin-stats').then(r => r.json()).then(d => {
        document.getElementById('user-count').textContent = d.users;
        document.getElementById('alert-count').textContent = d.alerts;
    });
    fetch('/api/data').then(r => r.json()).then(d => {
        document.getElementById('sc-claimed').textContent = (d.sc_total || 0).toFixed(1);
    });
}
function loadUsers() {
    const list = document.getElementById('user-list');
    list.innerHTML = 'Loading...';
    fetch('/api/data').then(r => r.json()).then(d => {
        if (d.approved_users && d.approved_users.length > 0) {
            list.innerHTML = d.approved_users.map(u => `
                <div class="user-item">
                    <span style="font-weight:600">${u}</span>
                    <button class="btn-remove" onclick="removeUser('${u}')">Remove</button>
                </div>
            `).join('');
        } else {
            list.innerHTML = '<div class="empty-state">No approved users yet.</div>';
        }
    });
}
function removeUser(id) {
    if (!confirm('Remove user ' + id + '?')) return;
    fetch('/remove-user', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({discord_id: id})
    }).then(() => { refreshStats(); loadUsers(); });
}
function loadLicenses() {
    const list = document.getElementById('license-list');
    list.innerHTML = 'Loading...';
    fetch('/api/admin-licenses').then(r => r.json()).then(keys => {
        const entries = Object.entries(keys);
        if (entries.length === 0) { list.innerHTML = '<div class="empty-state">No license keys found.</div>'; return; }
        list.innerHTML = entries.map(([key, data]) => {
            const status = data.status || 'active';
            const tier = data.tier || 'basic';
            const created = data.created ? new Date(data.created * 1000).toLocaleDateString() : 'N/A';
            const isActive = status === 'active';
            return '<div class="key-item"><div><div class="key-code">' + key + '</div><div class="key-meta">Created: ' + created + ' | ' + (isActive ? '<span class="badge-tier badge-' + tier + '">' + tier.toUpperCase() + '</span>' : '<span class="badge-revoked">REVOKED</span>') + '</div></div><div>' + (isActive ? '<button class="btn-remove" onclick="revokeLicense(\'' + key + '\')">Revoke</button>' : '') + '</div></div>';
        }).join('');
    });
}
function generateLicense() {
    const tier = document.getElementById('tier-select').value;
    fetch('/api/admin-generate-license', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({tier: tier})
    }).then(r => r.json()).then(data => {
        if (data.ok) {
            loadLicenses();
            navigator.clipboard.writeText(data.key).then(function() {
                var msg = document.getElementById('copied-msg');
                msg.style.display = 'block';
                setTimeout(function() { msg.style.display = 'none'; }, 3000);
            });
        }
    });
}
function revokeLicense(key) {
    if (!confirm('Revoke license key ' + key + '?')) return;
    fetch('/api/admin-revoke-license', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({key: key})
    }).then(r => r.json()).then(data => { if (data.ok) { loadLicenses(); } });
}
refreshStats();
setInterval(refreshStats, 5000);
</script>
</body>
</html>"""

# ================== DAILY CLAIMS PAGE ==================
DAILY_CLAIMS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daily Claims - Sweepstakes Monitor</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Righteous&family=Outfit:wght@400;600;700;800&display=swap" rel="stylesheet">
    """ + DASHBOARD_CSS + """
    <style>
        .claim-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 16px;
            margin-top: 20px;
        }
        .claim-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 20px;
            transition: all 0.3s ease;
        }
        .claim-card:hover {
            border-color: var(--accent);
            transform: translateY(-2px);
        }
        .claim-card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }
        .claim-card-name {
            font-family: 'Righteous', cursive;
            font-size: 1.1rem;
            color: var(--text-bright);
            letter-spacing: 0.5px;
        }
        .claim-card-user {
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-bottom: 10px;
        }
        .claim-timer {
            font-size: 1.8rem;
            font-weight: 700;
            text-align: center;
            padding: 16px;
            border-radius: 12px;
            background: var(--bg);
            border: 1px solid var(--border);
            margin: 10px 0;
            font-family: 'Outfit', monospace;
            letter-spacing: 2px;
        }
        .claim-timer.ready {
            color: #00ff88;
            border-color: #00ff88;
        }
        .claim-timer.waiting {
            color: var(--text-muted);
        }
        .claim-status {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }
        .status-idle { background: rgba(255,255,255,0.1); color: var(--text-muted); }
        .status-claiming { background: rgba(255,215,0,0.15); color: #ffd700; }
        .status-done { background: rgba(0,255,136,0.15); color: #00ff88; }
        .status-error { background: rgba(255,68,68,0.15); color: #ff4444; }
        .btn-claim {
            width: 100%;
            padding: 12px;
            border: none;
            border-radius: 10px;
            background: var(--accent);
            color: #fff;
            font-weight: 700;
            font-size: 0.95rem;
            cursor: pointer;
            transition: all 0.3s ease;
            margin-top: 10px;
        }
        .btn-claim:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(139,92,246,0.3);
        }
        .btn-claim:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        .add-casino-btn {
            position: fixed;
            bottom: 90px;
            right: 24px;
            width: 56px;
            height: 56px;
            border-radius: 50%;
            border: 2px dashed var(--border);
            background: var(--surface);
            color: var(--text-dim);
            font-size: 1.5rem;
            cursor: pointer;
            box-shadow: var(--shadow);
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .add-casino-btn:hover {
            border-style: solid;
            border-color: var(--accent);
            color: var(--accent);
            transform: scale(1.1);
        }
    </style>
</head>
<body>
<div class="dashboard-sidebar" id="dashboard-sidebar">
    <div class="sidebar-header"><h2>MENU</h2></div>
<nav class="sidebar-nav">
        <a href="/" class="sidebar-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
            Main
        </a>
        <a href="/accounts" class="sidebar-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
            Accounts
        </a>
        <a href="/daily-claim" class="sidebar-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0-3.5 3.5h-5A3.5 3.5 0 0 1 5 5h7"></path><path d="M12 2a4 4 0 0 1 4 4v12a4 4 0 0 1-4 4 4 4 0 0 1-4-4V6a4 4 0 0 1 4-4z"></path></svg>
            Daily Claim
        </a>
        <a href="/daily-claims" class="sidebar-link active">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
            Daily Claims
        </a>
        <a href="/profiles" class="sidebar-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
            Profiles
        </a>
        <a href="/proxies" class="sidebar-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
            Proxies
        </a>
        <a href="/membership" class="sidebar-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"></path><path d="M2 17l10 5 10-5"></path><path d="M2 12l10 5 10-5"></path></svg>
            Membership
        </a>
    </nav>
    <div class="sidebar-footer">
        <a href="/logout" class="sidebar-link settings-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
            Logout
        </a>
        <a href="/settings" class="sidebar-link settings-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
            Settings
        </a>
    </div>
</div>
<div class="sidebar-trigger" id="sidebarTrigger" onclick="toggleSidebar()" title="Toggle Menu">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
</div>
<div class="sidebar-overlay" id="sidebar-overlay" onclick="closeSidebar()"></div>

<header class="header">
<div style="display:flex;align-items:center;justify-content:center;gap:16px;position:relative;flex:1">
    <h1 style="text-align:center;margin:0 auto;padding:0 20px;">DAILY <span>CLAIMS</span></h1>
</div>
<div style="display:flex;align-items:center;gap:12px;">
    <button class="theme-toggle" onclick="toggleTheme()" title="Toggle Theme" id="themeBtn">🌙</button>
    <div class="status-badge">
        <span class="status-dot" id="status-dot"></span>
        <span id="status">IDLE</span>
    </div>
</div>
</header>

<div class="container">
    <div class="section-title">
        <span>AUTO-CLAIM SCHEDULER</span>
        <span style="font-size:0.7rem;opacity:0.6;margin-left:auto">24-hour cooldown per casino</span>
    </div>
    <div class="claim-grid" id="claimGrid"></div>
</div>

<button class="add-casino-btn" onclick="showAddModal()" title="Add Casino">+</button>

<div class="modal-overlay" id="addModal">
    <div class="modal-box">
        <h2>ADD CASINO</h2>
        <input type="text" class="modal-search" id="casinoSearch" placeholder="Search casinos..." oninput="filterCasinos()">
        <div id="casinoList" style="max-height:300px;overflow-y:auto;margin:10px 0"></div>
        <div class="form-group" style="margin-top:10px">
            <label>Username / Email</label>
            <input type="text" id="claimUsername" placeholder="Enter username or email">
        </div>
        <div class="form-group">
            <label>Password</label>
            <input type="password" id="claimPassword" placeholder="Enter password">
        </div>
        <div style="display:flex;gap:10px;margin-top:15px">
            <button class="btn" style="flex:1" onclick="closeAddModal()">Cancel</button>
            <button class="btn btn-primary" style="flex:2;background:var(--accent);color:#fff" onclick="saveClaimCasino()">Save & Add</button>
        </div>
    </div>
</div>

<script>
let selectedCasino = null;
const sites = ___SITES___;
const accounts = ___ACCOUNTS___;
let claimSchedule = ___SCHEDULE___;

function showAddModal() {
    document.getElementById('addModal').classList.add('active');
    renderCasinoList();
}
function closeAddModal() {
    document.getElementById('addModal').classList.remove('active');
    selectedCasino = null;
}
function filterCasinos() {
    renderCasinoList();
}
function renderCasinoList() {
    const q = (document.getElementById('casinoSearch').value || '').toLowerCase();
    const list = document.getElementById('casinoList');
    list.innerHTML = sites.filter(s => s.name.toLowerCase().includes(q)).map(s => `
        <div class="casino-item" data-domain="${s.domain}" onclick="selectClaimCasino('${s.domain}','${s.name}')" style="padding:10px 14px;border:1px solid var(--border);border-radius:8px;margin-bottom:6px;cursor:pointer;transition:all 0.2s;${selectedCasino === s.domain ? 'background:var(--accent);color:#fff;' : ''}">
            ${s.name}
        </div>
    `).join('');
}
function selectClaimCasino(domain, name) {
    selectedCasino = domain;
    renderCasinoList();
}
function saveClaimCasino() {
    const domain = selectedCasino;
    const username = document.getElementById('claimUsername').value.trim();
    const password = document.getElementById('claimPassword').value.trim();
    if (!domain || !username || !password) { alert('Fill all fields'); return; }
    fetch('/api/save-account', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({domain, username, password})
    }).then(r => r.json()).then(d => {
        if (d.ok) {
            // Add to claim schedule
            claimSchedule[domain] = {last_claim: 0, status: 'idle'};
            closeAddModal();
            renderClaims();
        }
    });
}
function renderClaims() {
    const grid = document.getElementById('claimGrid');
    const domains = Object.keys(accounts);
    if (domains.length === 0) {
        grid.innerHTML = '<div class="empty-state">No casino credentials saved yet. Click + to add one.</div>';
        return;
    }
    grid.innerHTML = domains.map(d => {
        const site = sites.find(s => s.domain === d) || {name: d};
        const sc = accounts[d];
        const sched = claimSchedule[d] || {last_claim: 0, status: 'idle'};
        const now = Math.floor(Date.now() / 1000);
        const elapsed = now - sched.last_claim;
        const remaining = Math.max(0, 86400 - elapsed);
        const ready = remaining <= 0;
        const hours = Math.floor(remaining / 3600);
        const mins = Math.floor((remaining % 3600) / 60);
        const secs = remaining % 60;
        const timerStr = ready ? 'READY TO CLAIM' : `${String(hours).padStart(2,'0')}:${String(mins).padStart(2,'0')}:${String(secs).padStart(2,'0')}`;
        const timerClass = ready ? 'claim-timer ready' : 'claim-timer waiting';
        const statusClass = 'status-' + sched.status;
        return `
            <div class="claim-card" data-domain="${d}">
                <div class="claim-card-header">
                    <span class="claim-card-name">${site.name}</span>
                    <span class="claim-status ${statusClass}">${sched.status.toUpperCase()}</span>
                </div>
                <div class="claim-card-user">${sc.username}</div>
                <div class="${timerClass}" data-last="${sched.last_claim}">${timerStr}</div>
                <button class="btn-claim" onclick="claimNow('${d}')" ${!ready || sched.status === 'claiming' ? 'disabled' : ''}>
                    ${sched.status === 'claiming' ? 'CLAIMING...' : ready ? 'CLAIM NOW' : 'WAITING'}
                </button>
            </div>
        `;
    }).join('');
}
function claimNow(domain) {
    fetch('/api/claim-now/' + domain, {method: 'POST'})
    .then(r => r.json())
    .then(d => { if (d.ok) setTimeout(renderClaims, 1000); });
}
function toggleSidebar() {
    document.getElementById('dashboard-sidebar').classList.toggle('open');
    document.getElementById('sidebar-overlay').classList.toggle('active');
    var trigger = document.getElementById('sidebarTrigger');
    if (trigger) trigger.classList.toggle('open');
}
function closeSidebar() {
    document.getElementById('dashboard-sidebar').classList.remove('open');
    document.getElementById('sidebar-overlay').classList.remove('active');
    var trigger = document.getElementById('sidebarTrigger');
    if (trigger) trigger.classList.remove('open');
}
function toggleTheme() {
    const html = document.documentElement;
    const btn = document.getElementById('themeBtn');
    if (html.getAttribute('data-theme') === 'light') {
        html.removeAttribute('data-theme');
        btn.textContent = '🌙';
        localStorage.setItem('theme', 'dark');
    } else {
        html.setAttribute('data-theme', 'light');
        btn.textContent = '☀️';
        localStorage.setItem('theme', 'light');
    }
}
(function() {
    const saved = localStorage.getItem('theme');
    if (saved === 'light') {
        document.documentElement.setAttribute('data-theme', 'light');
        const btn = document.getElementById('themeBtn');
        if (btn) btn.textContent = '☀️';
    }
})();
renderClaims();
setInterval(renderClaims, 1000);
</script>
</body>
</html>"""

# ================== PROFILES PAGE ==================
PROFILES_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Profiles - Sweepstakes Monitor</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Righteous&family=Outfit:wght@400;600;700;800&display=swap" rel="stylesheet">
    """ + DASHBOARD_CSS + """
    <style>
        .add-casino-btn {
            position: fixed;
            bottom: 90px;
            right: 24px;
            width: 56px;
            height: 56px;
            border-radius: 50%;
            border: 2px dashed var(--border);
            background: var(--surface);
            color: var(--text-dim);
            font-size: 1.5rem;
            cursor: pointer;
            box-shadow: var(--shadow);
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .add-casino-btn:hover {
            border-style: solid;
            border-color: var(--accent);
            color: var(--accent);
            transform: scale(1.1);
        }
        .modal-overlay {
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100vh;
            background: rgba(0,0,0,0.6);
            backdrop-filter: blur(6px);
            z-index: 200;
            display: none;
            justify-content: center;
            align-items: center;
        }
        .modal-overlay.active { display: flex; }
        .modal-box {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 16px;
            width: 90%;
            max-width: 500px;
            max-height: 80vh;
            overflow-y: auto;
            padding: 28px;
            position: relative;
        }
        .modal-box h2 {
            font-family: 'Righteous', cursive;
            color: var(--text-bright);
            margin-bottom: 16px;
            font-size: 1.2rem;
            letter-spacing: 1px;
        }
        .modal-search {
            width: 100%;
            padding: 10px 14px;
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text);
            font-family: 'Outfit', sans-serif;
            font-size: 0.9rem;
            margin-bottom: 12px;
        }
        .modal-search:focus { outline: none; border-color: var(--accent); }
        .casino-list-item {
            padding: 10px 14px;
            border: 1px solid var(--border);
            border-radius: 8px;
            margin-bottom: 6px;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .casino-list-item:hover {
            background: var(--surface-hover);
            border-color: var(--accent);
        }
        .casino-list-item .name {
            color: var(--text);
            font-weight: 600;
            font-size: 0.9rem;
        }
        .casino-list-item .tier-badge {
            font-size: 0.65rem;
            font-weight: 700;
            padding: 2px 6px;
            border-radius: 4px;
            margin-left: 8px;
        }
        .casino-list-item .tier-s { background: #ffd700; color: #000; }
        .casino-list-item .tier-a { background: #90ee90; color: #000; }
        .casino-list-item .tier-b { background: #9fc5e8; color: #000; }
        .casino-list-item .add-icon {
            width: 26px; height: 26px;
            border-radius: 50%;
            border: 2px solid var(--border);
            display: flex; align-items: center; justify-content: center;
            font-size: 0.9rem; color: var(--text-dim);
            transition: all 0.2s ease;
            flex-shrink: 0;
        }
        .casino-list-item:hover .add-icon {
            border-color: var(--accent);
            color: var(--accent);
        }
        .modal-close {
            position: absolute;
            top: 16px;
            right: 16px;
            background: none;
            border: none;
            color: var(--text-dim);
            font-size: 1.3rem;
            cursor: pointer;
        }
        .modal-close:hover { color: var(--text); }
        .profiles-container {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }
        .profile-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 24px;
            transition: all 0.3s ease;
        }
        .profile-card:hover {
            border-color: var(--accent);
            box-shadow: 0 8px 24px rgba(0,0,0,0.12);
        }
        .profile-card h3 {
            font-family: 'Righteous', cursive;
            color: var(--text-bright);
            margin-bottom: 16px;
            font-size: 1rem;
            letter-spacing: 1px;
        }
        .profile-field {
            display: flex;
            flex-direction: column;
            gap: 4px;
            margin-bottom: 10px;
        }
        .profile-field label {
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--text-dim);
        }
        .profile-field input {
            padding: 8px 12px;
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 6px;
            color: var(--text);
            font-family: 'Outfit', sans-serif;
            font-size: 0.9rem;
        }
        .profile-field input:focus { outline: none; border-color: var(--accent); }
        .profile-actions {
            display: flex;
            gap: 8px;
            margin-top: 14px;
        }
        .profile-actions button {
            flex: 1;
            padding: 8px;
            border: 1px solid var(--border);
            border-radius: 6px;
            font-family: 'Outfit', sans-serif;
            font-weight: 600;
            font-size: 0.8rem;
            cursor: pointer;
            transition: all 0.2s ease;
            background: var(--surface);
            color: var(--text);
        }
        .profile-actions button:hover {
            background: var(--accent);
            color: var(--bg);
            border-color: var(--accent);
        }
        .profile-actions .delete-btn:hover {
            background: #ff4444;
            color: #fff;
            border-color: #ff4444;
        }
        .login-setup {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 24px;
            margin: 0 0 20px 0;
        }
        .login-setup h4 {
            font-family: 'Righteous', cursive;
            color: var(--text-bright);
            margin-bottom: 12px;
            font-size: 0.9rem;
            letter-spacing: 1px;
        }
        .login-fields {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .login-field-row {
            display: flex;
            gap: 10px;
            align-items: flex-end;
        }
        .login-field-row .profile-field { flex: 1; margin: 0; }
        .google-btn {
            width: 40px;
            height: 40px;
            border: 1px solid var(--border);
            border-radius: 6px;
            background: var(--surface);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s ease;
            font-size: 1.1rem;
            flex-shrink: 0;
        }
        .google-btn:hover {
            border-color: var(--accent);
            background: var(--surface-hover);
        }
        .empty-message {
            text-align: center;
            padding: 60px 20px;
            color: var(--text-muted);
            font-size: 0.9rem;
        }
        .selected-count {
            font-size: 0.8rem;
            color: var(--text-dim);
            margin-bottom: 10px;
        }
        .add-selected-btn {
            width: 100%;
            padding: 10px;
            border: 1px solid var(--accent);
            border-radius: 8px;
            background: var(--accent);
            color: var(--bg);
            font-family: 'Outfit', sans-serif;
            font-weight: 700;
            font-size: 0.85rem;
            cursor: pointer;
            transition: all 0.2s ease;
            margin-top: 8px;
        }
        .add-selected-btn:hover {
            opacity: 0.85;
        }
        @media (max-width: 768px) {
            .profiles-container { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
<div class="dashboard-sidebar" id="dashboard-sidebar">
    <div class="sidebar-header"><h2>MENU</h2></div>
<nav class="sidebar-nav">
        <a href="/" class="sidebar-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
            Main
        </a>
        <a href="/accounts" class="sidebar-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
            Accounts
        </a>
        <a href="/daily-claim" class="sidebar-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0-3.5 3.5h-5A3.5 3.5 0 0 1 5 5h7"></path><path d="M12 2a4 4 0 0 1 4 4v12a4 4 0 0 1-4 4 4 4 0 0 1-4-4V6a4 4 0 0 1 4-4z"></path></svg>
            Daily Claim
        </a>
        <a href="/profiles" class="sidebar-link active">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
            Profiles
        </a>
        <a href="/membership" class="sidebar-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"></path><path d="M2 17l10 5 10-5"></path><path d="M2 12l10 5 10-5"></path></svg>
            Membership
        </a>
    </nav>
    <div class="sidebar-footer">
        <a href="/logout" class="sidebar-link settings-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
            Logout
        </a>
    </div>
</div>
<div class="sidebar-trigger" id="sidebarTrigger" onclick="toggleSidebar()" title="Toggle Menu">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
</div>
<div class="sidebar-overlay" id="sidebar-overlay" onclick="closeSidebar()"></div>

<header class="header">
<div style="display:flex;align-items:center;justify-content:center;gap:16px;position:relative;flex:1">
    <h1 style="text-align:center;margin:0 auto;padding:0 20px;">CASINO PROFILES</h1>
</div>
<div style="display:flex;align-items:center;gap:12px;">
    <button class="theme-toggle" onclick="toggleTheme()" title="Toggle Theme" id="themeBtn">&#127769;</button>
</div>
</header>

<div class="container">
    <div class="section-title"><span>YOUR PROFILES</span></div>
    <div id="selected-count" class="selected-count" style="display:none;"></div>
    <div class="profiles-container" id="profiles-grid"></div>
</div>

<button class="add-casino-btn" onclick="showAddCasinoModal()" title="Add Casino">+</button>

<!-- Add Casino Modal -->
<div class="modal-overlay" id="add-casino-modal">
    <div class="modal-box">
        <button class="modal-close" onclick="hideAddCasinoModal()">&times;</button>
        <h2>ADD CASINO</h2>
        <input type="text" class="modal-search" id="casino-search" placeholder="Search casinos..." oninput="filterCasinoList()">
        <div id="selected-count" class="selected-count" style="display:none;"></div>
        <div id="casino-list"></div>
        <button class="add-selected-btn" id="add-selected-btn" style="display:none;" onclick="addSelectedCasinos()">Add Selected</button>
    </div>
</div>

<script>
let sites = ___SITES___;
let accounts = ___ACCOUNTS___;
let selectedCasinos = new Set();

const CASINO_LIST = [
    {name:"Crown Coins",tier:"S"},{name:"McLuck",tier:"S"},{name:"Spree",tier:"S"},{name:"Pulsz",tier:"S"},{name:"PlayFame",tier:"S"},{name:"Jackpota",tier:"S"},{name:"Stake",tier:"S"},{name:"HelloMillions",tier:"S"},{name:"Shuffle",tier:"S"},{name:"MyPrize",tier:"S"},{name:"Lonestar",tier:"S"},{name:"RealPrize",tier:"S"},{name:"WOW Vegas",tier:"S"},{name:"Modo",tier:"S"},{name:"SpinBlitz",tier:"S"},{name:"ReBet",tier:"S"},{name:"Pulsz Bingo",tier:"S"},{name:"Legendz",tier:"S"},{name:"LuckyHands",tier:"S"},{name:"MegaBonanza",tier:"S"},{name:"Card Crush",tier:"S"},{name:"Dogg House",tier:"S"},{name:"Zula",tier:"S"},{name:"Fortune Wins",tier:"S"},{name:"Sportzino",tier:"S"},{name:"LuckyLand Slots",tier:"S"},{name:"LuckyLand Casino",tier:"S"},{name:"Chumba",tier:"S"},
    {name:"CoinsBack Casino",tier:"A"},{name:"Coin Wizard",tier:"A"},{name:"Clash5",tier:"A"},{name:"ThrillCoins",tier:"A"},{name:"SweetSweeps",tier:"A"},{name:"LuckyRush",tier:"A"},{name:"FortunaRush",tier:"A"},{name:"BangCoins",tier:"A"},{name:"DimeSweeps",tier:"A"},{name:"SweepsRoyal",tier:"A"},{name:"RichSweeps",tier:"A"},{name:"SpeedSweeps",tier:"A"},{name:"Ace",tier:"A"},{name:"Jackpot Go",tier:"A"},{name:"WinBonanza",tier:"A"},{name:"Stackr",tier:"A"},{name:"Novig",tier:"A"},{name:"Dara",tier:"A"},{name:"Chanced",tier:"A"},{name:"Rolla",tier:"A"},{name:"Clubs",tier:"A"},{name:"ChipNWin",tier:"A"},{name:"Legacy Arcade",tier:"A"},{name:"Golden Hearts",tier:"A"},{name:"Fliff",tier:"A"},{name:"Thrillz",tier:"A"},{name:"Global Poker",tier:"A"},{name:"American Luck",tier:"A"},{name:"Moozi",tier:"A"},{name:"Punt",tier:"A"},{name:"Yay",tier:"A"},
    {name:"TaoSweeps",tier:"B"},{name:"OceanKing",tier:"B"},{name:"Scoop",tier:"B"},{name:"SweepsUSA",tier:"B"},{name:"SweepNext",tier:"B"},{name:"Wild",tier:"B"},{name:"Baba",tier:"B"},{name:"High5",tier:"B"},{name:"LuckyBits Vegas",tier:"B"},{name:"Lavish Luck",tier:"B"},{name:"AcornFun",tier:"B"},{name:"LunaLand",tier:"B"},{name:"LuckParty",tier:"B"},{name:"PeakPlay",tier:"B"},{name:"Ruby Sweeps",tier:"B"},{name:"Cluck",tier:"B"},{name:"SpinSaga",tier:"B"},{name:"SorceryReels",tier:"B"},{name:"Betr",tier:"B"},{name:"SpinPals",tier:"B"},{name:"Sidepot",tier:"B"},{name:"Scrooge",tier:"B"}
];

function toggleSidebar() {
    document.getElementById('dashboard-sidebar').classList.toggle('open');
    document.getElementById('sidebar-overlay').classList.toggle('active');
    var trigger = document.getElementById('sidebarTrigger');
    if (trigger) trigger.classList.toggle('open');
}
function closeSidebar() {
    document.getElementById('dashboard-sidebar').classList.remove('open');
    document.getElementById('sidebar-overlay').classList.remove('active');
    var trigger = document.getElementById('sidebarTrigger');
    if (trigger) trigger.classList.remove('open');
}
function toggleTheme() {
    var html = document.documentElement;
    var btn = document.getElementById('themeBtn');
    if (html.getAttribute('data-theme') === 'light') {
        html.removeAttribute('data-theme');
        btn.textContent = '🌙';
        localStorage.setItem('theme', 'dark');
    } else {
        html.setAttribute('data-theme', 'light');
        btn.textContent = '☀️';
        localStorage.setItem('theme', 'light');
    }
}
(function() {
    var saved = localStorage.getItem('theme');
    if (saved === 'light') {
        document.documentElement.setAttribute('data-theme', 'light');
        var btn = document.getElementById('themeBtn');
        if (btn) btn.textContent = '☀️';
    }
})();

function getDomainForCasino(name) {
    var map = {
        "Crown Coins":"crowncoinscasino.com","McLuck":"mcluck.com","Spree":"spree.com","Pulsz":"pulsz.com","PlayFame":"playfame.com","Jackpota":"jackpota.com","Stake":"stake.us","HelloMillions":"hellomillions.com","Shuffle":"shuffle.com","MyPrize":"myprize.com","Lonestar":"lonestarcasino.com","RealPrize":"realprize.com","WOW Vegas":"wowvegas.com","Modo":"modocasino.com","SpinBlitz":"spinblitz.com","ReBet":"rebet.com","Pulsz Bingo":"pulszbingo.com","Legendz":"legendz.com","LuckyHands":"luckyhands.com","MegaBonanza":"megabonanza.com","Card Crush":"cardcrush.com","Dogg House":"dogghousecasino.com","Zula":"zulacasino.com","Fortune Wins":"fortunecoins.com","Sportzino":"sportzino.com","LuckyLand Slots":"luckylandslots.com","LuckyLand Casino":"luckylandcasino.com","Chumba":"chumbacasino.com",
        "CoinsBack Casino":"coinsback.com","Coin Wizard":"coinwizard.com","Clash5":"clash5.com","ThrillCoins":"thrillcoins.com","SweetSweeps":"sweetsweeps.com","LuckyRush":"luckyrush.com","FortunaRush":"fortunarush.com","BangCoins":"bangcoins.com","DimeSweeps":"dimesweeps.com","SweepsRoyal":"sweepsroyal.com","RichSweeps":"richsweeps.com","SpeedSweeps":"speedsweeps.com","Ace":"acecasino.com","Jackpot Go":"jackpotgo.com","WinBonanza":"winbonanza.com","Stackr":"stackr.com","Novig":"novig.com","Dara":"daracasino.com","Chanced":"chanced.com","Rolla":"rolla.com","Clubs":"clubs.casino","ChipNWin":"chipnwin.com","Legacy Arcade":"legacyarcade.com","Golden Hearts":"goldenheartsgames.com","Fliff":"fliff.com","Thrillz":"thrillz.com","Global Poker":"globalpoker.com","American Luck":"americanluck.com","Moozi":"moozi.com","Punt":"punt.com","Yay":"yaycasino.com",
        "TaoSweeps":"taosweeps.com","OceanKing":"oceankingcasino.com","Scoop":"scoopcasino.com","SweepsUSA":"sweepsusa.com","SweepNext":"sweepnext.com","Wild":"wild.io","Baba":"babacasino.com","High5":"high5casino.com","LuckyBits Vegas":"luckybitsvegas.com","Lavish Luck":"lavishluck.com","AcornFun":"acornfun.com","LunaLand":"lunaland.com","LuckParty":"luckparty.com","PeakPlay":"peakplay.com","Ruby Sweeps":"rubysweeps.com","Cluck":"cluck.com","SpinSaga":"spinsaga.com","SorceryReels":"sorceryreels.com","Betr":"betr.com",        "BetOnline":"betonline.ag",
        "SpinPals":"spinpals.com","Sidepot":"sidepot.com","Scrooge":"scroogecasino.com"
    };
    return map[name] || (name.toLowerCase().replace(/[^a-z0-9]/g,'') + '.com');
}

function getUrlForCasino(name) {
    var domain = getDomainForCasino(name);
    return 'https://www.' + domain;
}

function renderProfiles() {
    var grid = document.getElementById('profiles-grid');
    var siteNames = new Set(sites.map(function(s) { return s.name; }));
    var hasProfiles = false;
    grid.innerHTML = '';

    sites.forEach(function(site) {
        var account = accounts[site.domain] || {};
        var username = account.username || '';
        var password = account.password || '';
        var lastClaim = account.last_claim || '';
        hasProfiles = true;
        var card = document.createElement('div');
        card.className = 'profile-card';
        card.innerHTML =
            '<h3>' + site.name + '</h3>' +
            '<div class="login-setup" style="margin:0;padding:0;border:none;background:none;">' +
            '<div class="login-fields">' +
            '<div class="login-field-row">' +
            '<div class="profile-field"><label>Email / Username</label><input type="text" id="user-' + site.domain.replace(/\\./g,'-') + '" value="' + username + '" placeholder="Email or username"></div>' +
            '<div class="profile-field"><label>Password</label><input type="password" id="pass-' + site.domain.replace(/\\./g,'-') + '" value="' + password + '" placeholder="Password"></div>' +
            '<button class="google-btn" onclick="window.open(\'' + getUrlForCasino(site.name) + '\',\'_blank\')" title="Open casino in browser">G</button>' +
            '</div>' +
            '</div>' +
            '</div>' +
            '<div class="profile-actions">' +
            '<button onclick="saveProfile(\'' + site.domain + '\')">SAVE</button>' +
            '<button class="delete-btn" onclick="deleteProfile(\'' + site.domain + '\')">DELETE</button>' +
            '</div>';
        grid.appendChild(card);
    });

    if (!hasProfiles) {
        grid.innerHTML = '<div class="empty-message">No casino profiles yet. Click the + button to add one.</div>';
    }
}

function saveProfile(domain) {
    var safeDomain = domain.replace(/\\./g,'-');
    var username = document.getElementById('user-' + safeDomain).value.trim();
    var password = document.getElementById('pass-' + safeDomain).value.trim();
    fetch('/api/save-account', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({domain: domain, username: username, password: password})
    }).then(function(r) { return r.json(); }).then(function(data) {
        if (data.ok) { accounts[domain] = {username: username, password: password}; }
    });
}

function deleteProfile(domain) {
    if (!confirm('Delete this profile?')) return;
    fetch('/api/save-account', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({domain: domain, username: '', password: ''})
    }).then(function(r) { return r.json(); }).then(function() {
        delete accounts[domain];
        renderProfiles();
    });
}

function showAddCasinoModal() {
    document.getElementById('add-casino-modal').classList.add('active');
    selectedCasinos.clear();
    renderCasinoList();
    document.getElementById('casino-search').value = '';
    document.getElementById('casino-search').focus();
}

function hideAddCasinoModal() {
    document.getElementById('add-casino-modal').classList.remove('active');
}

function renderCasinoList() {
    var container = document.getElementById('casino-list');
    var existing = new Set(sites.map(function(s) { return s.name; }));
    var q = document.getElementById('casino-search').value.toLowerCase();
    var filtered = CASINO_LIST.filter(function(c) {
        return !existing.has(c.name) && c.name.toLowerCase().includes(q);
    });
    container.innerHTML = filtered.map(function(c) {
        var sel = selectedCasinos.has(c.name) ? ' style="background:var(--surface-hover);border-color:var(--accent);"' : '';
        return '<div class="casino-list-item"' + sel + ' onclick="toggleCasinoSelect(\'' + c.name.replace(/'/g,"\\'") + '\')">' +
            '<span><span class="name">' + c.name + '</span><span class="tier-badge tier-' + c.tier.toLowerCase() + '">' + c.tier + '</span></span>' +
            '<span class="add-icon">' + (selectedCasinos.has(c.name) ? '&#10003;' : '+') + '</span></div>';
    }).join('');
    updateSelectedCount();
}

function toggleCasinoSelect(name) {
    if (selectedCasinos.has(name)) { selectedCasinos.delete(name); }
    else { selectedCasinos.add(name); }
    renderCasinoList();
}

function updateSelectedCount() {
    var count = selectedCasinos.size;
    var btn = document.getElementById('add-selected-btn');
    if (count > 0) { btn.style.display = 'block'; btn.textContent = 'Add Selected (' + count + ')'; }
    else { btn.style.display = 'none'; }
}

function addSelectedCasinos() {
    selectedCasinos.forEach(function(name) {
        var domain = getDomainForCasino(name);
        var url = getUrlForCasino(name);
        fetch('/api/add-site', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: name, domain: domain, url: url})
        }).then(function(r) { return r.json(); }).then(function(data) {
            if (data.ok) { sites.push({name: name, domain: domain, url: url}); }
        });
    });
    selectedCasinos.clear();
    hideAddCasinoModal();
    setTimeout(renderProfiles, 500);
}

function filterCasinoList() {
    renderCasinoList();
}

renderProfiles();
</script>
</body>
</html>"""

# ================== MAIN DASHBOARD HTML ==================
MAIN_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Sweepstakes Dashboard</title>
    """ + DASHBOARD_CSS + """
</head>
<body>
<div class="dashboard-sidebar" id="dashboard-sidebar">
    <div class="sidebar-header">
        <h2>MENU</h2>
    </div>
<nav class="sidebar-nav">
        <a href="/" class="sidebar-link active" onclick="showSection('main')">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="3" width="7" height="7"></rect>
                <rect x="14" y="3" width="7" height="7"></rect>
                <rect x="14" y="14" width="7" height="7"></rect>
                <rect x="3" y="14" width="7" height="7"></rect>
            </svg>
            Main
        </a>
        <a href="/accounts" class="sidebar-link" onclick="showSection('accounts')">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                <circle cx="12" cy="7" r="4"></circle>
            </svg>
            Accounts
        </a>
        <a href="/daily-claim" class="sidebar-link" onclick="showSection('daily')">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0-3.5 3.5h-5A3.5 3.5 0 0 1 5 5h7"></path>
                <path d="M12 2a4 4 0 0 1 4 4v12a4 4 0 0 1-4 4 4 4 0 0 1-4-4V6a4 4 0 0 1 4-4z"></path>
            </svg>
            Daily Claim
        </a>
        <a href="/daily-claims" class="sidebar-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <polyline points="12 6 12 12 16 14"></polyline>
            </svg>
            Daily Claims
        </a>
        <a href="/profiles" class="sidebar-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                <circle cx="9" cy="7" r="4"></circle>
                <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
                <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
            </svg>
            Profiles
        </a>
        <a href="/proxies" class="sidebar-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
            </svg>
            Proxies
        </a>
        <a href="/membership" class="sidebar-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
                <path d="M2 17l10 5 10-5"></path>
                <path d="M2 12l10 5 10-5"></path>
            </svg>
            Membership
        </a>
    </nav>
    <div class="sidebar-footer">
        <a href="/logout" class="sidebar-link settings-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                <polyline points="16 17 21 12 16 7"></polyline>
                <line x1="21" y1="12" x2="9" y2="12"></line>
            </svg>
            Logout
        </a>
        <a href="/settings" class="sidebar-link settings-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="3"></circle>
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
            </svg>
            Settings
        </a>
    </div>
</div>
<div class="sidebar-trigger" id="sidebarTrigger" onclick="toggleSidebar()" title="Toggle Menu">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
</div>
<div class="sidebar-overlay" id="sidebar-overlay" onclick="closeSidebar()"></div>

<header class="header">
<div style="display:flex;align-items:center;justify-content:center;gap:16px;position:relative;flex:1">
    <h1 style="font-family:'Outfit',sans-serif;font-weight:800;text-align:center;margin:0 auto;padding:0 20px;letter-spacing:2px;">SWEEPSTAKES <span style="background:linear-gradient(135deg,#a855f7,#d946ef);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;">MONITOR</span></h1>
</div>
<div style="display:flex;align-items:center;gap:12px;">
    <button class="theme-toggle" onclick="toggleTheme()" title="Toggle Theme" id="themeBtn">🌙</button>
    <div class="status-badge">
        <span class="status-dot" id="status-dot"></span>
        <span id="status">OFFLINE</span>
    </div>
    <div class="user-profile" id="userProfile">
        <div class="user-avatar" onclick="toggleProfileDropdown()">
            <img id="profileAvatar" src="/api/avatar" style="width:100%;height:100%;border-radius:50%;object-fit:cover;display:none;" onerror="this.style.display='none'" />
            <svg id="avatarFallback" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                <circle cx="12" cy="7" r="4"></circle>
            </svg>
        </div>
        <div class="profile-dropdown" id="profileDropdown">
            <a href="/settings">⚙ Settings</a>
            <a href="/logout">🚪 Logout</a>
        </div>
    </div>
</div>
</header>

<div class="container">
    <div class="stats-grid">
        <div class="stat-card">
            <div class="icon">✅</div>
            <div class="value" id="claimed">0</div>
            <div class="label">Links Successfully Claimed</div>
        </div>
        <div class="stat-card">
            <div class="icon">🔗</div>
            <div class="value" id="found">0</div>
            <div class="label">Sweepstakes Alerts</div>
        </div>
        <div class="stat-card">
            <div class="icon">🎰</div>
            <div class="value" id="sc-total">0</div>
            <div class="label">Total SC Claimed</div>
        </div>
        <div class="stat-card">
            <div class="icon">⚡</div>
            <div class="value" id="rate">0/s</div>
            <div class="label">Monitor Rate</div>
        </div>
    </div>
    <div class="section-title">
        <span>LATEST UPDATES</span>
        <span style="font-size:0.7rem;opacity:0.6;margin-left:auto">Showing 5 most recent posts</span>
    </div>
    <div class="links-list scrollable" id="links-list">
        <div class="empty-state">No free spin/SC alerts yet...</div>
    </div>
</div>
<button class="refresh-btn" onclick="refreshData()">↻</button>
<script>
let lastAlertCount = 0;
let verifiedAt = null;
let serverStartTime = null;

function formatUptime(seconds) {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

function formatPostTime(timestamp) {
    if (!timestamp) return 'recently';
    const date = new Date(timestamp * 1000);
    const cstOffset = -6 * 60;
    const cst = new Date(date.getTime() + (date.getTimezoneOffset() + cstOffset) * 60000);
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    const mon = months[cst.getMonth()];
    const day = cst.getDate();
    const year = cst.getFullYear();
    let hour = cst.getHours();
    const ampm = hour >= 12 ? 'PM' : 'AM';
    hour = hour % 12 || 12;
    const min = String(cst.getMinutes()).padStart(2,'0');
    const sec = String(cst.getSeconds()).padStart(2,'0');
    return `${mon} ${day}, ${year} ${hour}:${min}:${sec} ${ampm} CST`;
}

function toggleSidebar() {
    const sidebar = document.getElementById('dashboard-sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    const trigger = document.getElementById('sidebarTrigger');
    sidebar.classList.toggle('open');
    overlay.classList.toggle('active');
    if (trigger) trigger.classList.toggle('open');
}

function closeSidebar() {
    const sidebar = document.getElementById('dashboard-sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    const trigger = document.getElementById('sidebarTrigger');
    sidebar.classList.remove('open');
    overlay.classList.remove('active');
    if (trigger) trigger.classList.remove('open');
}

function showSection(section) {
    document.querySelectorAll('.sidebar-link').forEach(l => l.classList.remove('active'));
    event.target.closest('.sidebar-link').classList.add('active');
    closeSidebar();
}

function showSettings() {
    window.location.href = '/settings';
    closeSidebar();
}

function toggleProfileDropdown() {
    const dd = document.getElementById('profileDropdown');
    dd.classList.toggle('show');
}

document.addEventListener('click', function(e) {
    const dd = document.getElementById('profileDropdown');
    const profile = document.getElementById('userProfile');
    if (dd && profile && !profile.contains(e.target)) {
        dd.classList.remove('show');
    }
});

async function refreshData() {
    try {
        const r = await fetch('/api/data');
        const d = await r.json();
        // Check for profile avatar
        const avatarImg = document.getElementById('profileAvatar');
        const avatarFallback = document.getElementById('avatarFallback');
        if (avatarImg) {
            avatarImg.src = '/api/avatar?' + Date.now();
            avatarImg.onload = function() { avatarImg.style.display = 'block'; if (avatarFallback) avatarFallback.style.display = 'none'; };
            avatarImg.onerror = function() { avatarImg.style.display = 'none'; if (avatarFallback) avatarFallback.style.display = 'block'; };
        }
        document.getElementById('claimed').textContent = (d.claimed || 0).toLocaleString();
        document.getElementById('found').textContent = d.found;
        document.getElementById('sc-total').textContent = (d.sc_total || 0).toFixed(2);
        if (d.scanned !== undefined && d.runtime > 0) {
            document.getElementById('rate').textContent = (d.scanned/d.runtime).toFixed(1) + '/s';
        }
        
        const statusEl = document.getElementById('status');
        const statusDot = document.getElementById('status-dot');
        statusEl.textContent = d.bot_status ? d.bot_status.toUpperCase() : 'OFFLINE';
        statusDot.className = 'status-dot';
        if (d.bot_status === 'online') {
            statusDot.classList.add('online');
        } else if (d.bot_status === 'checking') {
            statusDot.classList.add('checking');
        }
        
        if (d.verified_at !== null && d.verified_at !== undefined) {
            if (!verifiedAt) {
                verifiedAt = d.verified_at * 1000;
            }
        }
        
        // Render daily posts as bars
        const list = document.getElementById('links-list');
        if (d.daily_posts && d.daily_posts.length > 0) {
            const maxSc = Math.max(...d.daily_posts.map(p => p.sc_amount || 0), 1);
            list.innerHTML = d.daily_posts.slice(0, 10).map(p => {
                const pct = p.sc_amount ? Math.round((p.sc_amount / maxSc) * 100) : 20;
                const color = p.sc_amount >= 2 ? '#00ff88' : p.sc_amount >= 1 ? '#ffd700' : '#666';
                const scLabel = p.sc_amount ? p.sc_amount + ' SC' : 'FREE SPIN';
                return `
                    <div class="daily-bar" onclick="window.open('${p.url || '#'}','_blank')">
                        <span class="bar-casino">${p.casino_name || 'Unknown'}</span>
                        <div class="bar-track">
                            <div class="bar-fill" style="width:${pct}%;background:${color}"></div>
                        </div>
                        <span class="bar-amount" style="color:${color}">${scLabel}</span>
                        <span class="bar-time">${formatPostTime(p.created_utc)}</span>
                    </div>
                `;
            }).join('');
        } else {
            if (d.bot_status === 'online' || d.bot_status === 'checking') {
                list.innerHTML = '<div class="empty-state">No freebies found in the last 24 hours...</div>';
            } else {
                    list.innerHTML = '<div class="empty-state">Monitor is offline. Start the dashboard to begin.</div>';
                }
            }
        }
    } catch(e) { console.error(e); }
}

function toggleTheme() {
    const html = document.documentElement;
    const btn = document.getElementById('themeBtn');
    if (html.getAttribute('data-theme') === 'light') {
        html.removeAttribute('data-theme');
        btn.textContent = '🌙';
        localStorage.setItem('theme', 'dark');
    } else {
        html.setAttribute('data-theme', 'light');
        btn.textContent = '☀️';
        localStorage.setItem('theme', 'light');
    }
}

// Restore theme
(function() {
    const saved = localStorage.getItem('theme');
    if (saved === 'light') {
        document.documentElement.setAttribute('data-theme', 'light');
        const btn = document.getElementById('themeBtn');
        if (btn) btn.textContent = '☀️';
    }
})();

refreshData();
setInterval(refreshData, 1000);
</script>
</body>
</html>"""


# ================== REDDIT MONITOR ==================



# ================== REDDIT MONITOR ==================


# ================== REDDIT MONITOR ==================

# ================== REDDIT MONITOR ==================
def is_mod_post(post):
    title = post.get("title", "").lower()
    author = post.get("author", "").lower()
    distinguished = post.get("distinguished")
    stickied = post.get("stickied", False)
    
    # Only accept moderator/admin distinguished posts
    if distinguished in ["moderator", "admin"]:
        return True
    
    # Exclude ALL stickied posts (usually promotions/sales)
    if stickied:
        return False
    
    # Exclude ANY posts from accounts related to sales/promotions
    sales_accounts = ["bcasino", "casino", "sweep", "bonus", "promo", "offers", "deals", "sales"]
    for acc in sales_accounts:
        if acc in author:
            return False
    
    # Exclude casino advertisements and new casino announcements
    excluded = ["buy", "purchase", "sale", "sell", "advertisement", "ad ", " promo code", "discount", "offer for",
                "join now", "sign up bonus", "referral", "new casino", "casino added", "casinos added", "casino launch",
                "welcome to", "grand opening", "now live", "introducing", "welcome bonus", "deposit bonus",
                "trusted casinos", "full list of", "useful links", "sweepsgrail", "active bonus", "current bonus",
                "best bonus", "top bonus", "exclusive offer", "limited time", "act now", "don't miss",
                "sign up now", "register now", "claim now", "get now", "use code", "bonus code",
                "special offer", "promotion", "deal", "save", "best offer", "highest bonus",
                "promo", "vip bonus", "first deposit", "match bonus", "reload bonus",
                "verify email", "verify account", "confirm email", "kyp", "know your post",
                "icymi", "new casinos", "casinos", "added"]
    for word in excluded:
        if word in title:
            return False
    
    # Only accept posts that specifically mention free spins or free SC
    keywords = ["free spin", "free sc", "free sweeps credit", "free sweeps", "free gold", "sc free", 
                "free sweepscoin", "free sweeps coins", "no deposit", "freeplay", "free play",
                "bonus spin", "bonus sc", "daily spin", "daily sc", "freebie", "free coins",
                "free credits", "free play", "social casino", "exclusive free", "mystery free",
                "wheel spin", "spin wheel", "daily bonus", "hourly bonus", "weekly free",
                "login bonus", "login reward", "daily login", "streak bonus"]
    for word in keywords:
        if word in title:
            return True
    
    return False

def fetch_reddit_posts():
    posts = []
    
    for sr in SUBREDDITS:
        for sort in ["hot", "new"]:
            url = f"https://old.reddit.com/r/{sr}/{sort}.json?limit=25"
            try:
                resp = _reddit_get(url, retries=3)
                if resp.status_code == 200:
                    data = resp.json()
                    if "data" in data and "children" in data["data"]:
                        for child in data["data"]["children"]:
                            p = child["data"]
                            posts.append({
                                "id": p.get("id"),
                                "title": p.get("title"),
                                "url": "https://reddit.com" + p.get("permalink"),
                                "body": p.get("selftext", ""),
                                "author": p.get("author"),
                                "subreddit": p.get("subreddit", sr),
                                "distinguished": p.get("distinguished"),
                                "stickied": p.get("stickied"),
                                "created_utc": p.get("created_utc"),
                            })
                else:
                    print(f"[Reddit] {sr}/{sort} returned status {resp.status_code}")
            except requests.exceptions.Timeout:
                print(f"[Reddit] Timeout fetching {sr}/{sort}")
            except requests.exceptions.ConnectionError:
                print(f"[Reddit] Connection error fetching {sr}/{sort}")
            except Exception as e:
                print(f"[Reddit] Error fetching {sr}/{sort}: {e}")
    
    return posts

def monitor_loop():
    global state
    start_time = time.time()
    print(f"[{datetime.now()}] Monitor starting...")
    while True:
        try:
            with state_lock:
                state["bot_status"] = "online"
                state["status"] = "online"
            posts = fetch_reddit_posts()
            print(f"[{datetime.now()}] Fetched {len(posts)} posts")
            with state_lock:
                state["scanned"] += len(posts)
                state["status"] = "checking"
                new_links = []
                for p in posts:
                    pid = p.get("id")
                    if not any(l.get("id") == pid for l in state["links"]):
                        # Only process moderator posts
                        if not is_mod_post(p):
                            continue
                        title = p.get("title", "")
                        body = p.get("body", "")
                        post_time = p.get("created_utc", 0)
                        if time.time() - post_time <= 86400:
                            # Check for Free X SC pattern first (dedicated channel)
                            free_sc = is_free_sc_post(title, body)
                            sc_amount = free_sc["sc_amount"] if free_sc["valid"] else None
                            # Store enriched link data
                            link_entry = dict(p)
                            link_entry["post_time"] = post_time
                            link_entry["sc_amount"] = sc_amount
                            
                            if free_sc["valid"]:
                                state["links"].append(link_entry)
                                monitor_feed.append({"title": title, "url": extracted_link, "subreddit": p.get("subreddit"), "time": datetime.now().isoformat(), "sc_amount": sc_amount})
                                new_links.append(link_entry)
                                extracted_link = extract_link_from_body(body)
                                post_freecash_discord(title, extracted_link, post_time, sc_amount)
                                post_to_claims_discord(title, extracted_link, post_time, sc_amount)
                                print(f"[{datetime.now()}] Free SC found: {title[:50]}")
                            # Also check general free posts for main webhook
                            elif is_valid_free_post(title, body):
                                state["links"].append(link_entry)
                                monitor_feed.append({"title": title, "url": extracted_link, "subreddit": p.get("subreddit"), "time": datetime.now().isoformat(), "sc_amount": sc_amount})
                                new_links.append(link_entry)
                                extracted_link = extract_link_from_body(body)
                                post_to_discord(
                                    title,
                                    extracted_link,
                                    post_time,
                                    is_live=True,
                                    sc_amount=sc_amount
                                )
                                post_to_claims_discord(title, extracted_link, post_time, sc_amount)
                                print(f"[{datetime.now()}] New link found: {title[:50]}")
                                state["last_alert"] = {
                                    "title": p.get("title"),
                                    "url": p.get("url"),
                                    "author": p.get("author"),
                                    "subreddit": p.get("subreddit"),
                                    "timestamp": datetime.now().isoformat(),
                                    "post_time": post_time
                                }
                # Trigger automation for new links
                for link in new_links:
                    print(f"[{datetime.now()}] Triggering automation for: {link.get('url')}")
                    trigger_automation(link.get("url"), link.get("title"))
                # Sort links by post_time descending (newest first)
                state["links"].sort(key=lambda x: x.get("post_time") or x.get("created_utc", 0), reverse=True)
                state["found"] = len(state["links"])
                state["runtime"] = int(time.time() - start_time)
                state["status"] = "online"
                state["bot_status"] = "online"
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"[{datetime.now()}] Monitor error: {e}")
            traceback.print_exc()
            with state_lock:
                state["status"] = "checking"
                state["bot_status"] = "online"
            time.sleep(CHECK_INTERVAL)

def trigger_automation(url, title):
    """Trigger automation based on new link found"""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")
        
        # Check if we have account for this domain
        accounts = load_accounts()
        if domain in accounts:
            print(f"Triggering automation for {domain}: {title}")
            # Start automation in background
            def run_auto():
                auto = CasinoAutomation(headless=HEADLESS_MODE)
                if auto.start():
                    if auto.login(domain, accounts[domain]["username"], accounts[domain]["password"]):
                        sc = auto.claim_daily_bonus(domain)
                        with state_lock:
                            state["claimed"] += 1
                            state["sc_total"] = round(state["sc_total"] + sc, 2)
                            accounts = load_accounts()
                            accounts[domain]["sc_total"] = round(accounts[domain].get("sc_total", 0) + sc, 2)
                            save_accounts(accounts)
                    auto.close()
            t = threading.Thread(target=run_auto, daemon=True)
            t.start()
        else:
            print(f"No account found for {domain}")
    except Exception as e:
        print(f"Automation trigger error: {e}")

# ================== FLASK APP ==================
app = Flask(__name__)
app.secret_key = SESSION_SECRET

@app.after_request
def add_cors_headers(resp):
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    return resp

@app.route("/")
def index():
    # Tier 1: Check license key
    license_data = session.get('license')
    if not license_data or not license_data.get('valid'):
        return LICENSE_HTML
    # Tier 2: Check Discord verification
    verified_id = session.get('discord_id') or request.cookies.get('discord_id')
    if not verified_id:
        return VERIFY_HTML
    # Tier 3: Show dashboard
    return render_dashboard()

@app.route("/api/license", methods=["POST"])
def api_license():
    data = request.get_json(silent=True) or {}
    key = data.get("key", "")
    result = validate_license_key(key)
    if result["valid"]:
        session['license'] = {
            "valid": True,
            "tier": result.get("tier", "basic"),
            "key": result.get("key", key)
        }
        return jsonify({"valid": True, "tier": result.get("tier", "basic")})
    return jsonify({"valid": False})

@app.route("/api/activate", methods=["POST"])
def api_activate():
    """Online activation endpoint with HWID binding."""
    data = request.get_json(silent=True) or {}
    raw_key = data.get("key", "").strip()
    hwid = data.get("hwid", "").strip()
    if not raw_key or not hwid:
        return jsonify({"valid": False, "reason": "Missing key or hardware ID."}), 400
    result = validate_license_key(raw_key)
    if not result.get("valid"):
        return jsonify({"valid": False, "reason": result.get("reason", "Invalid key.")})
    result["hwid"] = hwid
    return jsonify({"valid": True, "tier": result.get("tier", "premium"), "key": result.get("key", raw_key)})

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

def render_dashboard():
    # Check license has premium tier for full dashboard
    license_data = session.get('license', {})
    if license_data.get('tier') in ('premium', 'basic'):
        return MAIN_DASHBOARD_HTML
    return LICENSE_HTML

@app.route("/accounts")
def accounts_page():
    verified_id = session.get('discord_id') or request.cookies.get('discord_id')
    if not verified_id:
        return redirect("/")
    sites = load_sites()
    accounts = load_accounts()
    html = ACCOUNTS_HTML.replace("___SITES___", json.dumps(sites)).replace("___ACCOUNTS___", json.dumps(accounts))
    return html

@app.route("/daily-claim")
def daily_claim_page():
    verified_id = session.get('discord_id') or request.cookies.get('discord_id')
    if not verified_id:
        return redirect("/")
    sites = load_sites()
    accounts = load_accounts()
    html = DAILY_CLAIM_HTML.replace("___SITES___", json.dumps(sites)).replace("___ACCOUNTS___", json.dumps(accounts))
    return html

@app.route("/profiles")
def profiles_page():
    verified_id = session.get('discord_id') or request.cookies.get('discord_id')
    if not verified_id:
        return redirect("/")
    sites = load_sites()
    accounts = load_accounts()
    html = PROFILES_HTML.replace("___SITES___", json.dumps(sites)).replace("___ACCOUNTS___", json.dumps(accounts))
    return html

@app.route("/daily-claims")
def daily_claims_page():
    verified_id = session.get('discord_id') or request.cookies.get('discord_id')
    if not verified_id:
        return redirect("/")
    sites = load_sites()
    accounts = load_accounts()
    schedule = load_claim_schedule()
    html = DAILY_CLAIMS_HTML.replace("___SITES___", json.dumps(sites)).replace("___ACCOUNTS___", json.dumps(accounts)).replace("___SCHEDULE___", json.dumps(schedule))
    return html

@app.route("/proxies")
def proxies_page():
    verified_id = session.get('discord_id') or request.cookies.get('discord_id')
    if not verified_id:
        return redirect("/")
    return '<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Proxies</title>'+DASHBOARD_CSS+'</head><body><div style="max-width:800px;margin:40px auto;padding:20px"><h1 style="font-family:Righteous;letter-spacing:2px;margin-bottom:20px">PROXIES</h1><p style="color:var(--text-muted)">Proxy management coming soon.</p></div></body></html>'

@app.route("/settings")
def settings_page():
    verified_id = session.get('discord_id') or request.cookies.get('discord_id')
    if not verified_id:
        return redirect("/")
    return '<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Settings</title>'+DASHBOARD_CSS+'</head><body><div style="max-width:800px;margin:40px auto;padding:20px"><h1 style="font-family:Righteous;letter-spacing:2px;margin-bottom:20px">SETTINGS</h1><p style="color:var(--text-muted)">Settings panel coming soon.</p></div></body></html>'

@app.route("/api/claim-now/<domain>", methods=["POST"])
def api_claim_now(domain):
    verified_id = session.get('discord_id') or request.cookies.get('discord_id')
    if not verified_id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    accounts = load_accounts()
    if domain not in accounts:
        return jsonify({"ok": False, "error": "No account"}), 404
    def do_manual_claim(d):
        accts = load_accounts()
        schedule = load_claim_schedule()
        schedule[d] = schedule.get(d, {"last_claim": 0, "status": "claiming"})
        schedule[d]["status"] = "claiming"
        save_claim_schedule(schedule)
        auto = CasinoAutomation(headless=HEADLESS_MODE)
        if auto.start():
            if auto.login(d, accts[d]["username"], accts[d]["password"]):
                sc = auto.claim_daily_bonus(d)
                if sc > 0:
                    schedule[d]["last_claim"] = time.time()
                    schedule[d]["status"] = "done"
                    with state_lock:
                        state["claimed"] += 1
                        state["sc_total"] = round(state["sc_total"] + sc, 2)
                    accts = load_accounts()
                    accts[d]["sc_total"] = round(accts[d].get("sc_total", 0) + sc, 2)
                    save_accounts(accts)
                else:
                    schedule[d]["status"] = "error"
            else:
                schedule[d]["status"] = "error"
            auto.close()
        else:
            schedule[d]["status"] = "error"
        save_claim_schedule(schedule)
    t = threading.Thread(target=do_manual_claim, args=(domain,), daemon=True)
    t.start()
    return jsonify({"ok": True, "message": "Claim started"})

@app.route("/api/claim-schedule", methods=["GET"])
def api_get_claim_schedule():
    verified_id = session.get('discord_id') or request.cookies.get('discord_id')
    if not verified_id:
        return jsonify({}), 401
    return jsonify(load_claim_schedule())

@app.route("/api/avatar", methods=["GET"])
def api_get_avatar():
    discord_id = session.get('discord_id') or request.cookies.get('discord_id')
    if not discord_id:
        return "", 404
    for ext in ["png", "jpg", "jpeg", "gif", "webp"]:
        path = PROFILE_PICS_DIR / f"{discord_id}.{ext}"
        if path.exists():
            return send_file(str(path), mimetype=f"image/{'jpeg' if ext == 'jpg' else ext}")
    return "", 404

@app.route("/api/avatar", methods=["POST"])
def api_upload_avatar():
    discord_id = session.get('discord_id') or request.cookies.get('discord_id')
    if not discord_id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    if 'avatar' not in request.files:
        return jsonify({"ok": False, "error": "No file"}), 400
    file = request.files['avatar']
    if file.filename == '':
        return jsonify({"ok": False, "error": "No file"}), 400
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else 'png'
    if ext not in ('png', 'jpg', 'jpeg', 'gif', 'webp'):
        return jsonify({"ok": False, "error": "Invalid format"}), 400
    # Delete old avatar files
    for old_ext in ["png", "jpg", "jpeg", "gif", "webp"]:
        old_path = PROFILE_PICS_DIR / f"{discord_id}.{old_ext}"
        if old_path.exists():
            old_path.unlink()
    file.save(str(PROFILE_PICS_DIR / f"{discord_id}.{ext}"))
    return jsonify({"ok": True})

@app.route("/remove-user", methods=["POST"])
def remove_user():
    if not session.get('admin_id') and not session.get('admin_email'):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    discord_id = str(data.get("discord_id", "")).strip()
    if discord_id:
        approved = load_approved_users()
        if discord_id in approved["discord_ids"]:
            approved["discord_ids"].remove(discord_id)
            save_approved_users(approved)
        return jsonify({"ok": True})
    return jsonify({"error": "Invalid ID"}), 400

@app.route("/api/admin-invite", methods=["POST"])
def admin_invite():
    if not session.get('admin_id') and not session.get('admin_email'):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    discord_id = data.get("discord_id", "").strip()
    message = data.get("message", "You have been invited for an interview.")
    if discord_id:
        invites_file = SCRIPT_DIR / "pending_invites.json"
        invites = {}
        if invites_file.exists():
            with open(invites_file, 'r') as f:
                invites = json.load(f)
        invites[discord_id] = {"message": message, "sent_at": time.time()}
        with open(invites_file, 'w') as f:
            json.dump(invites, f, indent=2)
        return jsonify({"ok": True})
    return jsonify({"error": "Invalid ID"}), 400
    
@app.route("/discord-faq")
def discord_faq():
    return send_from_directory(SCRIPT_DIR, "discord_faq.html")

@app.route("/api/flood-discord", methods=["POST"])
def flood_discord():
    try:
        admin = load_admin_users()
        admin_id = session.get('admin_id') or request.cookies.get('admin_id')
        if not admin_id or admin_id not in admin.get("admins", []):
            return jsonify({"error": "Unauthorized"}), 401
        
        def run_flood():
            posted = flood_discord_last_24h()
            with state_lock:
                state["last_flood"] = {"posted": posted, "time": time.time()}
        
        thread = threading.Thread(target=run_flood, daemon=True)
        thread.start()
        return jsonify({"ok": True, "message": "Flood started! Posts will be posted to Discord."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/verify-discord", methods=["POST"])
def verify_discord():
    data = request.get_json(silent=True) or {}
    discord_id = str(data.get("discord_id", "")).strip()
    
    # Validate Discord ID (17-18 digits)
    if not discord_id.isdigit() or len(discord_id) < 17:
        return jsonify({"ok": False}), 400
    
    # Check against approved users
    approved = load_approved_users()
    if discord_id in approved.get("discord_ids", []):
        session['discord_id'] = discord_id
        session['verified_at'] = time.time()
        response = make_response(jsonify({"ok": True}))
        response.set_cookie('discord_id', discord_id, httponly=True, samesite='Strict')
        response.set_cookie('verified_at', str(session['verified_at']), httponly=True, samesite='Strict')
        return response
    
    return jsonify({"ok": False}), 401

@app.route("/membership")
def membership_page():
    license_data = session.get('license')
    if not license_data or not license_data.get('valid'):
        return redirect("/")
    # Serve static membership content
    idx = MEMBERSHIP_DIR / "index.html"
    if idx.exists():
        return send_from_directory(MEMBERSHIP_DIR, "index.html")
    return "<h1>Membership</h1><p>Membership content coming soon.</p><a href='/'>Back to Dashboard</a>"

def _check_admin_auth():
    """Return True if session auth or X-Admin-Key header matches ADMIN_KEY."""
    if session.get('admin_id') or session.get('admin_email'):
        return True
    key_header = request.headers.get('X-Admin-Key', '')
    if key_header == ADMIN_KEY:
        return True
    return False

def _admin_key_header(headers):
    """Add X-Admin-Key to headers dict if available."""
    h = dict(headers)
    h['X-Admin-Key'] = ADMIN_KEY
    return h

@app.route("/api/admin-licenses")
def api_admin_licenses():
    if not _check_admin_auth():
        return jsonify({"error": "Unauthorized"}), 401
    keys = load_license_keys()
    return jsonify(keys)

@app.route("/api/admin-generate-license", methods=["POST"])
def api_admin_generate_license():
    if not _check_admin_auth():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    tier = data.get("tier", "premium")
    assigned_to = data.get("assigned_to", "").strip()
    notes = data.get("notes", "").strip()
    manual_key = data.get("manual_key", "").strip().upper()
    if tier not in ("premium", "staff"):
        return jsonify({"error": "Invalid tier"}), 400
    if manual_key:
        new_key = manual_key
    else:
        new_key = generate_license_key()
    keys = load_license_keys()
    keys[new_key] = {"status": "active", "tier": tier, "created": time.time()}
    if assigned_to:
        keys[new_key]["assigned_to"] = assigned_to
    if notes:
        keys[new_key]["notes"] = notes
    save_license_keys(keys)
    return jsonify({"ok": True, "key": new_key, "tier": tier})

@app.route("/api/admin-revoke-license", methods=["POST"])
def api_admin_revoke_license():
    if not _check_admin_auth():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    key_to_revoke = data.get("key", "").strip()
    keys = load_license_keys()
    if key_to_revoke in keys:
        keys[key_to_revoke]["status"] = "revoked"
        save_license_keys(keys)
        return jsonify({"ok": True})
    return jsonify({"error": "Key not found"}), 404

@app.route("/api/data")
def api_data():
    with state_lock:
        data_copy = dict(state)
        # Calculate server uptime (not just monitor runtime)
        if state.get("server_start"):
            data_copy['server_uptime'] = int(time.time() - state["server_start"])
        else:
            data_copy['server_uptime'] = 0
        # Add verified timestamp if user is verified
        if 'verified_at' in session:
            data_copy['verified_at'] = session['verified_at']
            data_copy['uptime_seconds'] = int(time.time() - session['verified_at'])
        else:
            data_copy['verified_at'] = None
            data_copy['uptime_seconds'] = 0
        # Sort links by post_time descending (newest first)
        data_copy['links'] = sorted(data_copy.get('links', []), key=lambda x: x.get('post_time') or x.get('created_utc', 0), reverse=True)
        approved = load_approved_users()
        data_copy['approved_users'] = approved.get("discord_ids", [])
        resp = jsonify(data_copy)
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp

@app.route("/api/admin-stats")
def api_admin_stats():
    if not _check_admin_auth():
        return jsonify({"error": "Unauthorized"}), 401
    approved = load_approved_users()
    with state_lock:
        return jsonify({
            "users": len(approved.get("discord_ids", [])),
            "alerts": len(state.get("links", []))
        })

@app.route("/api/save-account", methods=["POST"])
def save_account():
    data = request.get_json(silent=True) or {}
    domain = data.get("domain", "")
    username = data.get("username", "")
    password = data.get("password", "")
    
    if not domain or not username or not password:
        return jsonify({"ok": False, "error": "Missing fields"}), 400
    
    accounts = load_accounts()
    accounts[domain] = {
        "username": username,
        "password": password,
        "sc_total": accounts.get(domain, {}).get("sc_total", 0)
    }
    save_accounts(accounts)
    return jsonify({"ok": True})

@app.route("/api/claim", methods=["POST"])
def claim_sc():
    data = request.get_json(silent=True) or {}
    domain = data.get("domain", "")
    url = data.get("url", "")
    
    accounts = load_accounts()
    account = accounts.get(domain)
    if not account:
        return jsonify({"ok": False, "error": "Account not found"}), 404
    
    # Start automation in background thread
    def automate_claim():
        auto = CasinoAutomation(headless=False)
        if auto.start():
            if auto.login(domain, account["username"], account["password"]):
                sc_claimed = auto.claim_daily_bonus(domain)
                with state_lock:
                    state["claimed"] += 1
                    state["sc_total"] = round(state["sc_total"] + sc_claimed, 2)
                    # Update account SC total
                    accounts = load_accounts()
                    accounts[domain]["sc_total"] = round(accounts[domain].get("sc_total", 0) + sc_claimed, 2)
                    save_accounts(accounts)
            auto.close()
    
    t = threading.Thread(target=automate_claim, daemon=True)
    t.start()
    
    return jsonify({"ok": True, "message": "Claim started"})

@app.route("/api/kick-alert", methods=["POST"])
def kick_alert():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "")
    title = data.get("title", "")
    
    # Add to links if not already present
    with state_lock:
        # Check if URL already exists
        if not any(l.get("url") == url for l in state["links"]):
            import urllib.parse
            parsed = urllib.parse.urlparse(url)
            domain = parsed.netloc.replace("www.", "")
            
            state["links"].append({
                "title": title,
                "url": url,
                "author": "Kick Streamer",
                "subreddit": "kick.com",
                "post_time": time.time(),
                "source": "kick"
            })
            state["found"] = len(state["links"])
            
            # Trigger automation if account exists
            accounts = load_accounts()
            if domain in accounts:
                trigger_automation(url, title)
    
    return jsonify({"ok": True})

@app.route("/api/add-site", methods=["POST"])
def add_site():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "")
    domain = data.get("domain", "")
    url = data.get("url", "")
    sc_per_day = data.get("sc_per_day", 1)
    has_spins = data.get("has_spins", True)
    
    if not name or not domain or not url:
        return jsonify({"ok": False, "error": "Missing fields"}), 400
    
    sites = load_sites()
    # Check if site already exists
    if any(s.get("domain") == domain for s in sites):
        return jsonify({"ok": False, "error": "Site already exists"}), 400
    
    sites.append({
        "name": name,
        "domain": domain,
        "url": url,
        "sc_per_day": sc_per_day,
        "has_spins": has_spins
    })
    save_sites(sites)
    return jsonify({"ok": True})

@app.route("/admin-login", methods=["POST"])
def admin_login():
    data = request.get_json(silent=True) or {}
    method = data.get("method")
    
    if method == "discord":
        discord_id = data.get("id", "").strip()
        admin = load_admin_users()
        if discord_id in admin.get("admins", []) or discord_id == "953177450391683082":
            session['admin_id'] = discord_id
            return jsonify({"ok": True})
    
    elif method == "email":
        email = data.get("email", "").lower()
        password = data.get("password", "")
        admin = load_admin_users()
        if admin.get("emails", {}).get(email) == hashlib.sha256(password.encode()).hexdigest():
            session['admin_email'] = email
            return jsonify({"ok": True})
    
    elif method == "key":
        key = data.get("key", "").strip()
        if key == ADMIN_KEY:
            session['admin_id'] = "key_user"
            return jsonify({"ok": True})
    
    return jsonify({"ok": False}), 401

@app.route("/admin")
def admin_panel():
    if not session.get('admin_id') and not session.get('admin_email'):
        return ADMIN_LOGIN_HTML
    return ADMIN_PANEL_HTML

@app.route("/add-user", methods=["POST"])
def add_user():
    if not session.get('admin_id') and not session.get('admin_email'):
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json(silent=True) or {}
    discord_id = data.get("discord_id", "").strip()
    
    if discord_id and discord_id.isdigit() and len(discord_id) >= 17:
        approved = load_approved_users()
        if discord_id not in approved["discord_ids"]:
            approved["discord_ids"].append(discord_id)
            save_approved_users(approved)
        return jsonify({"ok": True})
    
    return jsonify({"error": "Invalid ID"}), 400

# ================== BROWSER AUTOMATION ==================
class CasinoAutomation:
    def __init__(self, headless=None):
        self.options = None
        self.driver = None
        # Use HEADLESS_MODE from config if headless not specified
        if headless is None:
            headless = HEADLESS_MODE
        try:
            from selenium.webdriver.chrome.options import Options
            self.options = Options()
            if headless:
                self.options.add_argument('--headless=new')
            self.options.add_argument('--no-sandbox')
            self.options.add_argument('--disable-dev-shm-usage')
        except:
            pass

    def load_site_xpaths(self, domain):
        """Load XPaths from site_xpaths.json"""
        xpaths_file = SCRIPT_DIR / "site_xpaths.json"
        if xpaths_file.exists():
            with open(xpaths_file, 'r') as f:
                all_xpaths = json.load(f)
                return all_xpaths.get(domain, all_xpaths.get("DEFAULT", {}))
        return {}

    def get_xpath(self, domain, key):
        """Get XPath for domain with generic fallback"""
        site_xpaths = self.load_site_xpaths(domain)
        if site_xpaths and key in site_xpaths.get("xpaths", {}):
            return site_xpaths["xpaths"][key]
        return GENERIC_XPATHS.get(key, "")

    def get_xpath(self, domain, key):
        """Get XPath for domain with generic fallback"""
        site_xpaths = self.load_site_xpaths(domain)
        if site_xpaths and key in site_xpaths.get("xpaths", {}):
            return site_xpaths["xpaths"][key]
        return GENERIC_XPATHS.get(key, "")

    def get_wait_time(self, domain, key):
        """Get wait time for domain with default"""
        site_xpaths = self.load_site_xpaths(domain)
        return site_xpaths.get("wait_times", {}).get(key, 3)
    
    def start(self):
        try:
            from selenium.webdriver.chrome.service import Service
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=self.options)
            return True
        except Exception as e:
            print(f"Failed to start browser: {e}")
            return False
    
    def login(self, domain, username, password, login_method="email"):
        if not self.driver:
            return False
        try:
            self.driver.get(f"https://{domain}")
            time.sleep(self.get_wait_time(domain, "page_load"))
            
            from selenium.webdriver.common.by import By
            from selenium.webdriver.common.keys import Keys
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            # Accept cookies if present
            try:
                cookie_btn = self.driver.find_element(By.XPATH, self.get_xpath(domain, "cookie_accept"))
                cookie_btn.click()
                time.sleep(1)
            except:
                pass
            
            # Click login button
            login_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, self.get_xpath(domain, "login_button")))
            )
            login_btn.click()
            time.sleep(1)
            
            # SSO login paths
            if login_method in ("google", "apple"):
                try:
                    provider = login_method.capitalize()
                    sso_btn = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, f"//button[contains(@aria-label,'{provider}') or contains(text(),'{provider}')] | //div[contains(@aria-label,'{provider}')]"))
                    )
                    sso_btn.click()
                    time.sleep(3)
                    if login_method == "google":
                        user_field = WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.XPATH, "//input[@type='email']"))
                        )
                        user_field.send_keys(username)
                        user_field.send_keys(Keys.RETURN)
                        time.sleep(2)
                        pass_field = WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.XPATH, "//input[@type='password']"))
                        )
                        pass_field.send_keys(password)
                        pass_field.send_keys(Keys.RETURN)
                    else:
                        user_field = WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.XPATH, "//input[@type='text' or @name='accountName']"))
                        )
                        user_field.send_keys(username)
                        time.sleep(1)
                        pass_field = self.driver.find_element(By.XPATH, "//input[@type='password' or @name='password']")
                        pass_field.send_keys(password)
                        pass_field.send_keys(Keys.RETURN)
                    time.sleep(self.get_wait_time(domain, "login"))
                    return True
                except Exception as sso_e:
                    print(f"[SSO] {login_method} auto-fill failed for {domain}: {sso_e}")
                    return False
            
            # Standard email/password login
            user_field = self.driver.find_element(By.XPATH, self.get_xpath(domain, "email_field"))
            pass_field = self.driver.find_element(By.XPATH, self.get_xpath(domain, "password_field"))

            user_field.send_keys(username)
            pass_field.send_keys(password)

            # Submit
            submit = self.driver.find_element(By.XPATH, self.get_xpath(domain, "submit_button"))
            submit.click()
            time.sleep(self.get_wait_time(domain, "login"))

            # Check for OTP/2FA fields after login
            self._handle_otp(domain)
            return True
        except Exception as e:
            print(f"Login failed for {domain}: {e}")
            return False

    def _handle_otp(self, domain):
        """Detect and handle OTP/2FA fields after login.
        For manual mode: pauses browser, logs message, waits up to 120s
        for user to enter the code, then detects completion."""
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            otp_xpath = self.get_xpath(domain, "otp_field")
            if not otp_xpath:
                return
            otp_fields = self.driver.find_elements(By.XPATH, otp_xpath)
            if not otp_fields:
                return
            # OTP detected — switch to visible browser for manual entry
            self.driver.execute_script("document.title = 'OTP REQUIRED - Enter code';")
            print(f"[OTP] 2FA required for {domain}. Enter code in the browser. Waiting up to 120s...")
            # Poll until OTP fields disappear (user entered code) or URL changes away from auth
            from urllib.parse import urlparse
            start = time.time()
            while time.time() - start < 120:
                try:
                    current = self.driver.current_url
                    if "login" not in current.lower() and "auth" not in current.lower():
                        print(f"[OTP] Verification detected for {domain}")
                        return
                    remaining = self.driver.find_elements(By.XPATH, otp_xpath)
                    otp_vals = [f.get_attribute("value") for f in remaining if f.get_attribute("value")]
                    if otp_vals and all(v for v in otp_vals):
                        # Try clicking verify button
                        try:
                            vb = self.driver.find_element(By.XPATH, self.get_xpath(domain, "otp_verify_button"))
                            vb.click()
                            time.sleep(2)
                        except:
                            pass
                        remaining2 = self.driver.find_elements(By.XPATH, otp_xpath)
                        if not remaining2 or not any(f.get_attribute("value") for f in remaining2):
                            print(f"[OTP] Code accepted for {domain}")
                            return
                except:
                    pass
                time.sleep(2)
            print(f"[OTP] Timeout waiting for OTP entry on {domain}")
        except Exception as e:
            print(f"[OTP] Error: {e}")
    
    def claim_daily_bonus(self, domain):
        if not self.driver:
            return 0
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            # Navigate to wallet/bonus page
            wallet_url = self.get_xpath(domain, "wallet_url")
            if wallet_url.startswith("/"):
                self.driver.get(f"https://{domain}{wallet_url}")
            else:
                self.driver.get(f"https://{domain}/{wallet_url}")
            time.sleep(self.get_wait_time(domain, "page_load"))
            
            # Look for daily bonus button
            bonus_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, self.get_xpath(domain, "daily_claim_button")))
            )
            bonus_btn.click()
            time.sleep(self.get_wait_time(domain, "claim"))
            return 1  # 1 SC claimed
        except Exception as e:
            print(f"Claim failed for {domain}: {e}")
            return 0
    
    def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None

def capture_oauth_session(domain, login_method="google", timeout_seconds=180):
    """Open a browser to the casino's login page for Google/Apple OAuth.
    Waits for the user to complete login, then captures cookies for future automated use.
    Returns dict with cookies and session data, or None if timeout/cancelled."""
    try:
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        opts = Options()
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage')
        opts.add_argument(f'--window-size=1200,900')
        opts.add_argument('--disable-blink-features=AutomationControlled')

        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service as ChromeService
        from webdriver_manager.chrome import ChromeDriverManager
        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=opts)

        # Navigate to the casino's domain
        sites = load_sites()
        site = next((s for s in sites if s["domain"] == domain or domain in s["domain"]), None)
        if site and site.get("url"):
            login_url = site["url"]
        else:
            login_url = f"https://{domain}"

        driver.get(login_url)
        import threading as _thr
        result = {"cookies": None, "success": False}
        done_event = _thr.Event()

        # Poll for login completion — check URL changes and cookie presence
        start = time.time()
        initial_url = driver.current_url
        while time.time() - start < timeout_seconds:
            try:
                current = driver.current_url
                # If URL changed significantly from login page, assume logged in
                if current != initial_url and "login" not in current.lower() and "auth" not in current.lower():
                    result["cookies"] = driver.get_cookies()
                    result["success"] = True
                    break
                # Check for common auth cookies
                auth_cookies = [c for c in driver.get_cookies() if any(k in c.get("name","").lower() for k in ["token","session","auth","sid","connect"])]
                if len(auth_cookies) >= 2:
                    result["cookies"] = driver.get_cookies()
                    result["success"] = True
                    break
            except:
                pass
            time.sleep(1)

        driver.quit()
        return result
    except Exception as e:
        print(f"[OAuth] Error: {e}")
        return {"cookies": None, "success": False, "error": str(e)}

def discover_sso_selectors(domain, driver):
    """After page load, scan for Google/Apple SSO buttons and return discovered selectors."""
    result = {"sso_google": "", "sso_apple": ""}
    try:
        from selenium.webdriver.common.by import By
        # Try common Google SSO button patterns
        google_patterns = [
            "//button[contains(@aria-label,'Google')]",
            "//button[contains(text(),'Google')]",
            "//div[contains(@aria-label,'Google')]",
            "//a[contains(@title,'Google')]",
            "//button[contains(@class,'google')]",
            "//div[contains(@class,'google')]",
            "//img[contains(@alt,'Google')]/..",
            "//*[contains(@class,'social')]//*[contains(text(),'Google')]",
        ]
        for pat in google_patterns:
            els = driver.find_elements(By.XPATH, pat)
            if els:
                result["sso_google"] = pat
                break
        apple_patterns = [
            "//button[contains(@aria-label,'Apple')]",
            "//button[contains(text(),'Apple')]",
            "//div[contains(@aria-label,'Apple')]",
            "//a[contains(@title,'Apple')]",
            "//button[contains(@class,'apple')]",
            "//div[contains(@class,'apple')]",
            "//img[contains(@alt,'Apple')]/..",
            "//*[contains(@class,'social')]//*[contains(text(),'Apple')]",
        ]
        for pat in apple_patterns:
            els = driver.find_elements(By.XPATH, pat)
            if els:
                result["sso_apple"] = pat
                break
    except:
        pass
    return result

def auto_sso_login(domain, login_method, username, password, timeout_seconds=180):
    """Open the casino's login page in a visible browser, detect the SSO button,
    auto-fill the Google/Apple OAuth form with provided credentials, wait for
    redirect back to casino, capture cookies, and save discovered selectors.
    Returns dict with success, cookies, and discovered XPaths."""
    try:
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        opts = Options()
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage')
        opts.add_argument('--window-size=1200,900')
        opts.add_argument('--disable-blink-features=AutomationControlled')

        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service as ChromeService
        from webdriver_manager.chrome import ChromeDriverManager
        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=opts)

        # Navigate to casino
        sites = load_sites()
        site = next((s for s in sites if s["domain"] == domain or domain in s["domain"]), None)
        login_url = site["url"] if site and site.get("url") else f"https://{domain}"
        driver.get(login_url)
        time.sleep(3)

        # Accept cookies
        try:
            cb = driver.find_element(By.XPATH, GENERIC_XPATHS["cookie_accept"])
            cb.click(); time.sleep(1)
        except: pass

        # Discover SSO selectors
        selectors = discover_sso_selectors(domain, driver)
        sso_xpath = selectors.get(f"sso_{login_method}", "")
        if not sso_xpath:
            # Try generic login button detection
            try:
                login_btn = driver.find_element(By.XPATH, GENERIC_XPATHS["login_button"])
                login_btn.click(); time.sleep(2)
                selectors = discover_sso_selectors(domain, driver)
                sso_xpath = selectors.get(f"sso_{login_method}", "")
            except: pass

        if not sso_xpath:
            driver.quit()
            return {"success": False, "cookies": None, "error": f"No {login_method} SSO button found"}

        # Click SSO button
        sso_btn = driver.find_element(By.XPATH, sso_xpath)
        sso_btn.click()
        time.sleep(3)

        # Handle OAuth popup/redirect — auto-fill the Google/Apple form
        try:
            if login_method == "google":
                # Google OAuth — email field
                email_field = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//input[@type='email']"))
                )
                email_field.send_keys(username)
                email_field.send_keys(Keys.RETURN)
                time.sleep(2)
                # Password field
                pass_field = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//input[@type='password']"))
                )
                pass_field.send_keys(password)
                pass_field.send_keys(Keys.RETURN)
            else:
                # Apple OAuth
                user_field = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//input[@type='text' or @name='accountName']"))
                )
                user_field.send_keys(username)
                time.sleep(1)
                pass_field = driver.find_element(By.XPATH, "//input[@type='password' or @name='password']")
                pass_field.send_keys(password)
                pass_field.send_keys(Keys.RETURN)
        except Exception as fill_err:
            print(f"[SSO] Auto-fill failed: {fill_err}")

        # Wait for login completion
        start = time.time()
        initial_url = driver.current_url
        result = {"cookies": None, "success": False, "selectors": selectors}
        while time.time() - start < timeout_seconds:
            try:
                current = driver.current_url
                if current != initial_url and "login" not in current.lower() and "auth" not in current.lower():
                    result["cookies"] = driver.get_cookies()
                    result["success"] = True
                    break
                auth_cookies = [c for c in driver.get_cookies() if any(k in c.get("name","").lower() for k in ["token","session","auth","sid","connect"])]
                if len(auth_cookies) >= 2:
                    result["cookies"] = driver.get_cookies()
                    result["success"] = True
                    break
            except: pass
            time.sleep(1)

        # Save discovered selectors to site_xpaths.json
        if result["success"]:
            xpaths_file = SCRIPT_DIR / "site_xpaths.json"
            if xpaths_file.exists():
                with open(xpaths_file) as f: all_xp = json.load(f)
            else:
                all_xp = {"DEFAULT": {"xpaths": dict(GENERIC_XPATHS), "wait_times": {"page_load":3,"login":4,"claim":3}}}
            if domain not in all_xp:
                all_xp[domain] = {"xpaths": {}, "wait_times": {"page_load":3,"login":4,"claim":3}}
            all_xp[domain]["xpaths"][f"sso_{login_method}"] = sso_xpath
            xp_key = f"sso_{login_method}_field"
            if login_method == "google":
                all_xp[domain]["xpaths"]["sso_email_field"] = "//input[@type='email']"
                all_xp[domain]["xpaths"]["sso_password_field"] = "//input[@type='password']"
            else:
                all_xp[domain]["xpaths"]["sso_user_field"] = "//input[@type='text' or @name='accountName']"
                all_xp[domain]["xpaths"]["sso_password_field"] = "//input[@type='password' or @name='password']"
            with open(xpaths_file, 'w') as f: json.dump(all_xp, f, indent=2)

        driver.quit()
        return result
    except Exception as e:
        print(f"[SSO] Error: {e}")
        return {"success": False, "cookies": None, "error": str(e)}

# ── Claims Casino static route ──
@app.route("/casino/")
@app.route("/casino/<path:filename>")
def serve_claims_casino(filename="index.html"):
    return send_from_directory(str(CLAIMS_CASINO_DIR), filename)

# ── Embed dashboard (no auth) for inline display ──
APPLICANTS_FILE = SCRIPT_DIR / "applicants.json"

STOCK_FILE = SCRIPT_DIR / "stock.json"
INVOICES_FILE = SCRIPT_DIR / "invoices.json"

def load_stock():
    if not STOCK_FILE.exists():
        return {"count": 0}
    with open(STOCK_FILE) as f:
        return json.load(f)

def save_stock(data):
    with open(STOCK_FILE, "w") as f:
        json.dump(data, f, indent=2)

def load_invoices():
    if not INVOICES_FILE.exists():
        return []
    with open(INVOICES_FILE) as f:
        return json.load(f)

def save_invoices(data):
    with open(INVOICES_FILE, "w") as f:
        json.dump(data, f, indent=2)

def load_applicants():
    if not APPLICANTS_FILE.exists():
        return []
    with open(APPLICANTS_FILE) as f:
        return json.load(f)

def save_applicants(data):
    with open(APPLICANTS_FILE, "w") as f:
        json.dump(data, f, indent=2)

@app.route("/api/track-page", methods=["POST"])
def api_track_page():
    data = request.get_json(silent=True) or {}
    did = data.get("discord_id", "").strip()
    p = data.get("page", "")
    ts = data.get("timestamp", int(time.time() * 1000))
    if did:
        with tracked_lock:
            tracked_users[did] = {"page": p, "last_seen": ts, "name": USERS.get(did, {}).get("name", did)}
    return jsonify({"ok": True})

@app.route("/api/admin-monitor")
def api_admin_monitor():
    if not _check_admin_auth():
        return jsonify({"error": "Unauthorized"}), 401
    now = int(time.time() * 1000)
    with tracked_lock:
        active = {k: v for k, v in tracked_users.items() if now - v.get("last_seen", 0) < 30000}
    return jsonify(active)

@app.route("/api/stock")
def api_stock():
    stock = load_stock()
    return jsonify(stock)

@app.route("/api/admin-stock", methods=["POST"])
def api_admin_stock():
    if not _check_admin_auth():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    count = data.get("count", 0)
    if not isinstance(count, int) or count < 0:
        return jsonify({"error": "Invalid count"}), 400
    stock = {"count": count, "updated": time.time()}
    save_stock(stock)
    return jsonify({"ok": True, "count": count})

@app.route("/api/cart-purchase", methods=["POST"])
def api_cart_purchase():
    data = request.get_json(silent=True) or {}
    discord_id = data.get("discord_id", "")
    currency = data.get("currency", "BTC")
    amount = data.get("amount", 299.0)
    address = data.get("address", "")
    private_key = data.get("private_key", "")
    invoice_id = data.get("invoice_id", "")

    stock = load_stock()
    if stock.get("count", 0) < 1:
        return jsonify({"ok": False, "error": "Out of stock"}), 400

    stock["count"] -= 1
    save_stock(stock)

    invoices = load_invoices()
    invoices.append({
        "id": invoice_id,
        "discord_id": discord_id,
        "currency": currency,
        "amount": amount,
        "address": address,
        "private_key": private_key,
        "status": "pending",
        "created": time.time()
    })
    save_invoices(invoices)

    return jsonify({"ok": True, "invoice_id": invoice_id, "remaining": stock["count"]})

@app.route("/api/admin-invoices")
def api_admin_invoices():
    if not _check_admin_auth():
        return jsonify({"error": "Unauthorized"}), 401
    invoices = load_invoices()
    return jsonify(invoices)

@app.route("/api/admin-invoice", methods=["POST"])
def api_admin_invoice():
    if not _check_admin_auth():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    invoices = load_invoices()
    invoices.append({
        "id": data.get("id", ""),
        "discord_id": data.get("discord_id", ""),
        "currency": data.get("currency", ""),
        "amount": data.get("amount", 0),
        "address": data.get("address", ""),
        "private_key": data.get("private_key", ""),
        "qr_data": data.get("qr_data", ""),
        "status": "pending",
        "created": time.time()
    })
    save_invoices(invoices)
    return jsonify({"ok": True})

@app.route("/api/admin-update-invoice", methods=["POST"])
def api_admin_update_invoice():
    if not _check_admin_auth():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    invoice_id = data.get("id", "")
    new_status = data.get("status", "")
    invoices = load_invoices()
    for inv in invoices:
        if inv.get("id") == invoice_id:
            inv["status"] = new_status
            license_key = ""
            if new_status == "paid":
                license_key = generate_license_key()
                keys = load_license_keys()
                keys[license_key] = {
                    "status": "active",
                    "tier": "premium",
                    "created": time.time(),
                    "assigned_to": inv.get("discord_id", "")
                }
                save_license_keys(keys)
            save_invoices(invoices)
            return jsonify({"ok": True, "license_key": license_key})
    return jsonify({"error": "Invoice not found"}), 404

@app.route("/api/waitlist-apply", methods=["POST"])
def api_waitlist_apply():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()
    discord = data.get("discord", "").strip()
    password = data.get("password", "")
    typ = data.get("type", "waitlist")
    username = data.get("username", discord or "").strip()
    avatar_url = data.get("avatar_url", "").strip()

    if not email:
        return jsonify({"ok": False, "error": "Email required"}), 400

    applicants = load_applicants()
    # Check if already applied
    existing = [a for a in applicants if a.get("email") == email]
    position = len(applicants) + 1

    applicants.append({
        "email": email,
        "discord": discord,
        "username": username,
        "avatar_url": avatar_url,
        "password": password if password else "",
        "status": "pending",
        "type": typ,
        "position": position,
        "timestamp": time.time()
    })
    try:
        save_applicants(applicants)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Save failed: {e}"}), 500

    return jsonify({"ok": True, "position": position})

@app.route("/api/check-approval")
def api_check_approval():
    email = request.args.get("email", "")
    discord = request.args.get("discord", "")
    license_id = request.args.get("license_id", "")

    applicants = load_applicants()
    approved_users = load_approved_users()

    # Check by email or discord
    for a in applicants:
        match = (email and a.get("email") == email) or (discord and a.get("discord") == discord)
        if match and a.get("status") == "approved":
            lid = a.get("license_id", license_id or discord[:8])
            return jsonify({"approved": True, "license_id": lid})

    # Also check approved users list
    if discord and discord in approved_users.get("discord_ids", []):
        return jsonify({"approved": True, "license_id": discord[:8]})

    return jsonify({"approved": False, "license_id": None})

@app.route("/api/admin-applicants")
def api_admin_applicants():
    if not _check_admin_auth():
        return jsonify({"error": "Unauthorized"}), 401
    applicants = load_applicants()
    return jsonify(applicants)

@app.route("/api/admin-applicant-action", methods=["POST"])
def api_admin_applicant_action():
    if not _check_admin_auth():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    email = data.get("email", "")
    action = data.get("action", "")  # approve, deny, interview, save

    applicants = load_applicants()
    for a in applicants:
        if a.get("email") == email:
            a["status"] = action
            if action == "approved":
                a["license_id"] = data.get("license_id", f"LIC-{len(applicants)}")
            break

    save_applicants(applicants)
    return jsonify({"ok": True})

@app.route("/api/embed-dashboard")
def embed_dashboard():
    html = MAIN_DASHBOARD_HTML
    base = f"http://localhost:{FLASK_PORT}"
    html = html.replace('"/api/', f'"{base}/api/')
    html = html.replace("'/api/", f"'{base}/api/")
    resp = make_response(html)
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp

# ================== MAIN ==================
if __name__ == "__main__":
    # Pre-approve known users
    approved = load_approved_users()
    KNOWN_IDS = ["695697021868310669", "186105992252096512", "222898514789662721", "741378521460637773", "1389284552442253352"]
    for did in KNOWN_IDS:
        if did not in approved["discord_ids"]:
            approved["discord_ids"].append(did)
    save_approved_users(approved)

    # Ensure membership directory exists
    MEMBERSHIP_DIR.mkdir(exist_ok=True)
    if not (MEMBERSHIP_DIR / "index.html").exists():
        with open(MEMBERSHIP_DIR / "index.html", "w") as f:
            f.write("")  # Create placeholder
    
    # Start monitor thread
    monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    monitor_thread.start()
    
    # Start daily freebies updater
    daily_freebies_thread = threading.Thread(target=daily_freebies_loop, daemon=True)
    daily_freebies_thread.start()
    
    # Start claim scheduler
    claim_thread = threading.Thread(target=claim_scheduler_loop, daemon=True)
    claim_thread.start()
    
    # Flood Discord with last 24 hours of Free SC/Spin posts
    print("=" * 50)
    print("SWEEPSTAKES MONITOR SYSTEM")
    print("=" * 50)
    print(f"Server:     http://localhost:{FLASK_PORT}")
    print(f"Membership: http://localhost:{FLASK_PORT}/membership")
    print(f"Casino:     http://localhost:{FLASK_PORT}/casino/")
    print(f"Admin:      http://localhost:{FLASK_PORT}/admin")
    print(f"Discord: Flooding last 24 hours of posts...")
    print("=" * 50)
    
    # Run flood in background thread
    flood_thread = threading.Thread(target=flood_discord_last_24h, daemon=True)
    flood_thread.start()
    
    app.run(host="0.0.0.0", port=FLASK_PORT, debug=False)
