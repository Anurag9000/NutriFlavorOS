# NutriFlavorOS Repair Proposal Release Status

**Status date:** 2026-08-02  
**Authoritative branch:** `main`  
**Database migration head:** `20260802_0016`  
**API version:** `0.13.0`  
**OpenAPI release contract:** `2026-08-02.7`

This document is an additive status continuation for the preparation-repair milestone. Where an older status document still names migration `20260802_0014`, API `0.12.1`, or OpenAPI contract `2026-08-02.6`, this continuation is the newer source for the repair-proposal release boundary until the consolidated ledger is rewritten atomically.

## Implemented

### Advisory repair computation

- strict previous request, complete previous deterministic response, and revised request;
- deterministic greedy minimal-change repair and bounded exact comparison;
- immutable-task signatures, pinned dependency closure, revised deadline/window/capacity checks, and structured conflicts;
- complete-only default with explicit partial mode for computation;
- preserved, moved, added, removed, and unresolved outcome partitions;
- objective/search diagnostics and canonical hashes;
- authenticated computation endpoint and strict offline CLI;
- enforced `requires_human_acceptance=true`, `accepted=false`, and `persistence_performed=false` boundary;
- protected advisory review page with exact source, revised request, immutable selection, comparison ledger, acknowledgements, and local-only export.

### Immutable repair proposals

- migration-backed `preparation_repair_proposals` and append-only `preparation_repair_proposal_events`;
- exact household/idempotency-key uniqueness and full request fingerprints;
- distinct review records for distinct idempotency keys, even when semantic hashes match;
- indexed semantic source/calendar/request/response identity for evidence and analysis;
- server-authoritative recomputation instead of trusting a client repair result;
- exact source schedule ID/version/hash/request hash;
- exact active reviewed target calendar ID/hash;
- approved source-plan revalidation where a plan link exists;
- retained occurrence/profile provenance validation;
- complete-only proposal creation;
- persisted repair request/result payloads and SHA-256 hashes;
- explicit required acknowledgement task IDs;
- viewer reads and event history; editor/owner creation and rejection;
- optimistic proposal versions, exact event idempotency, and mandatory rejection reasons;
- tamper detection for the persisted nested result and hash columns;
- read-time staleness for source schedule, source plan, target calendar, proposal status, and task-execution history;
- rejection of proposal creation after any task-execution event;
- mandatory proposal response fields `accepted=false` and `schedule_persistence_performed=false`;
- authenticated OpenAPI paths for create/list/get/events/reject;
- no accept, approve, persist, complete, or execute proposal endpoint.

### Configured verification

- exact migration head and runtime required-table verification;
- fresh SQLite migration from an empty database;
- ORM/Alembic uniqueness, constraint, hash, and index contract validation;
- generated OpenAPI release validation;
- authoritative creation-service import/call enforcement;
- execution-history boundary validation;
- service/API/idempotency/staleness/tamper/rejection tests;
- focused frontend type-check and advisory review tests;
- retained preparation-repair benchmark report.

The exact latest hosted runs and retained artifacts have not been observed through the available connector, so this document makes no green-build claim.

## Deliberately not implemented

### Accepted repaired draft

A proposal cannot yet create an accepted replacement draft. Existing schedule approval replays the original deterministic scheduler, whereas repair emits a distinct deterministic repair method. Persisting a repaired draft before method-aware replay would create a record that cannot satisfy the current approval contract.

Accepted-draft persistence remains blocked until these are implemented together:

1. explicit acknowledgement of every required changed task;
2. exact source proposal/version/hash checks;
3. source schedule, plan, calendar, profile, occurrence, and execution-history revalidation;
4. method-aware replay for original and repaired schedules;
5. exact acceptance idempotency and PostgreSQL concurrency behavior;
6. an immutable accepted-draft link retaining all source and result hashes;
7. a new draft rather than mutation of the source schedule;
8. append-only proposal acceptance and schedule-creation events;
9. separate owner approval;
10. separate task execution and guarded completion.

### Execution-aware repair

Schedules with task execution history are currently rejected as repair sources. A future execution-aware engine must preserve completed/skipped work, confirmed starts, dependency history, optimistic versions, and append-only evidence as immutable facts.

## Immediate continuation order

1. Observe and close the exact latest hosted workflows.
2. Add PostgreSQL races for proposal creation, duplicate key reuse, rejection, calendar supersession, source mutation, and execution onset.
3. Implement method-aware replay and accepted-draft persistence.
4. Add protected proposal history/rejection UI and later explicit acceptance UI.
5. Add authenticated Playwright/PostgreSQL and accessibility evidence.
6. Finish authoritative task-terminal completion migration.
7. Implement execution-aware and joint meal/preparation repair.
8. Add larger-neighborhood/relaxation methods, conflict explanations, and representative-scale benchmarks.

See:

- `docs/PREPARATION_REPAIR.md`;
- `docs/PREPARATION_REPAIR_PROPOSALS.md`;
- `docs/EXHAUSTIVE_AUDIT_2026-08-02_REPAIR_CONTINUATION.md`;
- `docs/IMPLEMENTATION_STATUS.md`;
- `docs/ROADMAP.md`.
