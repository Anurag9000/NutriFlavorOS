# Preparation Execution-Aware Repair Evidence Boundary

**Status:** implemented evidence foundation; repair-after-execution mutation remains fail-closed.  
**Base OpenAPI contract:** `2026-08-03.2`  
**Execution/repair extension:** `2026-08-07.3`

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

The evidence foundation does **not** yet authorize repair after execution history exists. The following remain required before mutation can be enabled:

1. a first-class execution-aware proposal request carrying the exact expected canonical snapshot hash;
2. a revised-request contract that can change only planned repairable work;
3. explicit normalization of dependencies already satisfied by terminal tasks;
4. a fail-closed policy for in-progress work and descendants blocked by it;
5. replacement persistence containing only future executable work while retaining source execution history unchanged;
6. changed-task and lineage acknowledgement at acceptance;
7. immutable persisted proposal/acceptance provenance for canonical snapshot and lineage hashes;
8. duplicate-execution prevention across a source/replacement chain;
9. an acyclic replacement-descendant invariant;
10. PostgreSQL races for start/complete/skip versus create/accept/approve/supersede;
11. support-export inclusion of snapshot, proposal, acceptance, and lineage identities;
12. frontend visualization that clearly separates historical executed facts from future replacement work.

Until those are implemented and validated, ordinary repair with any execution history remains rejected. No endpoint in this document verifies actual human performance, food safety, appliance state, or clinical suitability.
