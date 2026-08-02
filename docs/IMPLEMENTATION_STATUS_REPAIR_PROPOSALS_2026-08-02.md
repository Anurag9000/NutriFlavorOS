# NutriFlavorOS Repair Proposal Status — Historical Milestone

**Original milestone date:** 2026-08-02  
**Historical boundary:** migration `20260802_0016`, API `0.13.0`, OpenAPI `2026-08-02.7`  
**Superseded by:** migration `20260802_0018`, API `0.15.1`, OpenAPI `2026-08-02.11`

This file is retained as historical evidence of the earlier **proposal-only** milestone. It is not the current implementation status. The authoritative current ledger is `docs/IMPLEMENTATION_STATUS.md`.

## What this milestone established

At the proposal-only boundary, NutriFlavorOS had:

- advisory deterministic minimal-change repair;
- immutable server-recomputed repair proposals;
- exact source schedule, target calendar, occurrence/profile, and repair hashes;
- complete-only proposal persistence;
- exact creation/rejection idempotency;
- append-only proposal events;
- read-time staleness and tamper detection;
- rejection of ordinary repair after source task execution began;
- protected advisory and proposal-review interfaces;
- explicit non-acceptance/non-persistence computation fields.

At that historical point, proposal acceptance and replacement-draft creation were deliberately absent.

## Implemented after this milestone

The current lifecycle now adds:

- migration `20260802_0017` for immutable acceptance evidence and repair-derived schedule provenance;
- deterministic method-aware replay for original and repaired schedules;
- exact changed-task acknowledgement;
- acceptance that creates exactly one new `draft` without mutating the source;
- append-only proposal-acceptance and schedule-creation events;
- locked cross-record evidence validation;
- separate method-aware owner approval;
- migration `20260802_0018` enforcing one accepted replacement per source schedule/version;
- PostgreSQL duplicate/competing acceptance and source-execution race coverage;
- source task-execution blocking after accepted replacement;
- task-execution eligibility evidence and proactive frontend gating;
- per-schedule derivation evidence and household derivation coverage;
- protected Repair Proposals and Schedule Derivation routes;
- synchronized API/OpenAPI/schema/documentation release identity.

## Current lifecycle summary

1. Advisory repair computation remains non-persistent.
2. Proposal creation remains non-persistent with respect to schedules.
3. Explicit acceptance may create one new draft after exact acknowledgement and replay.
4. Only one accepted replacement may exist for a source schedule/version.
5. Owner approval remains separate and requires locked acceptance evidence plus replay.
6. Task execution remains separate.
7. A replaced source remains readable but cannot receive new execution events or completion.
8. Schedule completion remains guarded by explicit task terminality.

## Still-current safety boundaries

- Computation never reports itself accepted or persisted.
- Proposal creation never creates a schedule.
- Acceptance never approves, executes, or completes a schedule.
- Approval never implies task execution.
- Task events are explicit user-entered evidence, not sensor observation.
- No clinical, allergy, medication, contamination, temperature, presence, appliance, or food-safety claim is made.
- No hosted green-build claim is made without observing the exact current workflow and artifacts.

## Current references

- `README.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `docs/ROADMAP.md`
- `docs/PREPARATION_REPAIR.md`
- `docs/PREPARATION_REPAIR_PROPOSALS.md`
- `docs/PREPARATION_REPAIR_ACCEPTANCE.md`
- `docs/PREPARATION_REPAIR_EXECUTION_BOUNDARY.md`
- `docs/PREPARATION_SCHEDULE_DERIVATION.md`
