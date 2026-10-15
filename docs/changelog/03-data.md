# Changelog Sektor 03 — Data & Ingestion

Catatan perubahan pada pipa data pasar, audit kesegaran data, dan penanganan deduplikasi sinyal.

## Perkembangan Terkini

### Ditambahkan
- **Audit Kesegaran Sumber (`audit_kesegaran`)**: Job berkala memetakan status kesehatan seluruh fakta, umur data maksimal, dan daftar TTL per sumber di journald (`freshness.checked.audit_sumber`).
- **Peringkat Sumber Basi**: Pelacakan otomatis frekuensi data basi pada jendela 7 hari untuk mengidentifikasi kegagalan koneksi data provider secara objektif.

### Diperbaiki
- **Deduplikasi Penerbitan Sinyal (`handler_signal_sync`)**: Menggunakan kunci deduplikasi `source=path#ts` sehingga sinyal yang sudah pernah diterbitkan tidak lagi ditulis ulang dan tidak memicu banjir notifikasi alert duplikat.
