# War Room — gap assessment terhadap standar senior

Tanggal: 2026-10-08 UTC
Basis: inspeksi repository `/home/admin/warroom`, CI config, API contract, dan standar kerja pada dokumen `standar-kerja-war-room-engineering-trading.md`.

## Cara membaca

- **Hijau**: ada implementasi dan bukti test/operasional.
- **Kuning**: sebagian ada, tetapi belum menjadi kontrak atau belum diverifikasi penuh.
- **Merah**: gap yang dapat membuat angka, keamanan, atau release menyesatkan.

## Engineering

### Discovery dan governance

| Area | Status | Bukti / gap | Prioritas |
|---|---|---|---|
| Scope dan decision rights | Hijau | `docs/sdlc-war-room.md`, `AGENTS.md` | maintain |
| Paper/live separation | Hijau-kuning | UI/API/gate menandai PAPER; live grant tetap dikunci | P1: machine-check end-to-end |
| Domain ownership | Hijau-kuning | domain `live-trading` → worker facts → API → web | P1: publish contract formal |
| Acceptance criteria | Kuning | ada progress/runbook/test, tetapi belum satu template per feature | P2 |
| Risk register | Kuning | ada dokumen dan gate, belum satu register canonical | P2 |

### Frontend

| Area | Status | Bukti / gap | Prioritas |
|---|---|---|---|
| Design tokens | Hijau | token lint + `app.css` source | maintain |
| Canonical verdict | Hijau | UI merender verdict backend | maintain |
| Empty/unknown/freshness states | Hijau-kuning | `—`, source state, loading shell, stale labels | P1: audit semua route untuk consistency |
| Accessibility semantics | Hijau-kuning | `main`, headings, names diuji browser; keyboard/focus belum menjadi automated gate | P1 |
| Performance | Kuning | build lulus; belum ada budget/Lighthouse/real-user metric gate | P1 |
| Responsive QA | Kuning | desktop/mobile evidence ada; belum ada automated viewport acceptance suite | P1 |
| Domain logic in UI | Hijau-kuning | mayoritas read-only; Home masih memiliki aggregation/presentation branching | P1: keep only presentation derivation |

### Backend/API

| Area | Status | Bukti / gap | Prioritas |
|---|---|---|---|
| OpenAPI 3.1 | Hijau-kuning | `contracts/openapi.json` tersedia dan API FastAPI menghasilkan schema | P1: CI diff contract |
| Authn | Hijau | cookie session, expiry, revoke, scrypt, optional TOTP | maintain |
| RBAC | Hijau-kuning | viewer/operator/owner tests; production multi-role test account belum ada | P1 |
| IDOR/object authorization | Kuning | route-level checks kuat; negative object tests perlu diperluas | P1 |
| Input validation | Hijau-kuning | FastAPI schemas/path validation; security fuzz/property tests belum luas | P2 |
| Rate limits | Hijau-kuning | login/verifier/narrate limits ada; global per-IP/distributed limiter belum ada | P1 bila multi-instance |
| Idempotency | Kuning | facts append-only dan event flow; write endpoint idempotency contract belum menyeluruh | P1 |
| Provenance | Hijau | facts membawa source/time/TTL/hash; verification_state perlu diseragamkan | P1 |
| Audit trail | Hijau-kuning | events/audit models ada; audit coverage tiap policy mutation perlu inventory | P1 |

### Security/operations

| Area | Status | Bukti / gap | Prioritas |
|---|---|---|---|
| CSP | Hijau | SvelteKit single enforce policy; duplicate nginx policy sudah dihapus | maintain |
| Security headers | Hijau | HSTS, XFO, nosniff, Permissions-Policy, COOP/CORP | maintain |
| Secret scanning | Hijau-kuning | CI gitleaks; key yang sudah terekspos di chat tetap perlu rotation | P0 operational |
| Backup restore | Kuning | runbook restore ada; restore drill belum menjadi recurring verified job | P1 |
| Deploy/rollback | Hijau | build+restart+asset health gate+backup+rollback | maintain |
| Observability/SLO | Kuning | metrics/SSE/jobs ada; SLO/error-budget/latency dashboards belum formal | P1 |
| Incident response | Hijau-kuning | `ops/runbook-incident.md`; tabletop/restore exercise belum rutin | P2 |
| Supply chain | Kuning | lockfiles + CI; dependency vulnerability policy/SBOM belum menjadi gate | P1 |

