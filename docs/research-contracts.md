# Canonical research contracts

Implemented in `packages/core/src/warroom_core/specs.py`.

## HypothesisSpec

Every market hypothesis must declare:

- identity and rule version;
- market and instrument/pool;
- input fields;
- lookahead policy;
- all-in cost policy;
- timezone/session;
- entry, exit, stop, and sizing rules;
- baseline;
- split/walk-forward identifier;
- population;
- invalidation condition.

An incomplete hypothesis is rejected at construction time. Missing invalidation is never silently defaulted.

## ExecutionSpec

Every paper/shadow execution contract must declare:

- executable entry and exit price rules;
- stop and time-stop;
- fee, slippage, latency, and fill/no-fill policies;
- risk budget and sizing rule;
- no-trade conditions;
- venue, mode, and timezone-aware `as_of` timestamp.

`live` is rejected by this contract. Live capability remains a separate owner-granted runtime path and is still NO-GO.

## Usage rule

Adapters may serialize these dataclasses into API/OpenAPI payloads, but they must not weaken validation or invent defaults. The next step is to persist these specs beside research artifacts and require them before an evaluator can enter `eligible` status.
