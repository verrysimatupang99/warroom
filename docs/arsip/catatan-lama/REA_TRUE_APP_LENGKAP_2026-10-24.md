# Analisa REA — TRUE: AI Market Intelligence (`com.truetrading.dev`)

Tanggal: 24 Okt 2026
Sumber: bundel APKS dari APKCube (link pengguna) + Drive mirror
Status: **analisa statis permukaan** — bukan dekompilasi penuh (lihat §8)

---

## 1. Provenance berkas

| Item | Nilai |
|---|---|
| Unduhan | 76.892.166 byte (74 MB) |
| Format | **APKS** (bundel, bukan APK tunggal) |
| Isi | `base.apk` **118 MB** + 28 `split_config.*.apk` |
| DEX | **8 berkas** `classes*.dex` |
| Metadata | `APKCube/1 ... pkg=com.truetrading.dev vc=236` |
| Tanda tangan | `sig=MYwEFfAVkJpCrWQgsSb4sw` (belum diverifikasi) |

---

## 2. Arsitektur

**React Native**, bukan native murni:

| Komponen | Bukti |
|---|---|
| RN host | `com.truetrading/dev/MainApplication$reactNativeHost$1`, `MainActivity$createReactActivityDelegate$1` |
| JS engine | **Hermes bytecode** — `assets/index.android.bundle` 39 MB, magic `c6 1f bc 03` |
| Native module kustom | `ai.truefinance.devicestats.TrueDeviceStatsModule` + `FrameWatch` |

Implikasi: logika bisnis ada di Hermes bytecode, bukan DEX. Analisa kode butuh
dekompilasi Hermes, bukan hanya jadx.

---

## 3. Izin (28 `android.permission.*`)

**Wajar untuk trading + chat AI:**

| Izin | Alasan |
|---|---|
| `INTERNET`, `ACCESS_NETWORK_STATE`, `ACCESS_WIFI_STATE` | koneksi |
| `POST_NOTIFICATIONS`, `FOREGROUND_SERVICE` | alert harga |
| `USE_BIOMETRIC`, `USE_FINGERPRINT` | kunci aplikasi |
| `RECORD_AUDIO`, `FOREGROUND_SERVICE_MICROPHONE` | input suara "Kira" |
| `VIBRATE`, `WAKE_LOCK`, `RECEIVE_BOOT_COMPLETED` | standar |
| `BLUETOOTH_CONNECT`, `BLUETOOTH_ADMIN` | hardware wallet / WalletConnect |

**Perlu perhatian:**

| Izin | Kenapa |
|---|---|
| `AD_ID` + `ACCESS_ADSERVICES_AD_ID` | akses **Advertising ID** di aplikasi trading |
| `SYSTEM_ALERT_WINDOW` | bisa menggambar di atas aplikasi lain |
| `WRITE_EXTERNAL_STORAGE`, `READ_MEDIA_AUDIO` | akses penyimpanan |
| `DUMP` | level signature; deklarasinya mencurigakan |
| `DETECT_SCREEN_CAPTURE` | justru pro-privasi (deteksi screenshot) |

**Tidak diminta (bagus):** kamera, kontak, lokasi GPS, SMS, kalender.

Atribut `allowBackup` ada di manifest, **nilainya belum dipastikan** (butuh parser XML biner).
Kalau `true`, data aplikasi ikut backup sistem — relevan untuk aplikasi wallet.

---

## 4. SDK pihak ketiga

| SDK | Kemunculan | Fungsi |
|---|---|---|
| **Sentry** | 3.502 | crash reporting |
| **Firebase** | 2.168 | analytics / messaging / config |
| **AppsFlyer** | 746 | **install attribution + fingerprint perangkat** |
| **Mixpanel** | 235 | product analytics |
| Reown / WalletConnect | 70 / 27 | koneksi wallet |
| **Amplitude** | 32 | product analytics |
| Segment | 2 | event pipeline |

Empat SDK analitik sekaligus di aplikasi trading adalah konfigurasi berat.

---

## 5. Kunci & kredensial

| Ditemukan | Jenis | Penilaian |
|---|---|---|
| `pk_live_hirbpu0cVcLHrjktC9l7fbc9ctjv0SLa` | Clerk **publishable** | publik by design — aman |
| `pk_test_fqWjXZMSFwloh7orvJsRfjiUHXJqFzISO` | Clerk publishable (test) | publik by design |
| `https://729bf8…@o4510997957836800.ingest.de.sentry.io/…` | Sentry DSN | publik by design |
| `sk_live_*` / `sk_test_*` | secret key | **TIDAK ADA** ✅ |

Tidak ada private key, mnemonic, atau service-role key tertanam.

---

## 6. Permukaan jaringan

| Host | Kemunculan |
|---|---|
| `app.truefinance.ai` | 59 |
| `docs.truefinance.ai` | 3 |
| `status.`, `stake.`, `quotes.`, `explorer.`, `midas.truefinance.ai` | 1–2 |

Path API terlihat: `/api/v0/sdk/`, `/api/v1/wallets/`, `/api/v1/apps/`, `/api/human`, `/v1/browse/`.

**Endpoint MCP** (diverifikasi terpisah): `POST https://app.truefinance.ai/api/v1/mcp`
→ **401 `{"code":-32001,"message":"missing_token"}`**. Autentikasi ditegakkan.

---

## 7. Temuan utama: Data Safety vs isi aplikasi

Play Store menyatakan:

> "may share: **Personal info and Financial info**"
> "**No data collected**"

Isi aplikasi:

