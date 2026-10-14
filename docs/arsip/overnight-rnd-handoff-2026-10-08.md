# Overnight R&D handoff — War Room

**Deadline requested:** 2026-10-09 06:00 WIB  
**Mode:** R&D/paper/research only until every promotion and owner gate passes.

## Objective

Make War Room capable of producing a defensible research result and a staged paper-readiness decision for one data-complete market. Profit is an objective, not a guaranteed outcome. No live order is allowed merely because a result looks profitable.

## Selected vertical slice

Polymarket favorite 0.70–0.95 / Arm B.

Registration:

- `docs/research-polymarket-vertical-slice.md`
- `/tmp/warroom-materi/polymarket-vertical-slice-registration.json`

## Completed platform work

- read-only ResearchRun/ResearchRecord API;
- contract-bound KOS preview;
- RBAC/IDOR tests;
- OpenAPI contract-drift gate;
- staging migration to `f1a2b3c4d5e6`;
- verified restore drill on a separate staging restore database;
- Evidence page contract fingerprint/provenance display;
- authenticated readiness endpoint;
- full Python and web test suites green.

## Overnight execution order

1. Obtain/reuse only sanctioned read-only research dataset access.
2. Enumerate schema, timestamps, resolution, quotes, fills, fees, and outcome fields.
3. If fields are sufficient: create frozen manifest; run replay, baseline, and all-in cost model.
4. If fields are insufficient: publish `blocked_data_access` or `not_auditable`; do not fabricate a result.
5. Publish negative or positive outcome with denominator and evidence status.
6. Do not promote to live. Prepare a paper-shadow decision only if gates pass.
7. IDX proxy/Arjum/KOS remain later phases and separate strategies.

## Hard constraints

- Never guarantee profit or claim cuan before verified execution evidence.
- Never access or modify Tencent.
- Never modify `/opt/polymarket`, live activation, or live trading controls.
- Do not bypass allowlists, Cloudflare, secret boundaries, or DB permissions.
- Never accept credentials in chat or place them in repo/logs.
- Paper/live separation and owner gate remain mandatory.
