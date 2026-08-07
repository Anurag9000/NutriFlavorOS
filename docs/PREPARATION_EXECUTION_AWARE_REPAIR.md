# Preparation Execution-Aware Repair Evidence Boundary

**Status:** execution-aware read/preflight authority implemented; repair-after-execution persistence remains fail-closed.  
**Base OpenAPI contract:** `2026-08-03.2`  
**Execution/repair extension:** `2026-08-07.4`

## Purpose

Execution-aware repair must never rewrite history. A task that has started, completed, or been skipped is an observed execution fact, not a movable scheduling suggestion. NutriFlavorOS therefore separates execution evidence from future repair computation and introduces the authority in stages.

## Canonical execution snapshot

`GET /api/v1/households/{household_id}/preparation-operations/schedules/{schedule_id}/execution-snapshot` returns the canonical mutation-authority snapshot.

Its semantic hash binds:

- source schedule ID and optimistic version;
- latest execution-event ID;
- ordered execution-event count and ledger hash;
- every task's execution state and latest event ID;
- terminal completed/skipped task IDs;
- planned repairable task IDs;
- in-progress task IDs.

`captured_at` is audit metadata and is deliberately excluded from semantic identity, so re-reading unchanged execution state produces the same snapshot hash.

## Rich execution-aware repair frontier

`GET /api/v1/households/{household_id}/preparation-operations/schedules/{schedule_id}/execution-aware-repair-snapshot` is read-only evidence. It performs no repair computation and persists nothing.

The richer projection adds:

- planned start/finish and dependencies;
- confirmed start and terminal evidence;
- terminal reason/evidence type;
- frozen, active, terminal, repairable, ready, and blocked partitions;
- a privacy-preserving event-chain hash that hashes, rather than exposes, idempotency keys;
- explicit limitations and non-mutation flags.

The richer snapshot contains `canonical_execution_snapshot_hash`, and that canonical hash is included in the richer `snapshot_hash` payload. Before a richer snapshot is returned, the service compares both projections task-by-task and fails closed if schedule identity, event identity, task state, latest-event identity, or partitions disagree.

The two uses of “frozen” are intentionally different:

- canonical `frozen_task_ids` are terminal completed/skipped facts;
- richer `frozen_task_ids` are terminal facts plus in-progress work that cannot be moved;
- richer `active_task_ids` exactly match canonical `in_progress_task_ids`;
- richer `terminal_task_ids` exactly match canonical `frozen_task_ids`;
- repairable partitions must match exactly.

A transient inconsistent read returns no mixed frontier evidence.

## Execution-aware proposal preflight

`POST /api/v1/households/{household_id}/preparation-operations/repair-proposals/execution-aware/preflight` is the first-class request boundary for future repair after execution has begun. It still creates no proposal and no schedule.

The request must carry the exact source schedule ID/version/hash, canonical execution snapshot hash, richer execution-aware snapshot hash, target calendar version, a full revised request, and explicit acknowledgements that execution history is immutable, in-progress work will not be moved, and the operation is preflight-only.

Under the household/source serialization boundary, preflight:

- re-reads the exact current canonical/richer execution frontier and fails with `execution_aware_repair_snapshot_changed` on any identity drift;
- requires actual execution history, leaving zero-event sources on ordinary repair;
- requires the source, revised request, and execution snapshot to contain the same task-ID set at this phase;
- keeps the source horizon and granularity fixed because existing execution evidence is expressed in that timebase;
- requires every in-progress and terminal task definition to remain byte-for-byte unchanged;
- derives immutable/frozen task IDs from execution authority rather than trusting caller-supplied immutable IDs;
- treats terminal task dependencies as already satisfied and removes those dependency edges from the normalized future request;
- finds direct and transitive descendants of in-progress work and withholds them from repair computation until their active ancestor becomes terminal;
- emits only the remaining unstarted executable candidate tasks in `normalized_future_request`;
- validates that normalized future request against the exact active reviewed target calendar;
- reports `repair_computation_performed=false`, `proposal_persistence_performed=false`, and `schedule_persistence_performed=false`.

Task additions/removals remain disabled in this phase because their provenance and lineage have not yet crossed a persisted proposal boundary. This is a deliberate fail-closed restriction, not a claim that execution-aware repair is complete.

## Proposal creation and acceptance race authority

Ordinary repair still rejects any source that already has execution history.

For a zero-event ordinary-repair proposal, creation stores immutable execution evidence in the append-only proposal `created` event, including:

- canonical execution snapshot version/hash;
- execution-event ledger hash/count/latest-event ID;
- frozen, repairable, and in-progress partitions.

Guarded acceptance re-reads the canonical execution snapshot under the same household serialization boundary used by task execution. If any execution event or task state changed after proposal creation, acceptance fails with `repair_execution_snapshot_changed` and creates no acceptance row or replacement schedule.

Exact recovery of an acceptance that already committed remains idempotent and does not reinterpret a later source snapshot.

## Accepted source-to-replacement lineage

`GET /api/v1/households/{household_id}/preparation-operations/repair-proposals/{proposal_id}/task-lineage` is available only when that proposal has an accepted replacement draft. Arbitrary schedule-pair comparisons are not authoritative.

Lineage statuses are:

- `preserved`;
- `frozen_by_execution`;
- `shifted`;
- `newly_introduced`;
- `removed_before_execution`;
- `blocked_by_in_progress_predecessor`;
- `superseded_by_replacement`.

The current authoritative derivation rejects supersession while any source task is in progress. Terminal source tasks may not reappear as executable replacement tasks. Every source and replacement task must occur exactly once in the lineage projection.

Each lineage now includes `lineage_hash`, a SHA-256 identity over:

- source schedule ID/version;
- canonical source execution snapshot hash;
- the ordered complete lineage entry set.

Identical lineage evidence hashes identically; any task identity, state, timing, status, or replacement change changes the lineage hash. A supplied hash that disagrees with the evidence fails validation.

## What is deliberately not enabled yet

The read/preflight foundation does **not** yet authorize persisted repair after execution history exists. The following remain required before mutation can be enabled:

1. persisted execution-aware proposal creation from the normalized future request, with method-aware replay and no source mutation;
2. proposal schema/migration fields that bind canonical snapshot, richer frontier, normalized-future-request, and execution-event-ledger identities directly rather than only transient preflight output;
3. explicit provenance for any future introduced or removed planned task before task-set changes are enabled;
4. replacement persistence containing only future executable work while retaining source execution history unchanged;
5. changed-task and lineage acknowledgement at acceptance;
6. immutable persisted acceptance provenance for canonical snapshot and lineage hashes;
7. duplicate-execution prevention across a source/replacement chain;
8. an acyclic replacement-descendant invariant;
9. PostgreSQL races for start/complete/skip versus execution-aware create/accept/approve/supersede;
10. support-export inclusion of snapshot, preflight, proposal, acceptance, and lineage identities;
11. frontend visualization that clearly separates historical executed facts, blocked in-progress descendants, and future replacement work;
12. generated frontend bindings for the execution-aware preflight request/view and all later mutation contracts.

Until those are implemented and validated, ordinary repair with any execution history remains rejected and the execution-aware endpoint remains preflight-only. No endpoint in this document verifies actual human performance, food safety, appliance state, or clinical suitability.
