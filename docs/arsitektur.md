# Arsitektur War Room

Gambaran aliran data end-to-end. Detail tiap komponen ada di README paket/layanan masing-masing.

## Aliran data utama

```mermaid
flowchart LR
    subgraph Sumber["Sumber data"]
        MT5["MetaTrader 5\n(feed forex/gold)"]
        CEX["Bursa & on-chain\n(OKX, GMGN)"]
        IDX["IDX / Radar rantai\n(lokal)"]
        POLY["Polymarket\n(baca-saja)"]
        NEWS["Berita & kalender"]
    end

    subgraph Inti["Inti platform"]
        WORKER["services/worker\nJob runner: ingest, hitung,\nterbitkan fakta"]
        CORE["packages/core\nModel DB, gate statistik,\ndata splits, retensi"]
        LT["packages/live-trading\nMesin analisis multi-pasar,\nCLI lt, kalkulator risiko"]
        LLM["services/llm\nGateway LLM ber-grounding\nfakta + circuit breaker"]
    end

    subgraph Penyajian["Penyajian"]
        API["services/api\nFastAPI :8800\nREST + SSE, auth, RBAC"]
        WEB["apps/web\nSvelteKit 2\nSerene Capital"]
        NOTIFY["services/notifier\nTelegram Hermes"]
    end

    DB[("PostgreSQL\n+ WAL arsip")]

    MT5 --> WORKER
    CEX --> WORKER
    IDX --> WORKER
    POLY --> WORKER
    NEWS --> WORKER
    WORKER --> CORE --> DB
    WORKER --> DB
    LT --> DB
    DB --> API
    CORE --> LLM
    LLM --> API
    API --> WEB
    API --> NOTIFY
    WORKER --> NOTIFY
```

## Strategi plug-and-play (PnP)

Strategi/EA eksternal tidak pernah menyentuh kode platform. Loader memuat file `.py`
dari `~/.warroom/strategies` (atau `WARROOM_STRATEGY_PATH`) saat proses start.

```mermaid
flowchart LR
    subgraph Eksternal["Di luar repo (milik owner)"]
        P1["ea_scalper_v1.py"]
        P2["ea_laya_regime.py"]
        P3["ea_apa_saja.py"]
    end

    subgraph Platform["Platform (tidak berubah)"]
        LOADER["strategy_plugins.py\nfail-closed loader"]
        REG["pnp_registry\nregister() ≠ aktivasi"]
        BASE["BaseStrategy\nkontrak evaluate()"]
        ENG["Mesin eksekusi\npaper / gate live"]
    end

    P1 & P2 & P3 --> LOADER --> REG
    REG --> ENG
    BASE -. kontrak .-> P1
```

Sifat penting:

- **Fail-closed**: file tanpa `STRATEGY`, class yang salah, atau error eksekusi →
  `PluginStrategyError`; tidak ada registrasi parsial diam-diam.
- **Registrasi ≠ aktivasi**: `pnp_registry.register()` hanya mendaftar; strategi aktif
  diubah eksplisit via `pnp_registry.set_active_strategy(key)`.
- File berawalan `_` di-skip (boleh dipakai sebagai utilitas bersama).

## Gerbang keselamatan live

Percobaan eksekusi live melewati lapisan berurutan — tidak ada jalur pintas:

```mermaid
flowchart LR
    SIG["Sinyal strategi"] --> G1["Gate statistik\n(packages/core)"]
    G1 --> G2["Gate risiko & biaya\n(kalkulator live-trading)"]
    G2 --> G3["Gate izin owner\n(allowlist dry-run)"]
    G3 --> G4["Paper trade\n(wajib sebelum live)"]
    G4 -->|izin eksplisit| LIVE["Eksekusi live"]
```

Ambang gate dan rumus break-even **hanya boleh diubah manusia (owner)** —
lihat `AGENTS.md`.
