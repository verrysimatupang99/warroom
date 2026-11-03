# Laporan Teknis: Fitur "Bus Live" (MQTT) — Proyek Komuter

**Status:** Investigasi selesai · **Sifat:** read-only, tidak ada perubahan pada kode/sistem
**Tanggal:** 2026-11-03 · **Objek:** APK Komuter v2.0.63 (versionCode 69)

---

## 0. Ringkasan Eksekutif

Fitur **"Bus Live" BUKAN bagian dari repo War Room**. Fitur ini hidup di dalam
**APK Android `id.rute.jkt`** (Komuter / RUTE.JKT), yang kode sumbernya
**tidak ada di mesin ini** — yang tersedia hanya APK terkompilasi.

Temuan inti:

1. **Ya, Bus Live benar-benar jalan** — tapi bukan lewat backend/server Komuter.
   APK berbicara **langsung** ke broker MQTT milik TransJakarta
   (`wss://mqtt.tj.co.id:8084/mqtt`) memakai **klien MQTT 3.1.1 buatan sendiri**
   (hand-rolled, ~200 baris) di atas OkHttp WebSocket.
2. **Tidak ada autentikasi.** Klien pub-sub ke topik wildcard `/mobile_armada/#`
   tanpa username/password/token. Ini berarti APK menumpang feed publik TJ.
3. **Tidak ada backend dalam alur data Bus Live.** Server Komuter hanya dipakai
   untuk geocode/plan/stations. ETA bus dihitung **di perangkat**.
4. **Saat diamati, kedua jalur pendukung sedang rusak:**
   - `/komuter-api/` (nginx → `127.0.0.1:8930`) → **tidak ada proses listen**.
     Backend `/home/admin/rute-jkt/backend` **sudah tidak ada di disk**.
   - Broker `mqtt.tj.co.id:8084` → **TCP timeout** dari mesin ini (lihat §6).
5. **Klaim UI "khusus jaringan Indonesia" adalah catatan, bukan penegakan.**
   Tidak ada pengecekan geolokasi/ASN di kode. Yang terjadi hanya: koneksi gagal
   (timeout) bila di luar jangkauan, lalu UI menampilkan `"Gagal terhubung: …"`.

**Verdict jujur:** fitur ini *implementasinya nyata dan cukup rapi secara protokol*,
tetapi *ketergantungannya rapuh dan tanpa jaring pengaman*: bergantung penuh pada
broker pihak ketiga tanpa SLA, tanpa auth, tanpa cache, dan backend pendampingnya
kini mati.

---

## 1. Metodologi (apa yang benar-benar diperiksa)

| Langkah | Alat | Hasil |
|---|---|---|
| Cari sumber "Komuter"/MQTT di repo | `search_files` | Hanya `routers/komuter.py` + proxy nginx; **tidak ada kode MQTT** |
| Baca integrasi War Room | `read_file` | Proxy tipis ke `/home/admin/rute-jkt/backend` (**path hilang**) |
| Inspeksi APK | `unzip` + `strings` | Ditemukan `TjMqtt.kt`, `LiveBusScreen.kt`, `BusLogic.kt` |
| Disassembly DEX | `androguard` 4.1.4 (di `/tmp/dexenv`) | Bytecode penuh `TjMqtt`, `BusLogic`, `LiveBus`, screen |
| Uji runtime | `ss`, `curl`, socket, `openssl` | Port 8930 mati; broker timeout |

**Batas kejujuran:** tidak ada source `.kt`. Semua perilaku di bawah **dibaca dari
bytecode DEX** (bukan tebakan), dan **belum diverifikasi dengan APK berjalan di
perangkat Indonesia**. Poin yang tidak bisa dibuktikan ditandai eksplisit.

---

## 2. Arsitektur Sebenarnya

```
┌──────────────── APK Komuter (id.rute.jkt) ────────────────┐
│                                                            │
│  LiveBusScreen.kt ──collect──► TjMqtt.liveBuses()          │
│         │                          │                       │
│         │                          ▼                       │
│         │                    TjMqtt.session()              │
│         │                    (callbackFlow)                │
│         │                          │                       │
│         │            OkHttp WebSocket + MQTT 3.1.1 manual  │
│         │                          │                       │
│         ▼                          ▼                       │
│  BusLogic.arrivalsAt()      wss://mqtt.tj.co.id:8084/mqtt  │
│  (ETA dihitung di HP)              │                       │
│                                    ▼                       │
└────────────────────────────  [Broker TransJakarta] ───────┘

   JALUR TERPISAH (bukan untuk Bus Live):
   APK ──HTTP──► /komuter-api/ (nginx) ──► 127.0.0.1:8930  ◄── MATI
                 └─► /home/admin/rute-jkt/backend           ◄── HILANG
```

