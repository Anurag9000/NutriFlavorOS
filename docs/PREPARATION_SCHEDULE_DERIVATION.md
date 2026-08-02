# Preparation Schedule Derivation Evidence

## Purpose

Every persisted preparation schedule has an algorithmic origin. NutriFlavorOS distinguishes two reviewed derivation methods:

- `deterministic_dependency_aware_resource_scheduler_v2` — the original deterministic scheduler;
- `deterministic_minimal_change_preparation_repair_v1` — a repaired schedule created only through an accepted repair proposal.

Derivation evidence is read-only provenance. It does not approve, execute, complete, validate food safety, prove human activity, or certify schedule quality.

## Original deterministic schedules

An original schedule must report:

- the original scheduler method;
- its persisted schedule ID, version, status, and schedule hash;
- `evidence_complete = true`;
- null proposal, acceptance, source-schedule, and repair-hash fields.

If an original schedule contains any repair-specific field, the derivation endpoint fails closed with structured `409` evidence rather than silently reclassifying the record.

## Accepted repair schedules

A repair-derived schedule must have a complete cross-record chain:

1. a persisted schedule whose derivation method is the repair method;
2. an exact source repair proposal link and accepted proposal version;
3. an accepted proposal state;
4. one immutable acceptance record linked to the same proposal and created schedule;
5. exact source schedule ID, version, schedule hash, and request hash;
6. exact target reviewed calendar hash;
7. exact repair-request, repair-result, revised-request, and repaired-response hashes;
8. an acknowledgement set exactly matching every required moved, added, removed, or unresolved task;
9. an acceptance actor, timestamp, and nonblank reason.

The derivation read service cross-checks these identities across the proposal, acceptance, and persisted schedule. Missing or contradictory evidence returns a structured `409` and no partial success response.

## Authorized API

Viewer-authorized per-schedule evidence:

`GET /api/v1/households/{household_id}/preparation-operations/schedules/{schedule_id}/derivation`

Viewer-authorized household coverage:

`GET /api/v1/households/{household_id}/preparation-operations/schedule-derivation-coverage`

Both endpoints use household non-disclosure. A schedule outside the requested household is returned as `404` rather than revealing its existence.

## Per-schedule evidence

The evidence response includes:

- schedule identity and status;
- derivation method;
- completeness flag;
- proposal and acceptance identities for repair-derived schedules;
- source schedule identity;
- source schedule/request hashes;
- target calendar hash;
- repair request/result/revised-request/repaired-response hashes;
- acceptance actor, time, and reason;
- structural warnings.

The service performs no database writes, lifecycle transitions, task-execution mutation, or browser-local persistence.

## Household derivation coverage

Coverage describes stored structure across all persisted household schedules. It reports:

- total schedules;
- original-scheduler schedules;
- accepted-repair schedules;
- unknown derivation methods;
- complete and incomplete derivation chains;
- accepted proposal and acceptance-record counts;
- repair-derived drafts and approved schedules;
- repair-derived schedules with task-execution history;
- method counts;
- total derivation coverage ratio;
- repair-to-acceptance-link coverage ratio;
- latest acceptance time;
- explicit structural warnings.

Method counts partition all schedules. Completeness counts independently partition all schedules. Empty denominators produce a ratio of `1.0`, meaning no uncovered stored record exists—not that the product or household has been validated.

## Structural completeness

An original schedule is structurally complete when it uses the original method and has no repair-specific fields.

A repair-derived schedule is structurally complete only when the proposal, acceptance, source schedule identity, target calendar hash, all repair hashes, proposal version, created schedule link, derivation method, and changed-task acknowledgement set agree.

Unknown methods and contradictory evidence are counted as incomplete and surfaced in warnings.

## Frontend inspector

The protected `/preparation/operations/derivation` workspace provides:

- household and persisted-schedule selection;
- household derivation denominators and ratios;
- incomplete-chain warnings;
- original-versus-repair method labeling;
- exact proposal, acceptance, and source schedule identities;
- hash summaries;
- acceptance actor, time, and reason;
- no mutation control.

The typed client exposes only:

- `coverage`;
- `get`.

It exposes no create, accept, approve, execute, complete, update, or delete operation.

## Verification

Configured verification includes:

- strict domain partition validation;
- authenticated generated OpenAPI paths and schemas;
- original-schedule null-repair evidence tests;
- accepted-repair cross-record evidence tests;
- acceptance-tamper failure tests;
- household non-disclosure and authentication tests;
- empty, original-only, accepted-repair, and tampered-coverage tests;
- read-only service static contracts;
- protected route, sidebar, client, coverage, warning, and inspector tests;
- empty-database migration before focused backend and frontend gates.

Configured verification is not represented as hosted green evidence until the exact workflow run and artifacts are observed.

## Non-claims

Derivation evidence and coverage do not establish:

- correctness or optimality of a schedule;
- owner approval unless the separate approval event exists;
- task execution or human presence;
- appliance or sensor state;
- temperature or contamination evidence;
- food safety;
- clinical or nutritional validity;
- production readiness;
- a hosted green build without observed workflow evidence.
