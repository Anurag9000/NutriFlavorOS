# Approved-Plan Preparation Workflow

**Release boundary:** API `0.12.1`, migration head `20260802_0014`, OpenAPI contract `2026-08-02.6`, household-plan binding `2026-08-02.4`, and preparation-operations binding `2026-08-02.4`.

This workflow converts an exact approved household meal-plan version into a reviewable, deterministic, occurrence-bound preparation schedule without inferring deadlines, trusting stale evidence, or persisting/approving work automatically.

## End-to-end stages

1. Generate and persist a household plan as `draft`.
2. Owner explicitly approves one optimistic plan version.
3. Load preparation-occurrence candidates from that exact approved version.
4. Explicitly include or exclude every planned meal.
5. Confirm servings, required finish minute, priority, occurrence-set version, and duration policy for every included meal.
6. Server rechecks active reviewed preparation-profile availability and serving range while the plan row is locked.
7. Server returns a canonical non-persisted occurrence document and exact profile map.
8. A separate action stores a one-time 30-minute browser handoff.
9. The approved-plan pipeline consumes that handoff once.
10. Select the active reviewed household calendar and granularity.
11. Server rechecks plan status/version, occurrence-to-plan membership, profile identity, serving range, task templates, and calendar state.
12. Deterministic scheduler returns complete or explicitly partial output without persistence.
13. Partial output remains visible but cannot be staged.
14. A separate action creates `preparation-operations-handoff-v2`.
15. The operations workspace requires another explicit persistence action.
16. Owner approval replays and revalidates plan, occurrence, profile, calendar, request, response, and hashes.
17. Authorized users record explicit task start/completion/skip events.
18. Final schedule completion requires every deterministic task to be explicitly completed or skipped.

No stage automatically approves or executes the next stage.

## Plan lifecycle

Migration `20260802_0013` adds `draft`, `approved`, and `cancelled` plan states, optimistic versions, approver/cancellation provenance, and append-only plan events.

- Viewer/editor/owner may read plans and events.
- Owner approves.
- Editor/owner cancels.
- Exact retries collapse; contradictory key reuse and stale versions fail.
- Cancellation releases active reservations and invalidates dependent draft/approved schedules while preserving history.

## Candidate generation and serving semantics

Candidate endpoint:

`GET /api/v1/households/{household_id}/plans/{plan_id}/preparation-occurrences/candidates`

`day.portions[meal_slot]` is the stored planned **serving count**. It is not multiplied by recipe yield.

The response exposes:

- occurrence ID derived from day and exact meal-slot string;
- recipe identity and name;
- source recipe yield;
- planned serving count;
- descriptive batch scale = planned servings ÷ source recipe yield;
- active reviewed profile identity and serving range when available;
- explicit missing or incompatible profile state.

A stored meal without an explicit supported serving count fails closed.

Meal-slot names such as Breakfast, Lunch, Dinner, Snack, or custom labels never imply deadlines.

## Explicit occurrence confirmation

Confirmation endpoint:

`POST /api/v1/households/{household_id}/plans/{plan_id}/preparation-occurrences/confirm`

Requires editor/owner access and exactly one include/exclude decision for every candidate. Included occurrences require confirmed servings, explicit finish minute, priority, duration policy, and immutable occurrence-set version.

The plan row remains locked through confirmation so cancellation cannot complete between approval recheck and canonical document creation.

Every included occurrence requires an active reviewed profile compatible with confirmed servings. Missing evidence and serving-range drift fail closed.

The response is not an operational record by itself.

## Source-plan membership proof

Compilation and source-linked schedule persistence do not trust a plan ID alone. Every submitted occurrence must identify an occurrence ID generated from that approved plan and the exact recipe stored at that meal slot.

The server rejects:

- injected occurrence IDs;
- valid occurrence IDs paired with substituted recipes;
- stale or cancelled plan versions;
- route/document household mismatch.

## One-time occurrence handoff

`approved-plan-occurrence-handoff-v1` retains household ID, exact plan ID/version, canonical occurrence document, exact profile map, and creation time.

It:

- is stored only after a separate explicit action;
- expires after 30 minutes;
- is consumed once;
- is guarded against React development remounts;
- validates household/plan identity, quantities, duplicate IDs, profile identities, and profile-map coverage;
- is invalidated when reviewed occurrence inputs change.

## Server-authoritative compilation

Compile endpoint:

`POST /api/v1/households/{household_id}/plans/{plan_id}/preparation-occurrences/compile`

Requires editor/owner access, exact approved plan version, active reviewed calendar, canonical occurrence document, exact profile map, and explicit granularity.

Under the source-plan row lock, the service:

1. proves occurrence IDs and recipes belong to the plan;
2. verifies route/document household;
3. requires the selected calendar to remain active/reviewed;
4. verifies each profile ID/version/hash/recipe/status/active state;
5. checks confirmed serving range;
6. strictly validates non-empty task templates and dependencies;
7. namespaces task IDs by occurrence;
8. applies conservative-maximum or optimistic-minimum duration policy;
9. reconstructs resources only from the immutable calendar;
10. builds and runs the strict deterministic scheduler;
11. returns complete or explicit partial output without persistence.

Injected occurrences, recipe substitutions, stale plans, inactive calendars, profile drift, empty/invalid templates, serving drift, and malformed schedule requests fail closed.

## Compile-to-operations bridge

Only complete output with zero unscheduled work, non-empty tasks, and one scheduled result per task can become `preparation-operations-handoff-v2`.

The bundle retains exact calendar, source plan, occurrence document/hash, profile versions, complete request, deterministic response, and human-readable source notes.

Operations persistence and owner approval each repeat integrity checks. Browser hash previews are never trusted as authority.

## Task execution after approval

Migration `20260802_0014` adds a separate append-only execution ledger.

- Tasks begin `planned`.
- Explicit `started` produces `in_progress`.
- Explicit `completed` requires prior start.
- Explicit `skipped` is terminal and requires a reason.
- Dependencies must be completed or skipped before a task starts.
- Nonzero timing deviations require reasons.
- Every event increments the schedule optimistic version.
- Product schedule completion requires all tasks completed or skipped.

The system does not infer execution, observe appliances, measure temperatures, or declare food safe.

## Coverage

The protected preparation coverage dashboard reports operational provenance and task execution evidence separately. It includes replayability, source-plan linkage, deterministic task states, task-event history, deviations, skips/reasons, terminality, invalid histories, and latest event time.

Malformed histories are excluded from task-state denominators and surfaced as warnings. Coverage is not correctness, observed execution, nutrition quality, appliance state, temperature, or food-safety certification.

## Regression coverage

Committed tests cover serving semantics, missing servings, draft/stale/cancelled plans, explicit candidate decisions, profile availability/range, source-plan linkage, occurrence injection, recipe substitution, authorization, confirmation/cancellation serialization, handoff expiry/corruption, exact compile payload, duration policies, profile/calendar drift, empty profiles, complete/partial schedules, operations-handoff blocking, task state transitions, dependency chronology, timing reasons, guarded completion, execution coverage, household isolation, and PostgreSQL task-event races.

## Deliberate limitations

- Confirmation does not certify nutrition, allergies, food safety, equipment condition, or execution.
- Confirmed occurrences are durable when a schedule is persisted; no separate standalone occurrence table exists yet.
- Structured final persistence review still exposes expert JSON and remains incomplete.
- Timers/reminders, minimal-change repair, joint optimization, authenticated browser E2E, and automated accessibility evidence remain incomplete.
- Hosted workflow runs must be inspected before current `main` is described as green.