**Penting:** tidak ada satu pun byte data Bus Live yang melewati server Komuter
atau War Room. Server hanya untuk *perencanaan rute*, bukan *posisi bus*.

---

## 3. Protokol MQTT — Detail Terverifikasi (dari bytecode)

### 3.1 Konstanta (`TjMqtt.<clinit>` + `session`)

| Item | Nilai | Bukti |
|---|---|---|
| URL broker | `wss://mqtt.tj.co.id:8084/mqtt` | `const-string v3` di `session$1.invokeSuspend` |
| Header WS | `Sec-WebSocket-Protocol: mqtt` | `addHeader("Sec-WebSocket-Protocol","mqtt")` |
| Client ID | `"mqttjs_" + Long.toHexString(nanoTime ^ (millis*25214903917 & 0xFFFFFF))` | disamarkan menyerupai **MQTT.js** (klien web) |
| Topik SUBSCRIBE | `"/mobile_armada/#"` (**wildcard**, perhatikan garis miring depan) | `subscribePacket()` |
| QoS subscribe | `1` | byte `write(1)` |
| Packet ID subscribe | `1` | `write(0), write(1)` |
| Keepalive | 60 detik | `write(60)` di `connectPacket` |
| Protokol | Level **4** (MQTT 3.1.1), nama `"MQTT"` | `encodeString("MQTT")`, `write(4)` |
| Connect flags | `0x02` = **clean session**, tanpa user/pass/will | `write(2)` |
| PINGREQ | `[0xC0, 0x00]` tiap **40 detik** | array payload + `pingJob` `delay(40000)` |

### 3.2 Siklus hidup

- `connectPacket()` → rakit CONNECT manual: `packet(0x10, body)`.
- `onOpen` → kirim CONNECT.
- `onMessage` → baca tipe paket `(byte0 & 0xF0) >> 4`:
  - tipe **2 (CONNACK)** → **no-op** (tidak ada validasi return code)
  - tipe **3 (PUBLISH)** → `decodePublish()` → `parseBus()` → emit
  - tipe lain → diabaikan
- Setelah PUBLISH pertama berhasil: **baru** kirim `subscribePacket()`.

> ⚠️ **Cacat protokol (terverifikasi):**
> 1. **Tidak pernah kirim PUBACK** walau subscribe QoS 1 dan broker mengirim
>    PUBLISH QoS 1. Broker bisa retransmisi paket sama terus-menerus.
> 2. **tidak menangani PINGRESP** — tidak masalah fungsional, hanya boros.
> 3. **CONNACK tidak dicek** — kalau broker menolak (return code ≠ 0),
>    app tidak tahu dan hanya akan diam sampai timeout.
> 4. `decodePublish` **tidak menggeser** offset setelah Packet ID sebelum membaca
>    payload — hanya aman bila semua pesan QoS 0. Tidak ada penanganan QoS di header bit.

### 3.3 Reconnect

`liveBuses()` membungkus `session()` dalam loop `while(isActive)`:
`emitAll(session())` → `delay(min(2s × 2^n, 30s))`. Jadi backoff eksponensial
2s → 4s → 8s → 16s → 30s (cap), tanpa batas percobaan. **Tidak ada jitter**
(potensi thundering-herd ke broker TJ).

### 3.4 Klien HTTP

`OkHttpClient`: `pingInterval(30s)`, `connectTimeout(20s)`, `readTimeout(0)` (tak terbatas).

---

## 4. Pemetaan Data & Logika ETA

### 4.1 `parseBus(topic, json)` → `LiveBus`

Field JSON yang dibaca: `stops[]`, `next_stops`, `stop_id`, `name`, `eta`,
`platform_code`, `latitude`/`snap_latitude`, `longitude`/`snap_longitude`,
`bearing`, `route_code`, `route_long_name`, `route_color` (default `0055FF`),
`trip_headsign`, `bus_body_no`, `passengers_status`, `timestamp`.

