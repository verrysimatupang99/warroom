"""riwayat_idx.py — close/SMA10/volume IDX harian dari arsip tick Arjum (Tencent).

KENAPA MODUL INI ADA
--------------------
Filter BSJP (`signals/bsjp.py`) butuh SMA10. TradingView tidak mengirimnya, jadi tanpa modul
ini setiap kandidat ditolak dengan alasan "SMA10 tidak diketahui" — dan fitur yang selalu
kosong tidak berguna.

Sumber SMA10 sengaja dipilih yang **tanpa kuota REST Arjum**. Alasannya ada di
`trading-api-platform-selection`: `history` + `history_yf` Arjum adalah 99% pemakaian kuota
(3.187 dari 3.214 panggilan pada 5 Okt). Menghitung SMA10 dari tick WebSocket yang sudah
tersimpan berarti tidak menambah satu pun panggilan.

Kenapa dibaca lewat SSH, bukan disalin
--------------------------------------
`arjum_trades.db` **5,0 GB / 24,9 juta baris**. Menyalinnya berarti memindahkan 5 GB untuk
mengambil 10 angka per emiten. Modul ini mengirim SATU kueri agregat dan menerima hasilnya —
jaringan hanya mengangkut hasilnya, bukan basis datanya.

BATAS YANG DIKODEKAN DI SINI
----------------------------
1. **Close harian = harga tick TERAKHIR hari itu.** Itu pendekatan yang benar untuk running
   trade, tapi ia bukan harga penutupan resmi bursa (tidak ada lelang penutupan di sini).
   Perbedaan biasanya tipis, tapi jangan diklaim identik.
2. **VWAP dipakai sebagai pengganti harga open**, karena tick tidak memuat bar open. Diberi
   label supaya tidak menyamar sebagai open sungguhan.
3. Baris tanpa tanggal (`length(ts) <= 8`) DIBUANG. Ada 2,6 juta tick (≈10%) dari format awal
   yang tidak punya tanggal; memakainya akan mencampur hari secara acak.
4. Kalau satu hari pun tidak ada, fungsi mengembalikan ``None`` — **bukan** 0 dan bukan
   rata-rata sebagian. SMA10 dari 6 hari bukan SMA10.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import subprocess
from dataclasses import dataclass
from typing import Any

from live_trading.collectors.idx import _kode_bersih  # normalisasi .JK (satu implementasi)

log = logging.getLogger(__name__)

__all__ = ["TickerHistory", "fetch_history", "SMA_HARI_DEFAULT"]

SMA_HARI_DEFAULT = 10
# Kunci + host dibaca dari lingkungan; jangan di-hardcode ke dalam kode yang di-commit.
SSH_KEY_DEFAULT = "/etc/warroom/tencent_ed25519"
SSH_HOST_DEFAULT = "ubuntu@43.155.219.37"
DB_JAUH = "/home/ubuntu/.hermes/cron/state/arjum_trades.db"

# Satu kueri agregat: close harian (tick terakhir/hari) + VWAP + total volume, untuk N emiten.
_SQL = """
SELECT ticker,
       substr(ts,1,10) AS hari,
       MAX(rowid) AS tick_terakhir,
       SUM(price * lot) / NULLIF(SUM(lot), 0) AS vwap,
       SUM(lot) AS volume,
       COUNT(*) AS n_tick
  FROM trades
 WHERE ts LIKE '{sejak}%' ESCAPE '\\'
   AND length(ts) >= 10
   AND ticker IN ({tickers})
 GROUP BY ticker, hari
 ORDER BY ticker, hari
"""

# Harga penutup harian = harga pada tick TERAKHIR hari itu (rowid terbesar, karena tabel ini
# append-only sehingga rowid menaik = urut waktu). Kueri ini dijalankan SEKALI untuk semua
# (ticker, hari) sekaligus lewat JOIN ke agregat — bukan satu kueri per hari, yang pada basis
# 24,9 juta baris menjadi ratusan kueri dan berujung timeout.
_SQL_CLOSE = """
WITH agg AS (
  SELECT ticker, substr(ts,1,10) AS hari, MAX(rowid) AS rid
    FROM trades
   WHERE ts LIKE '{sejak}%' ESCAPE '\\'
     AND length(ts) >= 10
     AND ticker IN ({tickers})
   GROUP BY ticker, hari
)
SELECT t.ticker, agg.hari, t.price, t.lot, agg.rid
  FROM trades t JOIN agg ON t.rowid = agg.rid
