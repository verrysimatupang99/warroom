# War Room SDLC Governance

**Status:** active
**Owner:** user / project owner
**Technical-product lead:** Hermes Agent
**Execution mode:** paper-only; live remains NO-GO
**Scope:** `/home/admin/warroom` and its local runtime only
**Last baseline:** 2026-10-07

## 1. SDLC operating model

War Room is managed through a gated Software Development Life Cycle:

1. **Initiation** — define the problem, owner decision, scope, constraints, and success criteria.
2. **Requirements** — write functional, data-integrity, security, UX, and operational requirements.
3. **Architecture and design** — record boundaries, data lineage, state transitions, contracts, and trade-offs in ADRs.
4. **Implementation** — make the smallest change that satisfies the approved requirement.
5. **Verification** — run unit, integration, contract, E2E, accessibility, security, and data-integrity checks appropriate to the change.
6. **Release** — promote only when release gates pass; deploy through the repository runbook.
7. **Operations** — monitor services, freshness, provider health, error distribution, alerts, and data reconciliation.
8. **Review and retirement** — capture evidence, decisions, incidents, technical debt, and safely retire obsolete paths.

No phase is skipped because a change appears small. A UI change that changes a risk label is also a data-integrity change.

## 2. Non-negotiable constraints

- Live trading remains **NO-GO**. Never create or modify the live activation gate.
- Tencent and `/opt/polymarket` remain read-only.
- Secrets never enter source, logs, commits, reports, or chat.
- Gate thresholds, break-even rules, and policy modes are owner decisions; the agent may not change them.
- The UI renders facts; it does not invent or silently recalculate domain numbers.
- `null`, unavailable, stale, frozen, gross, paper, historical, candidate, open, and closed are distinct states.
- Every production-affecting change must have a rollback path and post-change verification.
- One coherent change should produce one commit with evidence in its description.

## 3. Governance and decision rights

| Decision | Owner | Agent role |
|---|---|---|
| Risk appetite, sizing, thresholds, BE policy | User | Explain impact; do not change silently |
| Live promotion | User | Verify gates; never self-promote |
| Architecture and implementation sequence | User approves direction; agent proposes | Design and implement approved work |
| UI/UX composition and copy | Agent proposes; user can override | Implement and verify |
| Deployment/restart | User authorization required | Prepare command/runbook; execute only when authorized |
| External host changes | User authorization required | Read-only inspection unless explicitly scoped |
| Security posture | Shared responsibility | Identify, test safely, remediate with approval |

## 4. Work item contract

Every non-trivial item must state:

- **Problem:** what is wrong or missing.
- **User outcome:** who needs what answer or capability.
- **Scope:** files, services, markets, and environments touched.
- **Acceptance criteria:** observable pass/fail conditions.
- **Risk classification:** UI, data, auth, execution, operations, or mixed.
- **Dependencies:** upstream data, contracts, migrations, or owner decisions.
- **Rollback:** how to revert safely.
- **Evidence:** tests, browser observations, headers, logs, or reconciliation output.

## 5. Environment lanes

### Development

- Local code and tests.
- No production state mutation.
- Synthetic fixtures allowed only when visibly labelled as fixtures.

### Verification / staging

- Production-like route and schema.
- Paper mode only.
- Browser QA, contract tests, E2E, accessibility, and security checks.

### Production observation

- Read-only baseline, health, logs, freshness, and rendered UI checks.
- No restart, deploy, configuration change, export, trade, or state mutation without explicit authorization.

### Live execution

- **Blocked.** Requires owner decision, frozen statistical split, completed risk controls, reconciliation evidence, staged promotion, and explicit activation approval.

## 6. Required quality gates

### Definition of Ready

- Requirement and decision owner identified.
- Current behavior measured.
- Dataset population and denominator named.
- Source, freshness, fees, slippage, and execution mode known.
- Acceptance criteria and rollback written.

### Definition of Done

- Implementation complete; no placeholder behavior.
- Unit and integration tests pass.
- Contract types and API behavior agree.
- UI states covered: loading, empty, stale, error, blocked, paper, historical, and normal.
- Accessibility and responsive behavior checked for UI changes.
- Security impact reviewed for auth/data changes.
- Evidence captured and linked from the work item.
- Runtime/source drift checked before any restart or release claim.

### Release gate

- `uv run ruff check .`
- `uv run pytest -q`
- web tests from `apps/web`
- Playwright E2E when the change affects routes, auth, SSE, or interaction
- `bash ops/ci-local.sh` for release candidates
- gitleaks when touching examples, config, or credential-adjacent files
- production health and rendered smoke check after authorized deployment
- rollback path confirmed

A skipped check is not a pass; it is an explicit release blocker or documented exception approved by the owner.

## 7. Current takeover baseline

### Runtime observed

- nginx: running
- PostgreSQL 16: running
- `warroom-api`: running
- `warroom-web`: running
- `warroom-worker`: running
- public HTTPS endpoint: available
- unauthenticated API boundary: returns `401`
- current repository has uncommitted screenshot evidence files; do not treat the tree as clean

### Current architecture

```text
market/domain sources
        ↓
live-trading domain + worker collectors
        ↓
facts / ledgers / freshness / gate evidence
        ↓
FastAPI REST + SSE + auth/RBAC
        ↓
SvelteKit rendering and policy labels
        ↓
operator dashboard + notifier
```

### Known owner decisions still blocking promotion

- Live remains NO-GO.
- Frozen statistical split and gate policy require owner decision.
- Tencent stays read-only.
- Provider ordering and policy remain owner-controlled.

## 8. Initial backlog

### P0 — correctness and safety

- Canonicalize one backend verdict per market: signal, evidence, risk, execution, promotion, and blocked reason.
- Make Polymarket promotion status impossible to show as proven while split is unfrozen.
- Keep IDX model breach explicit and prevent paper loss from being interpreted as a hard loss cap.
- Reconcile candidate, evaluated, open, and closed populations with explicit metadata.

### P1 — product clarity and operational truth

- Create a control-center summary separating candidate signals, promotable opportunities, open paper positions, stale sources, and system failures.
- Add source health states beyond `fresh/stale`: paused, frozen, degraded, unreachable, and last successful change.
- Make gross/net, paper/live, historical/current, and fee/slippage policy first-class data labels.
- Stabilize authenticated browser QA and session lifecycle tests.

### P2 — hardening and polish

- Move CSP from Report-Only to enforce after violation reports are clean.
- Verify role/object authorization, export boundaries, and SSE topic isolation with test roles.
- Consolidate OpenAPI-generated frontend types and add contract tests.
- Finish SVG icon, 44px interaction target, responsive, and loading-state consistency.

## 9. Change protocol

Before editing:

1. Check git status and current runtime/source relationship.
2. Read the relevant ADR, product requirement, and runbook.
3. Create or update the work item with acceptance criteria.
4. Take a checkpoint before risky or broad changes.
5. Implement in small increments.
6. Run the narrowest relevant test after each increment.
7. Run the full release gate before claiming completion.
8. Record what changed, what was verified, what was not changed, and remaining risk.

## 10. Reporting format

Every takeover update uses:

- **Phase:** SDLC phase and work item.
- **Changed:** files/services or observations.
- **Verified:** exact command or browser evidence.
- **Blocked:** owner decision, environment, or missing evidence.
- **Next gate:** the next acceptance criterion.

This document governs execution unless the owner explicitly changes it.
