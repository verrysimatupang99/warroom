# services/llm — War Room LLM gateway (P3)

Kontrak: `../live-trading/docs/blueprint/04-lapisan-ai.md`.

## Prinsip yang dikodekan

1. **Angka tidak pernah lahir dari LLM.** Nilai diinjeksi sebagai blok `FAKTA` bernomor
   (`F1: n=1175, win=79.0% (fact_id=101)`); keluaran yang menyebut angka tanpa `fact_id`
   ditolak, dan `fact_id` yang tidak ada di DB juga ditolak (`warroom_llm.pipeline`).
2. **Gagal = gagal.** Provider mati/timeout/JSON tak valid/keluaran tak ber-grounding →
   `insufficient` tanpa satu digit pun, bukan tebakan.
3. **Setiap panggilan tercatat** di tabel `llm_calls` (role, provider, model, prompt_version,
   tokens, cost, latency, ok, fallback_from, error_code, result_hash, fact_ids).
4. **Konten eksternal = data, bukan perintah.** Semua dokumen dibungkus penanda
   `<<<UNTRUSTED_DATA ...>>>` dan hanya masuk pesan `user`, tidak pernah `system`.
5. **Scrub kredensial** pada prompt keluar maupun jawaban; hanya nama env var yang disebut.

## Peta modul

| Modul | Isi |
|---|---|
| `config.py` | muat `/etc/warroom/llm.json` (env `WARROOM_LLM_CONFIG`), rantai primary→fallback |
| `providers.py` | klien HTTP OpenAI-compatible, circuit breaker, cache TTL |
| `gateway.py` | orkestrasi satu panggilan: fakta → anggaran → cache → rantai provider → audit |
| `prompts.py` | registry prompt berkas `prompts/*.json` + tabel `prompts` (append-only) |
| `pipeline.py` | scrub → JSON → skema → verifikasi `fact_id` → pemeriksa angka |
| `schemas.py` | model pydantic strict per peran (narrator, verifier, anomaly) |
| `facts.py` | `FactRef`, blok FAKTA, deteksi klaim angka tanpa kutipan |
| `scrub.py` / `untrusted.py` | penghapusan kredensial + pembungkus anti prompt-injection |
| `evals.py` | eval harness deterministik atas golden set per peran |

## Menjalankan

```bash
cd ~/warroom
uv run ruff check .
uv run pytest services/llm/tests -q

# eval harness (golden set ≥20 kasus/peran)
uv run python -c "from warroom_llm.evals import run_suite; print(run_suite('services/llm/golden'))"
```

Fixture (berkas prompt + golden) dilahirkan ulang secara deterministik oleh
`services/llm/tools/generate_fixtures.py`; skema diambil langsung dari model pydantic.
