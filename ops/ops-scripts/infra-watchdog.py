#!/usr/bin/env python3
"""War Room infra watchdog gabungan (read-only, senyap saat sehat).

Cek: systemd units, port loopback, disk, gate live, dan kesegaran DATA.

Kenapa bagian "freshness" tidak memakai umur berkas untuk semua target:
dua sumber di sini milik root (mode 600) sehingga UID admin tidak bisa
membacanya sama sekali. Dulu watchdog memaksakan `os.path.getmtime` dan
melaporkan "tak-terbaca: PermissionError" untuk snipe-state, sementara arsip
backup memunculkan galat izin yang sama. Akibatnya dua indikator itu **tidak
pernah benar-benar diperiksa** — statusnya terbaca "jujur" padahal kosong.

Untuk keduanya dipakai bukti yang memang bisa dibaca tanpa sudo:
- `klaim-pilot`  : fakta `poly.money/klaim-pilot` yang ditulis worker tiap jam.
- `lt-backup`    : hasil job `backup` worker, dicatat di journal tiap 6 jam.

State: /home/admin/live-trading/state/watchdog-infra.json
Keluar 0 selalu saat cek jalan (ALERT = baris teks, bukan exit code).
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
            "cloud-ops-web", "nginx",
            "mariadb", "postgresql@16-main", "redis-server", "memcached"]
TIMERS = ["live-trading-watchdog", "poly-dashboard-sync",
          "war-room-git-sync", "polymarket-orderflow-confirm"]
# Timer arsip Tencent (war-room-backup, polymarket-backup) sengaja TIDAK dipantau:
# skrip /usr/local/sbin/*-backup-to-tencent sudah tidak ada di host, unit-nya
# disabled sejak 17 Sep 2026. Penggantinya job `backup` worker (lihat
# check_backup_job). Memantau unit yang mati by design hanya menghasilkan ALERT
# permanen yang menyamarkan kegagalan nyata.
# cloudflared-cloudops juga dilepas: quick tunnel berhenti 5 Okt 2026 dan
# config-nya tidak ada lagi di host; /ops tidak lagi diekspos lewat tunnel.
UNITS = SERVICES + [t + ".timer" for t in TIMERS]
DISK_WARN_PCT = 80
# Job reconcile (penulis fakta klaim-pilot) berjalan tiap 3600 dtk.
KLAIM_PILOT_FRESH_S = 6 * 3600
# Job backup worker menulis arsip tiap 6 jam; toleransi satu siklus terlewat.
BACKUP_JOB_FRESH_S = 8 * 3600
STATE_FRESH_S = {"paper-shadow-summary": 900, "dashboard-data": 120}


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
            op = json.loads(o2)
        except Exception:
            op = {"_parse": "gagal"}
    return armed, op


def mtime_of(path):
    # `sudo stat` tidak ada di allowlist sudoers; baca langsung, gagal = jujur.
    return time.time() - os.path.getmtime(path)


def _umur_fakta(kind: str, key: str):
    """(umur_detik, detail) fakta terbaru menurut `observed_at` sebenarnya.

    (None, alasan) bila tak bisa dipastikan — pemanggil wajib melaporkannya,
    bukan menganggapnya sehat.
    """
    rc, o = sh(
        "sudo", "-n", "-u", "postgres", "psql", "-d", "warroom", "-tAc",
        "select coalesce(value_json->>'observed_at', observed_at::text) "
        f"from facts where kind='{kind}' and key='{key}' "
        "order by observed_at desc limit 1",
        timeout=20,
    )
    if rc != 0:
        return None, f"psql gagal: {(o or '').strip()[:100]}"
    baris = [x for x in (o or "").splitlines() if x.strip()]
    if not baris:
        return None, "fakta belum pernah ditulis"
    teks = baris[0].strip()
    try:
        ts = datetime.fromisoformat(teks.replace("Z", "+00:00"))
    except Exception:
        return None, f"observed_at tak terbaca: {teks[:60]}"
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return int(time.time() - ts.timestamp()), teks


def check_klaim_pilot(targets: dict) -> list[str]:
    """Umur DATA snipe/klaim, bukan umur berkas (berkasnya milik root 600).

    /var/lib/poly-pilot/snipe-live-v1-state.json terakhir ditulis 28 Sep 2026.
    Worker membacanya lewat allowlist sudo; `_mtime()` di jalur itu mengembalikan
    None sehingga `observed_at` fakta = waktu BACA. Artinya angka 20 hari bisa
    tampil seolah baru diverifikasi. Yang bisa diperiksa watchdog: fakta itu
    sendiri masih diproduksi tiap jam atau tidak.
    """
    detik, detail = _umur_fakta("poly.money", "klaim-pilot")
    if detik is None:
        targets["klaim-pilot"] = f"tak-terbaca: {detail}"
        return [f"klaim-pilot umurnya tidak bisa dipastikan ({detail})"]
    targets["klaim-pilot"] = round(detik)
    if detik > KLAIM_PILOT_FRESH_S:
        return [f"klaim-pilot basi {int(detik // 3600)} jam "
                "(job reconcile berhenti menulis fakta)"]
    return []


def check_backup_job(targets: dict) -> list[str]:
    """Bukti backup dari journal job worker, bukan membaca arsip root 600."""
    rc, o = sh("journalctl", "-u", "warroom-worker", "--since", "-24h",
               "--no-pager", "-o", "cat", timeout=30)
    if rc != 0:
        targets["lt-backup"] = "tak-terbaca: journalctl"
        return ["lt-backup: journal worker tak terbaca"]
    terakhir = None
    for line in reversed((o or "").splitlines()):
        i = line.find("{")
        if i < 0:
            continue
        try:
            d = json.loads(line[i:])
        except Exception:
            continue
        if d.get("job") == "backup":
            terakhir = d
            break
    if terakhir is None:
        targets["lt-backup"] = "tidak ada job backup dalam 24 jam"
        return ["lt-backup: job `backup` tidak jalan dalam 24 jam"]
    status = terakhir.get("status")
    detail = str(terakhir.get("detail", ""))[:120]
    try:
        umur = int(time.time() - datetime.fromisoformat(
            str(terakhir.get("ts", "")).replace("Z", "+00:00")).timestamp())
        targets["lt-backup"] = f"{status} {detail} ({umur // 3600} jam lalu)"
    except Exception:
        umur = None
        targets["lt-backup"] = f"{status} {detail}"
    if status != "ok":
        return [f"lt-backup GAGAL: {detail}"]
    if umur is not None and umur > BACKUP_JOB_FRESH_S:
        return [f"lt-backup basi {umur // 3600} jam (job backup tidak jalan)"]
    return []


def check_fresh():
    stale: list = []
    targets: dict = {}
    for label, path in [
        ("paper-shadow-summary", "/var/lib/poly-paper/execution-paper-shadow-summary.json"),
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
    stale += check_klaim_pilot(targets)
    stale += check_backup_job(targets)
    return stale, targets


def main():
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
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
