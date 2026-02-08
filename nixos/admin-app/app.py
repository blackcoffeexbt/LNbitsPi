#!/usr/bin/env python3
"""LNbitsBox Admin Dashboard — system monitoring and service management"""

import os
import sys
import time
try:
    import crypt
except ModuleNotFoundError:
    crypt = None  # Removed in Python 3.13; only needed on NixOS Pi
import shutil
import subprocess
import threading
from collections import deque
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session, jsonify
)

app = Flask(__name__, static_url_path="/box/static")
app.secret_key = os.urandom(24)

# Configuration
DEV_MODE = os.environ.get("DEV_MODE", "false") == "true"
SSH_USER = "lnbitsadmin"
SPARK_URL = os.environ.get("SPARK_URL", "http://127.0.0.1:8765")
LNBITS_URL = os.environ.get("LNBITS_URL", "http://127.0.0.1:5000")
ALLOWED_SERVICES = ["lnbits", "spark-sidecar"]

# Stats history — 2 hours at 30s intervals = 240 data points
STATS_INTERVAL = 30
STATS_HISTORY_SIZE = 240
stats_history = deque(maxlen=STATS_HISTORY_SIZE)
stats_lock = threading.Lock()


# ── Authentication ──────────────────────────────────────────────────

def authenticate(username, password):
    """Verify password against /etc/shadow (requires root)"""
    if DEV_MODE:
        return True
    if crypt is None:
        return False
    try:
        with open("/etc/shadow") as f:
            for line in f:
                fields = line.strip().split(":")
                if fields[0] == username and len(fields) > 1 and fields[1]:
                    return crypt.crypt(password, fields[1]) == fields[1]
    except Exception:
        pass
    return False


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if DEV_MODE or session.get("authenticated"):
            return f(*args, **kwargs)
        return redirect(url_for("login"))
    return decorated


# ── Stats Collection ────────────────────────────────────────────────

def get_cpu_temp():
    try:
        temp = Path("/sys/class/thermal/thermal_zone0/temp").read_text().strip()
        return round(int(temp) / 1000, 1)
    except Exception:
        return None