## Trading research/execution

### Common research contract

| Item | Status | Gap |
|---|---|---|
| Hypothesis/version | Kuning | narrative exists; canonical schema belum ada di DB/API |
| Observable features | Kuning | per-market collectors ada, definitions tersebar |
| Timestamp/timezone | Kuning | per market ada aturan; belum satu shared contract |
| Entry/exit/stop | Hijau-kuning | paper journals/ledger menyimpan banyak field; semantics tidak seragam |
| Risk sizing | Kuning | 1% baseline dan market-specific logic ada; tail-risk/gap policy belum seragam |
| Fee/slippage | Kuning | IDX/crypto/GMGN berbeda; Forex eksplisit bruto; common cost model belum ada |
| Baseline/counterfactual | Merah-kuning | ada gate/performance; baseline per hypothesis belum wajib di schema |
| Frozen split/walk-forward | Kuning | frozen split gate tersedia, tetapi tidak semua market punya split valid |
| Population/denominator | Hijau-kuning | Evidence page sudah menyebut closed trades; research artifacts belum semua konsisten |
| Invalidation | Kuning | UI/notes menyebut blocked; hypothesis-level invalidation belum wajib |
| Promotion gate | Hijau-kuning | canonical verdict + owner gate; paper-to-live remains NO-GO |

### Per-market readiness

| Market | Yang sudah ada | Blocker utama |
|---|---|---|
| Crypto | SMC candidates, paper ledger, cost-aware evidence, source/freshness | evidence masih insufficient; execution/live separation harus tetap terkunci |
| DEX/GMGN/LP | radar, fee/IL local mark, multi-source price check | on-chain reconciliation dan LP benchmark belum lengkap |
| Forex | journal, TVC structure, risk calculator, explicit BRUTO label | broker fee/spread/fill history; sample terlalu kecil |
| IDX | ledger, bandarmology/BSJP/ARA, model breach disclosure | raw intraday/broker history, gap/tail-risk, invalid stop invariant |
| Polymarket | CLOB/parity, arm separation, paper ledger, resolution-aware surface | frozen split and independent holdout; probability calibration/cost basis |

## Prioritas setelah studi ini

### P0 — keamanan operasional

1. Revoke/rotate exposed Google Stitch API key.
2. Ensure no credential artifact is added to `/home/admin/warroom` or commit history.
3. Keep Tencent, `/opt/polymarket`, and live activation read-only/untouched.

### P1 — kontrak yang membuat sistem senior

1. Buat canonical `HypothesisSpec` dan `ExecutionSpec` yang dipakai semua market.
2. Wajibkan `baseline`, `counterfactual`, `cost_policy`, `population`, `invalidation`, dan `split` sebelum evaluasi berstatus eligible.
3. Tambahkan contract-diff CI untuk `contracts/openapi.json`.
4. Tambahkan automated keyboard/focus/responsive route QA.
5. Tambahkan SLO minimum: API availability, p95 latency, error rate, source stale rate, job failures, SSE liveness.
6. Tambahkan restore drill terjadwal dan bukti read-back.
7. Tambahkan negative object-authorization test matrix.

### P2 — research maturity

1. Pilih satu market/data-complete untuk vertical slice.
2. Jalankan replay frozen + walk-forward + matched baseline.
3. Publikasikan seluruh horizon dan trigger frequency.
4. Archive hypothesis yang gagal sebagai evidence, bukan dihapus.
5. Jangan menambah strategy family baru sebelum slice reproducible.

## Keputusan saat ini

War Room sudah melewati standar dasar production operation untuk single-operator VPS: CI, auth, headers, deploy gate, rollback, source freshness, evidence surface, dan paper/live separation sudah nyata.

Belum setara standar senior penuh pada tiga titik:

1. research contract belum seragam lintas market;
2. SLO/performance/restore/authorization QA belum seluruhnya automated;
3. beberapa market masih menampilkan observasi atau paper evidence yang belum punya baseline/cost/split lengkap.

Implikasi: **layak dilanjutkan sebagai evidence dashboard dan paper research platform; belum layak menjadi live-trading control plane.**