Prioritas koordinat: `snap_latitude|snap_longitude` (posisi "snap ke jalan")
lebih diutamakan daripada `latitude|longitude` mentah.

### 4.2 `BusLogic.arrivalsAt(buses, stopName)`

Filter: `stops[]` yang `name == stopName` (case-insensitive) **dan** `eta > 0`,
lalu diurutkan naik berdasarkan ETA.

> ⚠️ **Kelemahan:** pencocokan memakai **nama halte**, bukan `stop_id`.
> `stop_id` ada di JSON tapi dibuang di `parseBus`. Nama halte TJ banyak yang
> mirip/duplikat → ETA berpotensi tertukar antar-halte. Ini asumsi berbasis kode,
> belum diuji lapangan.

### 4.3 Penanganan error di UI

`LiveBusScreen` meng-`collect` flow dalam try/catch →
`status = "Gagal terhubung: " + (e.message ?: "tidak diketahui")`,
`connected = false`. Saat data pertama tiba → `connected = true`,
`status = "Nyambung — data live ngalir"`.

---

## 5. Soal Klaim "Khusus Jaringan Indonesia"

Teks UI (string di APK):
- ID: *"Feed posisi bus live dari broker MQTT TransJakarta. Cuma bisa nyambung dari jaringan Indonesia ya."*
- EN: *"Live bus position feed from the TransJakarta MQTT broker. Reachable from Indonesian networks only."*

**Fakta dari kode:** **tidak ada** pengecekan lokasi, IP, SIM, atau ASN.
Klaim tersebut adalah **deskripsi konsekuensi jaringan**, bukan pembatasan aktif.
Yang benar-benar terjadi: koneksi gagal → pesan error generik. Pengguna tidak
pernah diberi tahu "*Anda di luar Indonesia*" secara spesifik.

Begitu juga klaim "*broker MQTT resmi TransJakarta*" — mesin ini tidak bisa
memverifikasi status resmi/legal feed tersebut (lihat §7).

---

## 6. Kondisi Runtime Saat Diperiksa

| Jalur | Perintah | Hasil | Tafsir |
|---|---|---|---|
| Backend Komuter (War Room) | `curl :8800/api/v1/komuter/health` | **HTTP 500** `{"code":"internal"}` | Import `app.main` gagal |
| Akar penyebab | `python -c "import app"` | `ModuleNotFoundError: No module named 'app'` | `/home/admin/rute-jkt/backend` **tidak ada** |
| Proxy nginx | `ss -ltnp \| grep 8930` | **tidak listen** | `/komuter-api/` upstream mati |
| `curl :80/komuter-api/health` | | HTTP **301** → https | redirect ke host yang sama |
| Broker TJ | socket TCP `103.145.125.134:8084` | **TimeoutError** | Tak terjangkau dari mesin ini (luar Indonesia / firewall) |
| DNS | `getent hosts` | `103.145.125.134` | Resolusi OK → masalah di lapisan jaringan, bukan DNS |
| TLS cert | `openssl s_client` | (tidak ada output — koneksi tak terbentuk) | Tidak dapat diverifikasi |

**Implikasi jujur:** saat ini, **dari mesin ini**, tidak ada satu pun komponen
Bus Live yang terbukti berfungsi. Ini **tidak** membuktikan fitur rusak di
perangkat pengguna di Indonesia — hanya membuktikan *ketergantungan eksternal
tidak dapat diaudit/diuji dari sini*.

> Catatan integritas: `HOLD_DO_NOT_TOUCH_AZURE_VM.md` ada di root repo. Saya tidak
> menyentuh apa pun di luar pembacaan; semua pekerjaan analisis di `/tmp`.

---

## 7. Batasan Investigasi (apa yang TIDAK bisa saya buktikan)

1. **Tidak ada source code.** Semua kesimpulan dari bytecode; nama variabel,
   komentar, dan niat desain tidak dapat dipastikan.
2. **Tidak ada uji perangkat.** Saya tidak bisa menjalankan APK di jaringan
   Indonesia, jadi tidak bisa memastikan feed benar-benar mengalir.
