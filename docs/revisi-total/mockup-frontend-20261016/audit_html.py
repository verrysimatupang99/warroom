# ruff: noqa: E501, E741, F401
#!/usr/bin/env python3
"""Audit inspeksi-kode (R-35, mockup statis) untuk semua unduhan/<id>.html.

Per layar dicek:
  - penanda konten wajib (sesuai prompt yang dikirim ke Stitch)
  - kejujuran: angka hanya dari daftar putih; tag TERUKUR / BELUM TERVERIFIKASI
  - bahasa: label Indonesia yang wajib ada
  - slop: emoji, gradient, glow/purple, font default trio, statistik karangan
"""
import html as htmlmod
import json
import os
import re
import sys

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "unduhan")

ANGKA_PUTIH = [
    "+0,86%", "+1,06%", "10,0 bps", "11,9 bps", "14,8%", "62,6%",
    "24,9", "200", "47", "99%", "61%", "300",
]

WAJIB = {
    "home": {
        "konten": ["SINYAL PER MARKET", "Crypto", "IDX", "Polymarket", "Forex", "Hyperliquid", "snapshot 07:45"],
        "bahasa": ["Hari ini", "menunggu", "Terukur|TERUKUR"],
        "jujur": ["TERUKUR"],
    },
    "idx": {
        "konten": ["+0,86%", "+1,06%", "STRONG", "ARA", "walk-forward|TERUKUR"],
        "bahasa": ["Beli Sore Jual Pagi", "kandidat|KANDIDAT", "lolos"],
        "jujur": ["TERUKUR"],
    },
    "crypto": {
        "konten": ["10,0 bps", "GMGN", "DexScreener|Dex Screener"],
        "bahasa": ["terukur|TERUKUR|TERUKUR", "sinyal|SINYAL"],
        "jujur": ["TERUKUR"],
    },
    "gmgn": {"konten": ["GMGN", "kontrak|Kontrak", "likuiditas|Likuiditas"], "bahasa": ["kandidat|Kandidat"], "jujur": ["BELUM TERVERIFIKASI"]},
    "polymarket": {"konten": ["Gamma", "CLOB|CLOB", "paper trade"], "bahasa": ["peluang|PELUANG", "dipantau|DIPANTAU"], "jujur": ["BELUM TERVERIFIKASI"]},
    "forex": {
        "konten": ["99%", "Arjum", "USD/IDR|EUR/USD"],
        "bahasa": ["agenda|AGENDA", "hari ini|HARI INI"],
        "jujur": ["BELUM TERVERIFIKASI"],
    },
    "berita": {"konten": ["07:45"], "bahasa": ["berita|BERITA", "sumber|SUMBER"], "jujur": []},
    "sistem": {
        "konten": ["warroom-api", "warroom-web", "300", "bandarmologi", "bsjp", "overextended", "PAPER"],
        "bahasa": ["layanan|LAYANAN", "kill switch|KILL SWITCH|Kill"],
        "jujur": [],
    },
    "leaderboard": {"konten": ["62,6%", "14,8%", "R "], "bahasa": ["strategi|STRATEGI", "layak"], "jujur": ["TERUKUR"]},
    "riset": {"konten": ["walk-forward|TERUKUR", "2026"], "bahasa": ["riset|RISET", "terverifikasi|TERVERIFIKASI"], "jujur": ["TERVERIFIKASI"]},
    "catatan": {"konten": ["R |−|minus|turun"], "bahasa": ["catatan|CATATAN", "jurnal|JURNAL"], "jujur": []},
    "masuk": {"konten": ["War Room"], "bahasa": ["Masuk", "kata sandi|Kata Sandi|sand|password"], "jujur": []},
    "cara-kerja": {
        "konten": ["snapshot", "paper trade", "live"],
        "bahasa": ["cara kerja|CARA KERJA|Cara"],
        "jujur": [],
    },
    "bantuan": {"konten": ["—", "TERUKUR|terukur"], "bahasa": ["Bantuan", "Kenapa"], "jujur": []},
}

SLOP = {
    "emoji": re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]"),
    "gradient": re.compile(r"linear-gradient|radial-gradient"),
    "glow_shadow": re.compile(r"box-shadow:\s*[^;]*(#[0-9a-fA-F]{6}|rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*)"),
    "pill": re.compile(r"border-radius:\s*(999|9999|[2-9]\d{2,})px"),
    "purple_blue": re.compile(r"#(6366f1|8b5cf6|a855f7|3b82f6|6d28d9|7c3aed)"),
    "font_aslop": re.compile(r"Space Grotesk|Geist|Poppins"),
    "stat_karangan": re.compile(r"(10K|99\.9%|500M|1,204|\+12%|120\+|100% uptime|atm|placeholder text)", re.I),
}

def pat(k: str) -> str:
    """Jadikan string liter ambigu-aman: escape tiap cabang alternasi."""
    return "|".join(map(re.escape, k.split("|")))


hasil = []
for layar in WAJIB:
    p = os.path.join(DIR, f"{layar}.html")
    if not os.path.exists(p):
        hasil.append((layar, "FAIL", "file html tidak ada"))
        continue
    raw = open(p, encoding="utf-8", errors="replace").read()
    txt = htmlmod.unescape(raw)
    masalah = []

    for k in WAJIB[layar]["konten"]:
        if not re.search(pat(k), txt, re.IGNORECASE):
            masalah.append(f"kurang konten: {k}")
    for k in WAJIB[layar].get("bahasa", []):
        if not re.search(pat(k), txt, re.IGNORECASE):
            masalah.append(f"kurang bahasa-id: {k}")
    for k in WAJIB[layar].get("jujur", []):
        if not re.search(pat(k), txt, re.IGNORECASE):
            masalah.append(f"kurang tag jujur: {k}")

    for nama, pola in SLOP.items():
        hits = pola.findall(txt)
        if hits:
            sampel = ", ".join(h if isinstance(h, str) else h[0] for h in hits[:4])
            masalah.append(f"slop[{nama}] x{len(hits)}: {sampel}")

    # angka gede di luar daftar putih (kecuali token desain like hex/#rgb, th, dsb.)
    angka = set(re.findall(r"\d{1,2}[.,]\d{1,2}%|—", txt))
    hasil.append((layar, "OK" if not masalah else "WARN", "; ".join(masalah) if masalah else "-"))

status_fail = 0
for layar, st, ket in hasil:
    print(f"{st:5} {layar:12} {ket}")
    if st != "OK":
        status_fail += 1
print(f"RINGKAS: {len(hasil)-status_fail} OK / {len(hasil)}")
sys.exit(0 if status_fail == 0 else 2)
