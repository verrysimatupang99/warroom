# Trading Floor — dokumen audit 23 Oktober 2026

Hasil sesi "Trading Floor": satu Chief Orchestrator (`orchestrator`) memerintah empat
spesialis pasar (`crypto`, `forex`, `idx`, `polymarket`). Setiap agen bekerja di worktree
sendiri dan menghasilkan audit pasar + audit codebase.

## Peta berkas

| Berkas | Isi |
|---|---|
| `CONSENSUS_RECOMMENDATIONS.md` | Konsensus terpadu + matriks alokasi modal. Status: **NO-GO live penuh**. |
| `<pasar>_market_audit.md` / `polymarket_audit.md` | Audit per pasar: kondisi pasar + kesiapan codebase + vektor risiko. |
| `docs/trading-floor/directive-<pasar>.json` | Direktif orkestrator per pasar (mandat, model utama/validator, deliverables). |
| `docs/MACRO_ORCHESTRATION_DIRECTIVE.md` | Tesis makro lintas aset. |
| `docs/MARKET_SPECIALISTS_AUDIT.md` | Status kesiapan tiap workspace spesialis. |
| `.agent_chat_history.json` | Riwayat chat agen (append-only, digabung saat merge branch). |

## Mengapa direktif diberi nama per pasar

Semula keempat worktree menaruh `ORCHESTRATOR_DIRECTIVE.json` di **root repo yang sama**,
jadi keempat berkas itu bertabrakan saat branch di-merge ke `main` (konflik add/add) —
padahal isinya berbeda: satu direktif per pasar. Karena itu berkasnya dipindah ke
`docs/trading-floor/directive-<pasar>.json` supaya keempatnya bisa hidup berdampingan.

## Tesis utama

**Alpha–Execution Divergence** — kualitas deteksi sinyal (alpha) solid di keempat pasar,
tetapi edge terkikis di lapisan eksekusi:

- **Polymarket**: win rate semu 81,8% tetapi PnL −$6,40 (payoff biner asimetris + fee taker).
- **Forex (XAUUSD)**: tren H1 bearish bersih, tetapi buffer breakeven $0,30 vs spread rollover
  Exness 12–25 pts → risiko *phantom stop-out*.
- **Crypto**: fail-closed terkunci (izin/kunci/siap = False); butuh Z-score adaptif untuk
  rasio taker dan filter likuiditas DEX yang lebih ketat.
- **IDX**: bandarmologi + foreign flow lulus 39 unit test; tetap **Cap Fase 2**
  (sinyal untuk eksekusi manual, bukan auto-order).

## Status gate live saat dokumen ini disimpan

A1/A2 lolos angkanya, tetapi **A3/A4/A5 belum** dan `qa_viewer` belum dirotasi, jadi
keputusan owner tetap **NO-GO**. Lihat `docs/checklist-go-nogo-live.md`.
