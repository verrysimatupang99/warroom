# Analisa REA — TRUE: AI Market Intelligence (`com.truetrading.dev`)

Tanggal: 24 Okt 2026
Status: **sebagian** — APK tidak tersedia publik, analisa mendalam terhalang.

---

## 1. Identitas aplikasi

| Field | Nilai |
|---|---|
| Nama | **TRUE: AI Market Intelligence** |
| Package | `com.truetrading.dev` |
| Developer | **True Labs Limited** |
| Unduhan | 1K+ |
| Rating konten | Everyone |
| Bahasa | 22 bahasa & dialek |

**Klaim kemampuan (dari listing):**
- Harga live, chart profesional dengan **liquidity heatmap**, indikator, volume
- Asisten AI bernama **"Kira"** — membaca chart, flow, dan berita
- Upload chart/dokumen → dijelaskan dalam bahasa awam
- Berita pasar, kalender ekonomi, brief harian
- Watchlist & portofolio dalam satu tampilan
- Academy (materi edukasi)
- **Konektor MCP** — "link Claude, ChatGPT, Perplexity, Cursor ke TRUE"
- Non-kustodial: "TRUE never holds your assets", wallet Solana (Phantom/Solflare/Backpack/WalletConnect)

---

## 2. Deklarasi Data Safety (dari Play)

| Item | Nilai |
|---|---|
| Data dibagikan ke pihak ketiga | **Personal info + Financial info** |
| Data dikumpulkan | **"No data collected"** |
| Enkripsi transit | Ya |
| Bisa minta hapus data | Ya |

⚠️ **Dua baris pertama saling bertentangan** seperti ditampilkan. Ini pola umum pada
formulir Data Safety Google (bagian "dikumpulkan" vs "dibagikan" diisi terpisah), tapi
tetap layak dikonfirmasi ke developer — bukan temuan definitif.

---

## 3. Permukaan yang berhasil diperiksa

### MCP endpoint — AUTENTIKASI DITEGAKKAN ✅

```
POST https://app.truefinance.ai/api/v1/mcp
Content-Type: application/json
{"jsonrpc":"2.0","id":1,"method":"initialize",...}

→ HTTP 401
{"jsonrpc":"2.0","error":{"code":-32001,"message":"missing_token"}}
```

Endpoint publik yang didokumentasikan ("talk to the public MCP server with no install")
ternyata **mewajibkan token**. Tidak ada `tools/list` yang bisa dienumerasi tanpa kredensial.

Header yang terlihat:
- `content-type: application/json; charset=utf-8`
- `x-content-type-options: nosniff`
- `access-control-allow-headers: Content-Type, Authorization, X-Registration-Attempt-Id, X-Registration-Selected-Button`

**Catatan:** dokumentasi menyebut "public MCP server ... with no install" — yang benar
adalah tanpa instalasi *software*, bukan tanpa autentikasi. Perbedaan ini penting agar
tidak salah paham soal eksposur.

### Infrastruktur terkait
| Host | Fungsi |
|---|---|
| `app.truefinance.ai` | aplikasi web + MCP endpoint |
| `docs.truefinance.ai` | dokumentasi developer |
| `truefinance.ai` | situs pemasaran |

Dokumentasi developer mencakup: Trading API (keys, HMAC, orders), Realtime API,
WebSocket, Orders & Signing, Rate Limits, Security & Custody.

---

## 4. Yang menghalangi analisa lebih dalam

| Kebutuhan | Status | Dampak |
|---|---|---|
| **APK** | ❌ tidak ada di mirror publik | Tidak bisa `inspect_android_package` |
| `adb` + perangkat | ❌ adb tidak terpasang, tidak ada device | Tidak bisa tarik APK dari perangkat |
| `jadx` + JDK | ❌ jadx tidak terpasang (JDK ada) | REA butuh JADX MCP JAR |
| Chrome/Chromium lokal | ❌ tidak terpasang | REA `inspect_web_page` butuh CDP loopback |
| Token MCP | ❌ tidak ada | Tidak bisa enumerasi tool MCP |

### Hasil percobaan unduh APK
| Sumber | Hasil |
|---|---|
| `d.apkpure.com` | **403** |
| `apkpure.com/...` | **410 Gone** |
| `apkpure.net/...` | **410 Gone** |
| `apkmirror.com` (pencarian) | **tidak ada listing** untuk package ini |
| `apkcombo.com` / `apkcombo.app` | **tidak terjangkau** (000) |
| `apk.support` | **tidak terjangkau** (000) |

Kesimpulan: APK **tidak tersedia** lewat jalur publik dari server ini. Kemungkinan
karena aplikasi masih baru (1K+ unduhan) atau dibatasi per wilayah.

---

## 5. Cara melanjutkan

| Opsi | Yang perlu Anda lakukan | Yang bisa saya hasilkan |
|---|---|---|
| **A — Kirim APK** | Ekstrak dari HP (mis. aplikasi "APK Extractor") lalu unggah | Manifest lengkap, permission, daftar kelas, endpoint API yang di-hardcode, SDK pihak ketiga, cek tracker |
| **B — Token MCP read-only** | Buat dari app TRUE | Enumerasi `tools/list`, skema input, cek tool mana yang butuh auth, audit permukaan MCP |
| **C — Izinkan saya pasang tool** | Konfirmasi | `jadx` + Chromium (~200 MB) lalu analisa bundle JS web app |

Dari ketiganya, **B paling cepat dan paling aman** — tidak perlu memasang apa pun, dan
MCP adalah permukaan yang paling relevan untuk aplikasi berbasis AI ini.

---

## 6. Catatan metodologis

Semua yang dilakukan di sini bersifat **pasif dan read-only**:
- Membaca halaman Play Store publik
- Membaca dokumentasi developer publik
- Satu permintaan `initialize` ke endpoint MCP publik (ditolak 401)

Tidak ada upaya melewati autentikasi, tidak ada eksploitasi, tidak ada pengambilan data
pengguna. Analisa APK lebih dalam menunggu berkasnya tersedia.
