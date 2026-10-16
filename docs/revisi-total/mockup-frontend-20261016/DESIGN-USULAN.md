# War Room - Gaya Visual Baru (USULAN DRAFT)

> Status: **USULAN, menunggu keputusan pemilik.** Arah ini digenerate agen atas perintah
> sesi 16 Okt 2026 ("lu boleh propose gaya baru yang rubah UI/UX atau Frontend total").
>
> **Peringatan jujur (sistem antislop):** arah desain buatan agen cenderung condong ke
> selera default AI. Ini draft, bukan hasil final, sampai pemilik menyetujuinya.
>
> **Catatan override:** PRODUCT.md menyatakan tema `app.css` mengikat. Pernyataan itu
> sengaja dilewati atas instruksi sesi. Keputusan final kembali ke pemilik.
> Yang TIDAK dilewati: aturan angka jujur (tanpa statistik karangan, kosong = `-`,
> tag terukur/belum-terverifikasi), keterbacaan mobile, dan status tanpa kode warna saja.

## Design Read

> Control-room app untuk satu operator, dibuka berkali-kali sehari dari layar kecil:
> bahasa visual "ops ledger" gelap dengan satu lampu amber. Dial **ENERGY 2 / RHYTHM 2 / MOTION 1.**

## Keputusan + alasan (R-31, satu baris per keputusan)

| Keputusan | Alasan |
|---|---|
| Dasar graphite gelap berlapis (#101214 / #17191C) | Warisan preferensi pemilik "gelap saja" (6 Okt) dengan family lebih netral, bukan biru |
| Aksen tunggal AMBER #F5B83D | Identitas "lampu war room"; jadi kontras mint yang menyala di layar gelap |
| Mint #34E39A khusus nilai positif TERUKUR | Warna semantik dengan makna tunggal, membatasi cara pakai |
| Merah #FF6B6B hanya risiko, selalu + glyph + kata | PRODUCT.md: untung/rugi tidak boleh bergantung warna saja |
| IBM Plex Sans + IBM Plex Mono untuk semua angka | Angka tabular jadi isi utama; suara "manual operasi", bukan font default trio |
| Radius 6px + border hairline + flat | Card terbaca sebagai dokumen berbatas, bukan floating-slop; hanya satu elemen melayang |
| Track bar proporsi (track + fill) | Komponen warisan lama yang sudah teruji membandingkan besaran ber-maksimum |
| Motif identitas: honesty-tag di setiap angka | Terjemahan `catatan_kejujuran` (TERUKUR solid / BELUM TERVERIFIKASI dashed + sumber) - motif pembeda produk |
| Bottom nav 5 item kompak + "Lainnya", target 44px | PRODUCT.md: sering dibuka dari layar kecil |
| Tanpa gradient/glassmorphism/glow | Terminal data tidak butuh dekorasi; fokus harus ke angka |

## Struktur layout (perubahan total layout)

1. Halaman dibangun dari **kartu keputusan** (satu kesimpulan/kartu), bukan dinding widget
   maupun bento-grid. Home dibuka pita keputusan lebar berisi satu kalimat jawaban
   untuk hari ini: berapa pasar layak, berapa yang menunggu.
2. Setiap halaman punya **satu fokus** (band/titik keputusan), sisanya mengikuti hierarki.
3. Label bagian pakai eyebrow mono uppercase (mewarisi disiplin visual lama).
4. Status yang menjaga uang (kill switch, mode paper/live) memakai glyph + kata + warna.

## Verifikasi (R-35, mode inspeksi-kode)

Sesi ini tidak punya kemampuan melihat gambar, поэтому verifikasi dilakukan lewat audit
kode HTML tiap layar (palet, penanda konten, bahasa, silap UI, statistik karangan) -
**14/14 OK** (satu revisi: marker checkmark dekoratif di gmgn diganti teks `[OK]`/`[!]`).
PNG unduhan berupa strip full-page skala 512px; referensi penuh di file `.html`
(buka di browser, lebar 390px). Semua angka di mockup berupa angka nyata dari
PRODUCT.md atau `-` + alasan.