def get_uptime():
    try:
        secs = float(Path("/proc/uptime").read_text().split()[0])
        days = int(secs // 86400)
        hours = int((secs % 86400) // 3600)
        minutes = int((secs % 3600) // 60)
        return {"seconds": secs, "formatted": f"{days}d {hours}h {minutes}m"}
    except Exception:
        return {"seconds": 0, "formatted": "unknown"}


def get_service_status(service):
    try:
        result = subprocess.run(
            ["systemctl", "is-active", f"{service}.service"],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def get_spark_balance():
    """Query Spark sidecar for wallet balance"""
    try:
        import requests
        resp = requests.post(f"{SPARK_URL}/v1/balance", timeout=5)
        if resp.ok:
            data = resp.json()
            balance_msat = data.get("balance_msat")
            if balance_msat is not None:
                return {"balance": int(balance_msat) // 1000}
            balance_sats = data.get("balance_sats")
            if balance_sats is not None:
                return {"balance": int(balance_sats)}
    except Exception:
        pass
    return None


def get_cpu_percent():
    try:
        import psutil
        return psutil.cpu_percent(interval=0)
    except Exception:
        return 0


def get_memory_info():
    try:
        import psutil
        mem = psutil.virtual_memory()
        return {
            "used": mem.used,
            "total": mem.total,
            "percent": mem.percent,
        }
    except Exception:
        return {"used": 0, "total": 0, "percent": 0}


def collect_stats():
    """Collect all system stats"""
    disk = shutil.disk_usage("/")
    return {
        "timestamp": datetime.now().isoformat(),
        "cpu_percent": get_cpu_percent(),
        "ram": get_memory_info(),
        "cpu_temp": get_cpu_temp(),
        "disk": {
            "used": disk.used,
            "total": disk.total,
            "percent": round(disk.used / disk.total * 100, 1) if disk.total else 0,
        },
        "uptime": get_uptime(),
        "services": {
            svc: get_service_status(svc) for svc in ALLOWED_SERVICES
        },
        "spark_balance": get_spark_balance(),
    }


def stats_collector():
    """Background thread collecting stats periodically"""
    # Initial collection with small delay for psutil baseline
    try:
        import psutil
        psutil.cpu_percent()
    except Exception:
        pass
    time.sleep(1)

    while True:
        try:
            stats = collect_stats()
            with stats_lock:
                stats_history.append(stats)
        except Exception:
            pass
        time.sleep(STATS_INTERVAL)


# Start background collector
threading.Thread(target=stats_collector, daemon=True).start()


# ── Routes ──────────────────────────────────────────────────────────

@app.route("/box/login", methods=["GET", "POST"])
def login():
    if session.get("authenticated"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        password = request.form.get("password", "")

        if authenticate(SSH_USER, password):
            session["authenticated"] = True
            return redirect(url_for("dashboard"))

        flash("Invalid password", "error")

    return render_template("login.html")


@app.route("/box/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/box/")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/box/api/stats")
@login_required
def api_stats():
    current = collect_stats()
    with stats_lock:
        history = list(stats_history)
    return jsonify({
        "current": current,
        "history": {
            "timestamps": [s["timestamp"] for s in history],
            "cpu": [s["cpu_percent"] for s in history],
            "ram": [s["ram"]["percent"] for s in history],
            "temp": [s["cpu_temp"] for s in history],
        }
    })


@app.route("/box/api/shutdown", methods=["POST"])
@login_required
def api_shutdown():
    if DEV_MODE:
        return jsonify({"status": "ok", "message": "DEV MODE: would shutdown"})
    subprocess.Popen(["systemctl", "poweroff"])
    return jsonify({"status": "ok", "message": "Shutting down..."})


@app.route("/box/api/reboot", methods=["POST"])
@login_required
def api_reboot():
    if DEV_MODE:
        return jsonify({"status": "ok", "message": "DEV MODE: would reboot"})
    subprocess.Popen(["systemctl", "reboot"])
    return jsonify({"status": "ok", "message": "Rebooting..."})


@app.route("/box/api/restart/<service>", methods=["POST"])
@login_required
def api_restart_service(service):
    if service not in ALLOWED_SERVICES:
        return jsonify({"status": "error", "message": "Invalid service"}), 400

    if DEV_MODE:
        return jsonify({"status": "ok", "message": f"DEV MODE: would restart {service}"})

    try:
        subprocess.run(
            ["systemctl", "restart", f"{service}.service"],
            check=True, capture_output=True, timeout=30
        )
        return jsonify({"status": "ok", "message": f"{service} restarted"})
    except subprocess.CalledProcessError as e:
        return jsonify({"status": "error", "message": e.stderr.decode()}), 500


# ── WiFi ───────────────────────────────────────────────────────────

def parse_nmcli_line(line):
    """Parse nmcli terse output line, handling escaped colons in SSIDs"""
    fields = []
    current = []
    i = 0
    while i < len(line):
        if line[i] == '\\' and i + 1 < len(line):
            current.append(line[i + 1])
            i += 2
        elif line[i] == ':':
            fields.append(''.join(current))
            current = []
            i += 1
        else:
            current.append(line[i])
            i += 1
    fields.append(''.join(current))
    return fields


@app.route("/box/api/wifi/scan")
@login_required
def api_wifi_scan():
    if DEV_MODE:
        return jsonify({"networks": [
            {"ssid": "MyNetwork", "signal": 85, "security": "WPA2", "connected": True},
            {"ssid": "Neighbor", "signal": 60, "security": "WPA2", "connected": False},
            {"ssid": "OpenWifi", "signal": 40, "security": "", "connected": False},
        ]})
    try:
        subprocess.run(["nmcli", "device", "wifi", "rescan"],
                       capture_output=True, timeout=10)
        time.sleep(2)
        result = subprocess.run(
            ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY,IN-USE", "device", "wifi", "list"],
            capture_output=True, text=True, timeout=10
        )
        networks = []
        seen = set()
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = parse_nmcli_line(line)
            if len(parts) >= 4:
                ssid = parts[0]
                if not ssid or ssid in seen:
                    continue
                seen.add(ssid)
                networks.append({
                    "ssid": ssid,
                    "signal": int(parts[1]) if parts[1].isdigit() else 0,
                    "security": parts[2],
                    "connected": parts[3] == "*",
                })
        networks.sort(key=lambda n: n["signal"], reverse=True)
        return jsonify({"networks": networks})
    except Exception as e:
        return jsonify({"networks": [], "error": str(e)})


@app.route("/box/api/wifi/connect", methods=["POST"])
@login_required
def api_wifi_connect():
    data = request.get_json()
    ssid = data.get("ssid", "")
    password = data.get("password", "")

    if not ssid:
        return jsonify({"status": "error", "message": "SSID required"}), 400

    if DEV_MODE:
        return jsonify({"status": "ok", "message": f"DEV MODE: would connect to {ssid}"})

    try:
        cmd = ["nmcli", "device", "wifi", "connect", ssid]
        if password:
            cmd += ["password", password]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return jsonify({"status": "ok", "message": f"Connected to {ssid}"})
        else:
            msg = result.stderr.strip() or result.stdout.strip() or "Connection failed"
            return jsonify({"status": "error", "message": msg}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/box/api/wifi/status")
@login_required
def api_wifi_status():
    if DEV_MODE:
        return jsonify({"connected": True, "ssid": "MyNetwork", "ip": "192.168.1.100"})
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.strip().split("\n"):
            parts = parse_nmcli_line(line)
            if len(parts) >= 4 and parts[1] == "wifi" and parts[2] == "connected":
                ip_result = subprocess.run(
                    ["nmcli", "-t", "-f", "IP4.ADDRESS", "device", "show", parts[0]],
                    capture_output=True, text=True, timeout=5
                )
                ip = ""
                for ip_line in ip_result.stdout.strip().split("\n"):
                    if "IP4.ADDRESS" in ip_line:
                        ip = ip_line.split(":")[-1].split("/")[0]
                        break
                return jsonify({"connected": True, "ssid": parts[3], "ip": ip})
        return jsonify({"connected": False})
    except Exception as e:
        return jsonify({"connected": False, "error": str(e)})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8090, debug=DEV_MODE)
