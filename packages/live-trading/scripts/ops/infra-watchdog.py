#!/usr/bin/env python3
"""War Room infra watchdog gabungan (read-only, senyap saat sehat).

Cek: systemd units, port loopback, disk, gate live, freshness state/backups.
State: /home/admin/live-trading/state/watchdog-infra.json (delta antar run).
Keluar 0 selalu saat cek jalan (ALERT = baris teks, bukan exit code).
UID yang jalan: admin (gate = cek keberadaan berkas; snipe-state = allowlist sudo cat).
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime

HOME = "/home/admin"
STATE_F = f"{HOME}/live-trading/state/watchdog-infra.json"
PORTS = {3100: "warroom-web", 8800: "warroom-api", 8790: "poly-agent",
         8799: "lt-dashboard", 8100: "cloudops-v2", 8000: "cloudops-api",
         3000: "cloudops-web", 8090: "tunnel-local"}
SERVICES = ["warroom-api", "warroom-web", "warroom-worker",
            "live-trading-dashboard", "poly-agent",
            "polymarket-paper-shadow", "polymarket-paper-candidate",
            "polymarket-paper-fade", "polymarket-research-recorder",
            "cloud-ops-api", "cloud-ops-v2",
            "cloud-ops-web", "cloudflared-cloudops", "nginx",
            "mariadb", "postgresql@16-main", "redis-server", "memcached"]
TIMERS = ["live-trading-watchdog", "poly-dashboard-sync",
          "war-room-backup", "polymarket-backup",
          "war-room-git-sync", "polymarket-orderflow-confirm"]
UNITS = SERVICES + [t + ".timer" for t in TIMERS]
DISK_WARN_PCT = 80
STATE_FRESH_S = {"paper-shadow-summary": 900, "snipe-state": 300,
                 "dashboard-data": 120, "lt-backup": 6 * 3600 + 600}
ALLOW_SUDO_CAT = [
    "/var/lib/poly-paper/execution-paper-shadow-summary.json",
    "/var/lib/poly-pilot/snipe-live-v1-state.json",
    "/var/www/html/data.json",
]


def sh(*a, timeout=15):
    try:
        r = subprocess.run(a, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return 99, str(e)


def check_units():
    down = []
    for u in UNITS:
        rc, o = sh("systemctl", "is-active", u if "." in u else u + ".service")
        if o.strip().splitlines()[0:1] != ["active"]:
            down.append(u)
    return down


def check_ports():
    dead = []
    for p, name in PORTS.items():
        s = socket.socket()
        s.settimeout(3)
        try:
            s.connect(("127.0.0.1", p))
        except Exception:
            dead.append(f"{p}/{name}")
        finally:
            s.close()
    return dead


def check_disk():
    try:
        u = shutil.disk_usage("/")
        pct = round(u.used / u.total * 100, 1)
        return pct, pct >= DISK_WARN_PCT
    except Exception:
        return -1, True


def check_gate():
    # DISARMED = tidak ada file exact /etc/poly-pilot/activation-approved
    rc, o = sh("ls", "/etc/poly-pilot/activation-approved")
    armed = (rc == 0)
    op = {}
    rc2, o2 = sh("sudo", "-n", "/usr/bin/cat",
                 "/var/lib/poly-pilot/snipe-live-v1-state.json")
    if rc2 == 0:
        try:
            op = json.loads(o2.strip().splitlines()[0] if False else o2)
        except Exception:
            op = {"_parse": "gagal"}
    return armed, op


def mtime_of(path):
    # `sudo stat` tidak ada di allowlist sudoers dan pasti ditolak di konteks
    # systemd setelah baris %sudo blanket dicabut — baca langsung, gagal = jujur.
    return time.time() - os.path.getmtime(path)


def check_fresh():
    stale = []
    now = time.time()
    targets = {}
    for label, path in [
        ("paper-shadow-summary", "/var/lib/poly-paper/execution-paper-shadow-summary.json"),
        ("snipe-state", "/var/lib/poly-pilot/snipe-live-v1-state.json"),
        ("dashboard-data", "/var/www/html/data.json"),
    ]:
        try:
            age = mtime_of(path)
            targets[label] = round(age)
            limit = STATE_FRESH_S.get(label, 900)
            if age > limit:
                stale.append(f"{label} basi {int(age // 60)} mnt")
        except Exception as e:
            targets[label] = f"tak-terbaca: {type(e).__name__}"
    try:
        ltd = f"{HOME}/live-trading/backups"
        cands = sorted((f for f in os.listdir(ltd) if f.endswith(".tar.gz")),
                       reverse=True)
        if cands:
            age = now - os.path.getmtime(os.path.join(ltd, cands[0]))
            targets["lt-backup"] = f"{cands[0]} umur {int(age // 3600)} jam"
            if age > STATE_FRESH_S["lt-backup"]:
                stale.append(f"lt-backup basi {int(age // 3600)} jam")
        else:
            stale.append("lt-backup: tidak ada arsip")
    except Exception as e:
        stale.append(f"lt-backup tak-terbaca: {type(e).__name__}")
    return stale, targets


def main():
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    prev = {}
    try:
        prev = json.load(open(STATE_F))
    except Exception:
        pass
    units_down = check_units()
    ports_dead = check_ports()
    disk_pct, disk_warn = check_disk()
    gate_armed, _ = check_gate()
    stale, fresh = check_fresh()
    alerts = []
    for u in units_down:
        alerts.append(f"ALERT unit down: {u}")
    for p in ports_dead:
        alerts.append(f"ALERT port mati: {p}")
    if disk_warn:
        alerts.append(f"ALERT disk / {disk_pct}% (>= {DISK_WARN_PCT}%)")
    if gate_armed:
        alerts.append("ALERT gate LIVE armed (/etc/poly-pilot/activation-approved ADA)")
    for s in stale:
        alerts.append(f"WARN {s}")
    for a in alerts:
        if prev.get("last_alert", {}).get(a) == prev.get("run_at"):
            pass
    line = (f"{now} units={len(UNITS)-len(units_down)}/{len(UNITS)} "
            f"ports={len(PORTS)-len(ports_dead)}/{len(PORTS)} "
            f"disk={disk_pct}% gate={'ARMED' if gate_armed else 'DISARMED'} "
            f"stale={len(stale)}")
    print(line)
    for a in alerts:
        print(a)
    if not alerts:
        print("SEHAT semua cek lolos")
    try:
        os.makedirs(os.path.dirname(STATE_F), exist_ok=True)
        json.dump({"run_at": now, "units_down": units_down,
                   "ports_dead": ports_dead, "disk_pct": disk_pct,
                   "gate_armed": gate_armed, "stale": stale,
                   "fresh": fresh}, open(STATE_F, "w"), indent=1)
    except Exception as e:
        print(f"WARN state tak-tersimpan: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
