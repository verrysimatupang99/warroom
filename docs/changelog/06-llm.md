# Changelog Sektor 06 — LLM & Kecerdasan Buatan

Catatan perubahan pada layanan gateway LLM, router multi-provider, isolasi prompt, dan audit panggilan.

## Perkembangan Terkini

### Ditambahkan
- **Gateway LLM Multi-Provider (`services/llm`)**: Implementasi gateway mandiri dengan router failover berlapis (qonek, kiyara, nutaraline).
- **Circuit Breaker & Fallback**: Proteksi latensi tinggi dan kesalahan 401/429. Jika provider primer tidak merespons dalam ambang batas, permintaan dialihkan ke provider sekunder tanpa menahan eksekusi worker.
- **Audit Panggilan Terstruktur (`llm_calls`)**: Setiap inferensi dicatat lengkap ke tabel audit (model, provider, token input/output, latensi ms, dan status hasil) untuk transparansi biaya dan reproduktibilitas.
- **Ekstraksi Penalaran Beekeeper (ADR-008)**: Parser output terstruktur untuk mengekstrak analisis pasar, sinyal pendukung, dan evaluasi kontradiksi sebelum menghasilkan keputusan.

### Diperbaiki
- Penanganan timeout pada inferensi panjang kini mengembalikan status kesalahan terstruktur daripada exception fatal yang menghentikan loop worker.
- Sanitasi input prompt untuk mencegah injeksi konteks atau kebocoran kredensial sistem.
