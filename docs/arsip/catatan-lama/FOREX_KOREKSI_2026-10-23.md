# Forex — koreksi pemahaman & temuan arsitektur (23 Okt 2026, lanjutan)

## 1. Koreksi terhadap laporan saya sebelumnya

Laporan `FOREX_STATUS_2026-10-23.md` menyebut lot tetap 0.10 sebagai "akar masalah"
dan menerapkan risk sizing sebagai default. **Itu salah menilai keputusan owner.**

Klarifikasi owner:
- lot 0.10 **memang disengaja** pada akun demo $500,
- proteksi sudah ada: **Buffered Breakeven (+1.2R), Partial TP (50% di +1.0R),
  Dynamic Trailing (+1.5R), Daily Ratchet** (`InpDailyTargetLock $40`,
  `InpDailyFloorLock $30`, `InpDailyMaxLoss $25`),
- Laya AI dipakai sebagai **middleware**: data mentah MT5 + sinyal Telegram diolah
  Laya untuk menentukan trade.

Konsekuensi: `InpUseRiskSizing` default `true` yang saya tambahkan **bertentangan**
dengan kebijakan owner. Sebaiknya default dikembalikan ke `false` (lot tetap 0.10)
dan risk sizing dijadikan opsi, bukan default. **Belum diubah** — menunggu keputusan.

## 2. Temuan: "Laya Sentinel" di API adalah stub, bukan AI

`services/api/src/warroom_api/laya_sentinel.py` — daemon yang dilaporkan sebagai
"Laya AI System-1", nyatanya:

```python
def __init__(self):
    self.laya_confidence = 0.92      # angka tetap
    self.bias_status     = "NEUTRAL" # tetap
    self.bias_score      = 0.0       # tetap
    self.active_headlines_count = 6  # tetap

async def _audit_cycle(self):
    self.security_status = "PHP_DISABLED_SECURE"  # string tetap
    self.last_verdict = "HEALTHY"                 # string tetap
```

Tidak ada pemanggilan model, tidak ada pembacaan data MT5, tidak ada pembacaan
Telegram. Endpoint `GET /api/v1/tencent/forex/sentinel` dan `/forex/bias` karena itu
mengembalikan **angka karangan yang terlihat meyakinkan** (`confidence 0.92`,
`verdict HEALTHY`, `n=6`, `age_sec` selalu kecil karena `last_check_ts` di-refresh
tiap 5 detik oleh loop kosong).

Risiko: kalau ada konsumen yang memakai `/forex/bias` sebagai gerbang, ia
mempercayai "NEUTRAL, bukan blackout" yang tidak berasal dari analisis apa pun.

## 3. Temuan: EA MT5 tidak memakai Laya sama sekali

`/srv/private/WarRoom_AutoTrader.mq5` tidak menyebut `laya`, `bias`, atau `sentinel`.
Alur EA saat ini murni:

```
GET /api/v1/tencent/forex/levels?symbol=XAUUSD  -> side/entry/sl/tp1
  -> cek spread, cek invalid stops
  -> trade.Buy/Sell
```

Jadi klaim "Laya sebagai middleware penentu trade" **belum terwujud di jalur EA**.
Middleware Laya yang sesungguhnya ada di paket domain
(`warroom_core/forex/strategies/multi_session_laya.py`) dan sudah diuji nyata
(`LayaEvaluator` memanggil model `convaiinnovations/laya`, p≈0.96), tetapi EA tidak
membacanya.

## 4. Temuan: EA tidak membedakan akun DEMO vs LIVE

`AccountInfoInteger` hanya dipakai untuk nomor akun. Tidak ada
`ACCOUNT_TRADE_MODE` check, dan telemetri tidak mengirim penanda demo/live.
Dengan lot 0.10 tetap, salah arah akun = risiko uang nyata.

## 5. Akses Azure

- `az` terautentikasi (`immanuelsimatupang99@gmail.com`, Azure for Students).
- VM: **`mt5-trader-vm`**, RG `FOREX-MT5-RG`, IP publik `138.91.35.65`, Windows,
  status `VM running` (displayStatus juga `Updating`), guest agent `Ready`.
- `az vm run-command invoke` **macet**: percobaan pertama timeout 180 s, lalu
  semua percobaan berikutnya gagal `Conflict: Run command extension execution is in
  progress`. Artinya ada eksekusi yang menggantung di sisi VM (kemungkinan terkait
  status `Updating`).
- SSH port 22 ke IP itu **timeout** (tidak terbuka).

Jadi akses Azure CLI **ada**, tetapi jalur eksekusi perintah belum berfungsi. Perlu
ditunggu sampai VM selesai `Updating`, atau run-command dibatalkan/di-reset.

## 6. Yang belum dikerjakan (menunggu keputusan/akses)

1. Kembalikan `InpUseRiskSizing` ke `false` sebagai default (hormati lot 0.10 owner)
   — atau tentukan angka `InpRiskPct` yang disepakati bila sizing ingin dipakai.
2. Compile + attach ulang EA di MT5 (butuh akses VM).
3. Sambungkan Laya middleware yang NYATA ke jalur keputusan EA (sekarang tidak ada).
4. Guard DEMO/LIVE di EA + penanda mode di telemetri.
5. Perbaiki atau hentikan klaim "Laya Sentinel" di API selama masih stub — jangan
   biarkan angka karangan tampil sebagai hasil analisis.
