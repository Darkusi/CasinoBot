#!/usr/bin/env python3
"""
Claims Casino - Activation Server
Standalone Flask server for online license activation with HWID binding.
Deployable to Render, Railway, PythonAnywhere, or any VPS.

Usage:
    python activation_server.py          # Run on port 5002
    python activation_server.py --port 8080

Endpoints:
    POST /api/activate   - Activate a license key with HWID
    POST /api/validate   - Validate an active license (periodic check)
    POST /api/revoke     - Revoke a license (admin)
    GET  /api/status     - Server status

License file: licenses.json (auto-created)
"""

import json
import os
import sys
import time
import hashlib
import uuid
from pathlib import Path
from flask import Flask, jsonify, request

app = Flask(__name__)

DATA_DIR = Path(__file__).parent
LICENSES_FILE = DATA_DIR / "licenses.json"

# Default admin key for managing licenses
ADMIN_KEY = os.environ.get("ACTIVATION_ADMIN_KEY", "CHANGE-ME-PLEASE")


def load_licenses():
    if LICENSES_FILE.exists():
        with open(LICENSES_FILE) as f:
            return json.load(f)
    return {}


def save_licenses(data):
    with open(LICENSES_FILE, "w") as f:
        json.dump(data, f, indent=2)


def normalize_key(raw):
    return raw.upper().replace("-", "").strip()


@app.route("/api/activate", methods=["POST"])
def api_activate():
    data = request.get_json(silent=True) or {}
    raw_key = data.get("key", "").strip()
    hwid = data.get("hwid", "").strip()

    if not raw_key or not hwid:
        return jsonify({"valid": False, "reason": "Missing key or hardware ID."}), 400

    normalized = normalize_key(raw_key)
    licenses = load_licenses()

    for stored_key, info in licenses.items():
        if normalize_key(stored_key) == normalized:
            if info.get("status") != "active":
                return jsonify({"valid": False, "reason": "License revoked or expired."})

            existing_hwid = info.get("hwid", "")
            if existing_hwid and existing_hwid != hwid:
                return jsonify({"valid": False, "reason": "License already bound to another machine."})

            info["hwid"] = hwid
            info["last_activation"] = time.time()
            info["activated_at"] = info.get("activated_at", time.time())
            save_licenses(licenses)

            return jsonify({
                "valid": True,
                "tier": info.get("tier", "premium"),
                "key": stored_key,
                "message": "Activation successful."
            })

    return jsonify({"valid": False, "reason": "Invalid license key."})


@app.route("/api/validate", methods=["POST"])
def api_validate():
    data = request.get_json(silent=True) or {}
    raw_key = data.get("key", "").strip()
    hwid = data.get("hwid", "").strip()

    if not raw_key or not hwid:
        return jsonify({"valid": False}), 400

    normalized = normalize_key(raw_key)
    licenses = load_licenses()

    for stored_key, info in licenses.items():
        if normalize_key(stored_key) == normalized:
            if info.get("status") != "active":
                return jsonify({"valid": False})
            if info.get("hwid", "") and info["hwid"] != hwid:
                return jsonify({"valid": False})
            return jsonify({"valid": True, "tier": info.get("tier", "premium")})

    return jsonify({"valid": False})


@app.route("/api/revoke", methods=["POST"])
def api_revoke():
    data = request.get_json(silent=True) or {}
    admin_key = data.get("admin_key", "")

    if admin_key != ADMIN_KEY:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    raw_key = data.get("key", "").strip()
    if not raw_key:
        return jsonify({"ok": False, "error": "Missing key"}), 400

    normalized = normalize_key(raw_key)
    licenses = load_licenses()

    for stored_key in list(licenses.keys()):
        if normalize_key(stored_key) == normalized:
            licenses[stored_key]["status"] = "revoked"
            licenses[stored_key]["revoked_at"] = time.time()
            save_licenses(licenses)
            return jsonify({"ok": True, "message": "License revoked."})

    return jsonify({"ok": False, "error": "Key not found."}), 404


@app.route("/api/add-key", methods=["POST"])
def api_add_key():
    data = request.get_json(silent=True) or {}
    admin_key = data.get("admin_key", "")

    if admin_key != ADMIN_KEY:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    new_key = data.get("key", "").strip()
    tier = data.get("tier", "premium")

    if not new_key:
        return jsonify({"ok": False, "error": "Missing key"}), 400

    licenses = load_licenses()
    if new_key in licenses:
        return jsonify({"ok": False, "error": "Key already exists."})

    licenses[new_key] = {
        "status": "active",
        "tier": tier,
        "hwid": "",
        "created": time.time(),
        "activated_at": None,
        "last_activation": None
    }
    save_licenses(licenses)

    return jsonify({"ok": True, "key": new_key, "tier": tier})


@app.route("/api/list-keys", methods=["POST"])
def api_list_keys():
    data = request.get_json(silent=True) or {}
    admin_key = data.get("admin_key", "")

    if admin_key != ADMIN_KEY:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    licenses = load_licenses()
    result = {}
    for k, v in licenses.items():
        result[k] = {
            "status": v.get("status"),
            "tier": v.get("tier"),
            "hwid": v.get("hwid", "")[:8] + "..." if v.get("hwid") else "",
            "activated_at": v.get("activated_at"),
            "last_activation": v.get("last_activation")
        }
    return jsonify(result)


@app.route("/api/status")
def api_status():
    licenses = load_licenses()
    total = len(licenses)
    active = sum(1 for v in licenses.values() if v.get("status") == "active")
    bound = sum(1 for v in licenses.values() if v.get("hwid"))
    return jsonify({
        "ok": True,
        "server": "Claims Casino Activation Server",
        "licenses_total": total,
        "licenses_active": active,
        "licenses_bound": bound
    })


if __name__ == "__main__":
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 5002
    print(f"[Claims Casino] Activation server starting on port {port}")
    print(f"[Claims Casino] Admin key: {ADMIN_KEY[:8]}... (set ACTIVATION_ADMIN_KEY env var)")
    print(f"[Claims Casino] Licenses file: {LICENSES_FILE}")
    app.run(host="0.0.0.0", port=port, debug=False)