"""


@dataclass
class TickerHistory:
    """Riwayat harian satu emiten, plus turunannya (SMA10, rata-rata volume)."""

    ticker: str
    hari: list[str]
    close: list[float]
    vwap: list[float]
    volume: list[float]
    sma10: float | None = None
    vavg10: float | None = None
    sumber: str = "tick Arjum (Tencent) — close = tick terakhir tiap hari"

    @property
    def cukup(self) -> bool:
        """True hanya bila ada ≥10 hari. SMA10 dari hari lebih sedikit bukan SMA10."""
        return len(self.close) >= SMA_HARI_DEFAULT

    def to_dict(self) -> dict[str, Any]:
        return {
            "sma10": round(self.sma10, 2) if self.sma10 is not None else None,
            "vavg10": round(self.vavg10, 2) if self.vavg10 is not None else None,
            "sumber": self.sumber,
            "n_hari": len(self.close),
            "hari_terakhir": self.hari[-1] if self.hari else None,
        }


def _hitung_turunan(r: TickerHistory) -> TickerHistory:
    if r.cukup:
        r.sma10 = sum(r.close[-SMA_HARI_DEFAULT:]) / SMA_HARI_DEFAULT
        # Rata-rata volume 10 hari SEBELUM hari terakhir — hari ini belum selesai,
        # memasukkannya akan membuat rel-vol tampak kecil tanpa sebab.
        v = r.volume[:-1] if len(r.volume) > SMA_HARI_DEFAULT else r.volume
        v10 = v[-SMA_HARI_DEFAULT:]
        r.vavg10 = (sum(v10) / len(v10)) if v10 else None
    return r


def fetch_history(
    tickers: list[str],
    *,
    ssh_key: str = SSH_KEY_DEFAULT,
    ssh_host: str = SSH_HOST_DEFAULT,
    db: str = DB_JAUH,
    hari_lookback: int = 45,
    timeout_s: int = 90,
    maks_per_panggilan: int = 15,
) -> dict[str, TickerHistory]:
    """Ambil close harian + SMA10 untuk ``tickers`` dari arsip tick di Tencent.

    ``maks_per_panggilan`` ada karena alasan terukur: satu kueri ``ticker IN (...)`` dengan
    puluhan emiten pada 24,9 juta baris berjalan 90+ detik dan timeout. Memecahnya menjadi
    batch kecil membuat setiap panggilan selesai jauh di bawah batas waktu. Nilai 15 dipilih
    dari pengukuran, bukan tebakan.

    Mengembalikan ``{ticker: TickerHistory}``; ticker tanpa cukup hari tetap ada di hasil
    tetapi ``sma10``-nya ``None`` — pemanggil yang memutuskan, bukan fungsi ini.
    """
    if not tickers:
        return {}
    # Normalisasi di BOUNDARY: buang sufiks .JK sekali di sini, supaya setiap pemanggil
    # aman. Universe Tencent (idx_universe.json) menulis SEMUA 516 ticker sebagai 'CAMP.JK';
    # tanpa ini kueri `ticker IN ('CAMP.JK')` tidak cocok dengan DB yang menyimpan 'CAMP'
    # → hasil kosong → SMA10 None → kandidat BSJP ditolak tanpa sebab yang terlihat.
    bersih = sorted({_kode_bersih(t) for t in tickers if _kode_bersih(t)})
    if not bersih:
        return {}
    if len(bersih) > maks_per_panggilan:
        gabung: dict[str, TickerHistory] = {}
        for i in range(0, len(bersih), maks_per_panggilan):
            bagian = bersih[i:i + maks_per_panggilan]
            gabung.update(
                fetch_history(
                    bagian, ssh_key=ssh_key, ssh_host=ssh_host, db=db,
                    hari_lookback=hari_lookback, timeout_s=timeout_s,
                    maks_per_panggilan=maks_per_panggilan,
                )
            )
        return gabung
    daftar = ",".join("'" + t.replace("'", "") + "'" for t in bersih)
    # Batas tanggal dibuat sebagai bagian AWAL dari ts ('YYYY-MM-'), bukan substr(ts,1,10).
    # Alasannya terukur: tabel ini punya indeks idx_trades_ticker_ts, dan `ts LIKE 'YYYY-MM-%'`
    # memakainya (0,5 detik), sedangkan `substr(ts,1,10) >= ...` mematikannya sehingga setiap
    # kueri memindai 24,9 juta baris (50+ detik). Perbedaan frasa kueri = 100× waktu.
    # Batas tanggal diambil sebagai AWAL bulan, bukan tanggal mundur N hari. Dua alasan:
    # (1) `ts LIKE 'YYYY-MM-%'` memakai indeks idx_trades_ticker_ts (0,5 detik), sedangkan
    #     `substr(ts,1,10) >= ...` mematikannya sehingga tiap kueri memindai 24,9 juta baris;
    # (2) mundur tepat N hari bisa mendarat di bulan yang tidak punya data sama sekali
    #     (mis. 45 hari dari 5 Okt = Agustus) sehingga hasilnya kosong tanpa penjelasan.
    # Ambil bulan ini dan bulan sebelumnya; pemanggil tinggal mengambil 10 baris terakhir.
    bulan_ini = dt.date.today().replace(day=1)
    bulan_lalu = (bulan_ini - dt.timedelta(days=1)).replace(day=1)
    sejak = bulan_lalu.isoformat()[:7]
    sql = _SQL.format(tickers=daftar, sejak=sejak)
    sql_close = _SQL_CLOSE.format(tickers=daftar, sejak=sejak)

    # Skrip dikirim lewat STDIN, bukan `python3 -c`. Alasannya konkret: SQL-nya memuat
    # tanda kutip berlapis ('''...''' dan '...'), dan melewatkannya sebagai argumen `-c`
    # membuat shell memanggang escaping-nya — hasilnya kueri rusak tanpa pesan yang jelas.
    # STDIN tidak melewati shell, jadi isi skrip sampai utuh.
    #
    # Close harian = baris dengan rowid TERAKHIR hari itu (running trade append-only, jadi
    # rowid menaik = urut waktu). MAX(rowid) per grup jauh lebih cepat daripada mencari
    # MAX(ts) lalu mencocokkannya kembali: pada basis 24,9 juta baris tanpa indeks, puluhan
    # emiten selesai dalam hitungan detik.
    skrip = (
        "import sqlite3, json\n"
        f"c = sqlite3.connect('file:{db}?mode=ro', uri=True)\n"
        f"agg = c.execute({sql!r}).fetchall()\n"
        f"close = c.execute({sql_close!r}).fetchall()\n"
        "hasil = {}\n"
        "for tkr, hari, price, _lot, _rid in close:\n"
        "    hasil[(tkr, hari)] = price\n"
        "print(json.dumps([[a[0], a[1], hasil.get((a[0], a[1])), a[3], a[4], a[5]] for a in agg]))\n"
    )

    perintah = [
        "ssh", "-i", ssh_key,
        "-o", "BatchMode=yes", "-o", "ConnectTimeout=12",
        "-o", "StrictHostKeyChecking=no",
        ssh_host,
        "python3 -",
    ]
    try:
        hasil = subprocess.run(
            perintah, input=skrip, capture_output=True, text=True, timeout=timeout_s
        )
    except subprocess.TimeoutExpired:
        log.warning("fetch_history: timeout %ss", timeout_s)
        return {}
    if hasil.returncode != 0:
        log.warning("fetch_history: ssh gagal rc=%s: %s", hasil.returncode, hasil.stderr[:200])
        return {}
    try:
        baris = json.loads(hasil.stdout.strip() or "[]")
    except json.JSONDecodeError as exc:
        log.warning("fetch_history: keluaran bukan JSON: %s", exc)
        return {}

    kumpul: dict[str, TickerHistory] = {}
    for tkr, hari, close, vwap, vol, _n in baris:
        if close is None:
            continue
        r = kumpul.setdefault(
            str(tkr).upper(), TickerHistory(ticker=str(tkr).upper(), hari=[], close=[],
                                            vwap=[], volume=[])
        )
        r.hari.append(str(hari))
        r.close.append(float(close))
        r.vwap.append(float(vwap) if vwap is not None else float(close))
        r.volume.append(float(vol) if vol is not None else 0.0)

    for r in kumpul.values():
        # Urutkan menaik menurut tanggal sebelum menghitung SMA.
        urut = sorted(zip(r.hari, r.close, r.vwap, r.volume, strict=True))
        if urut:
            r.hari, r.close, r.vwap, r.volume = map(list, zip(*urut, strict=True))
        _hitung_turunan(r)
    return kumpul