3. **Format topik `/mobile_armada/#` (garis miring depan) tidak diverifikasi
   terhadap broker nyata.** Ini justru titik paling rapuh: MQTT tidak
   mem-normalisasi leading slash — kehilangan satu `/` = subscribe gagal.
   Belum terbukti salah, tapi juga **belum terbukti benar**.
4. **Status "resmi" broker** tidak diverifikasi. Mengambil feed tanpa auth
   dari infrastruktur pihak ketiga berpotensi melanggar ToS — perlu tinjauan legal.
5. **Tidak ada monitoring** terhadap fitur ini apa pun (tidak ada metrik, log
   server, atau alert) karena datanya tidak melewati server sendiri.

---

## 8. Temuan Prioritas

| # | Tingkat | Temuan | Dasar |
|---|---|---|---|
| F1 | **Kritis** | Backend Komuter mati: `rute-jkt/backend` hilang → `/api/v1/komuter/*` HTTP 500, `/komuter-api/` tanpa upstream | §6 |
| F2 | **Tinggi** | Bus Live 100% bergantung broker pihak ketiga; tanpa auth, tanpa cache, tanpa fallback | §3.1 |
| F3 | **Tinggi** | Tidak ada PUBACK untuk PUBLISH QoS 1 → risiko duplikasi/retransmisi | §3.2 |
| F4 | **Sedang** | CONNACK tidak divalidasi → kegagalan senyap | §3.2 |
| F5 | **Sedang** | ETA dicocokkan via nama halte, bukan `stop_id` → risiko tertukar | §4.2 |
| F6 | **Sedang** | Klaim "Indonesia only" tidak ditegakkan & tidak dijelaskan ke pengguna | §5 |
| F7 | **Rendah** | Tanpa jitter pada backoff; `readTimeout=0` | §3.3–3.4 |
| F8 | **Rendah** | `connected=true` diset saat data **pertama**, bukan saat CONNACK | §3.2 |

---

## 9. Rekomendasi (tanpa saya menerapkan apa pun)

1. **Pulihkan/relokasi backend Komuter** (F1) atau **hapus** router
   `komuter.py` dari War Room agar tidak menyajikan endpoint 500 yang menyesatkan.
2. **Tambahkan PUBACK** (F3) dan **validasi CONNACK** (F4) — perbaikan kecil,
   dampak besar pada keandalan.
3. **Verifikasi topik `/mobile_armada/#`** langsung dari perangkat Indonesia
   sebelum menyimpulkan fitur sehat (F2/§7.3).
4. **Ubah pencocokan halte ke `stop_id`** (F5) — datanya sudah tersedia di JSON.
5. **Perjelas copy UI** atau **tegakkan** pembatasan jaringan (F6).
6. **Tinjau aspek legal** penggunaan feed tanpa autentikasi (§7.4).

---

## 10. Kesimpulan

"Bus Live" di Komuter adalah **klien MQTT 3.1.1 buatan sendiri yang berbicara
langsung ke broker TransJakarta dari dalam APK** — bukan fitur backend.
Implementasinya nyata, relatif ringkas, dan cukup paham protokol, tetapi:

- bergantung penuh pada sumber eksternal **tanpa autentikasi & tanpa kendali**,
- punya **cacat protokol** (PUBACK, CONNACK, offset QoS) yang membatasi keandalan,
- klaim "Indonesia only" adalah **konsekuensi, bukan kontrol**,
- dan **komponen pendampingnya (API Komuter) saat ini mati** karena direktori
  backend sudah tidak ada.

Segala sesuatu di atas berasal dari bytecode APK v2.0.63 dan pengujian runtime
read-only. Poin yang tidak dapat diverifikasi dari mesin ini sudah ditandai
secara eksplisit dan tidak saya sajikan sebagai fakta.

---

### Lampiran: Artefak Analisis
- DEX terurai: `/tmp/apk_probe/x/classes{1,2,3}.dex`
- Disassembly `TjMqtt`: `/tmp/apk_probe/tjmqtt_disasm.txt` (1.809 baris)
- `BusLogic`: `/tmp/apk_probe/buslogic.txt`
- Entry effect UI: `/tmp/apk_probe/scr_effect.txt`, `collector.txt`, `screen2.txt`
- Toolchain: `/tmp/dexenv` (androguard 4.1.4)