1. **AppsFlyer** — atribusi instalasi & fingerprint perangkat
2. **Mixpanel, Amplitude, Firebase Analytics** — analitik produk
3. **Izin `AD_ID`** — Advertising ID
4. **Modul native `TrueDeviceStats`** — telemetri performa perangkat

**Penilaian:** kehadiran SDK ≠ bukti pengumpulan data, tapi kombinasinya **tidak konsisten**
dengan klaim "No data collected". Untuk aplikasi wallet non-kustodial, transparansi data
adalah isu keamanan, bukan cuma privasi.

---

## 8. Yang belum dilakukan

| Kebutuhan | Status |
|---|---|
| Manifest lengkap (`allowBackup`, `usesCleartextTraffic`, `exported`) | ❌ butuh parser XML biner |
| Dekompilasi kode | ❌ Hermes bytecode, butuh `hermes-dec`/`hbctool` |
| Analisa DEX mendalam | ❌ REA butuh `jadx-headless-mcp` 0.7.1 JAR |
| Enumerasi tool MCP | ❌ butuh token read-only |
| Verifikasi tanda tangan | ❌ butuh apksigner |

REA menolak dengan:
> `Set REA_JADX_MCP_JAR to the absolute path of a caller-supplied jadx-headless-mcp 0.7.1 JAR.`

`adb` tidak terpasang, tidak ada Chrome lokal untuk `inspect_web_page`. Analisa di atas
memakai tooling setara (unzip, strings, ekstraksi manifest biner).

---

## 9. Ringkasan

| Aspek | Nilai |
|---|---|
| Kunci rahasia tertanam | 🟢 tidak ada |
| Izin berlebihan | 🟡 AD_ID, SYSTEM_ALERT_WINDOW, DUMP |
| Tracking pihak ketiga | 🟡 4 SDK analitik + AppsFlyer |
| Konsistensi Data Safety | 🔴 "No data collected" vs isi aplikasi |
| Auth endpoint MCP | 🟢 401 terverifikasi |
| Izin sensitif (kamera/kontak/lokasi/SMS) | 🟢 tidak diminta |

**Kesimpulan:** tidak ada kredensial berbahaya tertanam, tapi **jejak analitiknya berat**
dan **deklarasinya tidak konsisten** dengan isi aplikasi.

---

## 10. Hasil dekompilasi (jadx 1.5.6 + hermes-dec 0.1.8)

### Manifest
| Atribut | Nilai | Penilaian |
|---|---|---|
| `allowBackup` | **false** | 🟢 baik — data wallet tidak ikut backup |
| `usesCleartextTraffic` | tidak diset | 🟢 default false (targetSdk ≥ 28) |
| `debuggable` | tidak diset | 🟢 false |
| `networkSecurityConfig` | tidak ada | 🟡 tidak ada pinning eksplisit |

### 14 komponen exported — 7 tanpa proteksi permission
| Komponen | Catatan |
|---|---|
| `MainActivity` | 4 intent-filter (launcher + deep link) — wajar |
| `androidx.compose.ui.tooling.PreviewActivity` | 🔴 **activity tooling debug ter-export di build release** |
| `expo.modules.clipboard.ClipboardFileProvider` | 🟡 **FileProvider ter-export tanpa permission** |
| `app.notifee.core.AlarmPermissionBroadcastReceiver` | 🟡 receiver ter-export tanpa permission |
| `NotificationReceiverActivity`, Customer.io, CropImageActivity | pustaka, risiko rendah |

Sisanya (`SystemJobService`, Firebase receivers, `DiagnosticsReceiver`, `ProfileInstallReceiver`,
`RevocationBoundService`) terlindungi permission sistem.

### Deep link
| Filter | Skema / host | Penilaian |
|---|---|---|
| Launcher | — | normal |
| Custom scheme | `truetradingmobileapp://`, `exp+true-ai://` | 🟡 **dapat dibajak aplikasi lain** (skema kustom tidak terverifikasi) |
| App Link | `https://true-test.onelink.me` | 🔴 **domain TEST AppsFlyer ikut di build release** |
| App Link | `https://app.truefinance.ai` | 🟢 domain produksi |

Temuan `true-test.onelink.me` menunjukkan konfigurasi atribusi **test** terkirim ke produksi.

### Permukaan API (66 path dari Hermes)
```
/api/auth/wallet/attach      /api/auth/wallet/proof
/api/bot/v1                  /api/legal/consent[/status]
/api/memecoin/solana/{list/new-listings,search,stream}
/api/perps-dex/venue-moves   /api/coingecko/{global,markets-sparkline}
/api/v1/academy/{complete,status}   /api/v1/{announcement,content}
/api/store-review[/config]   /api/native-update-flag
/config.json                 /privy
```

`/privy` menandakan **embedded wallet via Privy** — pihak ketiga yang membuat & mengelola
wallet di dalam aplikasi. Ini informasi penting untuk klaim "non-custodial": kunci dibuat
di perangkat, tapi provisioning-nya lewat Privy.

### Hermes bundle
| Metrik | Nilai |
|---|---|
| Versi HBC | 96 |
| Fungsi | **142.518** |
| String | **307.758** |
| Identifier | 88.368 |
| Source hash | `2d877cc7…` |

Pencarian `sk_live`, `sk_test`, `service_role`, `private_key` di seluruh disassembly:
**tidak ditemukan**. Yang muncul hanya fungsi pustaka standar (`mnemonicToSeed`,
`mnemonicToAccount`, `mnemonicToEntropy` — dari viem/ethers).
