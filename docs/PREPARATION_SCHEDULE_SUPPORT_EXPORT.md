# Preparation Schedule Support Export

## Purpose

The preparation schedule support export captures one internally consistent, read-only evidence package for diagnosis, audit, household support, and incident review.

It does not mutate a schedule, proposal, acceptance, task event, plan, calendar, pantry, reservation, or inventory record. It does not prove that cooking occurred and does not verify food safety.

## Evidence package

Document version `preparation-schedule-support-export-v1` contains:

- exact household and schedule identity;
- persisted schedule, status, optimistic version, request/response provenance, and hashes;
- append-only schedule lifecycle events;
- original-versus-repair derivation evidence;
- task-execution eligibility and exact accepted-replacement identity where blocked;
- deterministic task states and complete append-only task-event history;
- every repair proposal for which the selected schedule is the source;
- the accepted source proposal when the selected schedule is a replacement;
- immutable acceptance records;
- complete proposal event chains;
- database dialect, transaction isolation, read-only flag, PostgreSQL snapshot marker, and snapshot timestamps;
- one canonical SHA-256 evidence hash;
- explicit `mutation_performed=false`, `actual_execution_verified=false`, and `food_safety_verified=false`.

Related proposal IDs are sorted and unique. Every acceptance and event must belong to the exported household and related proposal set. Derivation and eligibility proposal identities must be represented in the proposal evidence.

## Canonical evidence hash

The evidence hash binds all domain evidence and non-claim fields. It intentionally excludes:

- database dialect;
- transaction isolation label;
- read-only transaction flag;
- PostgreSQL snapshot marker;
- snapshot start/completion timestamps;
- the hash field itself.

Two exports of unchanged evidence may therefore share the same evidence hash even though they use different transactions and timestamps. A lifecycle change, task event, proposal transition, replacement, version, status, or hash change alters the evidence hash.

## PostgreSQL snapshot semantics

PostgreSQL export uses a dedicated connection with:

- isolation level `REPEATABLE READ`;
- `SET TRANSACTION READ ONLY`;
- `txid_current_snapshot()` retained as the snapshot marker;
- no row mutation or lifecycle service call;
- transaction rollback after materializing the strict export model.

The first database statement establishes a stable snapshot. Every later schedule, proposal, acceptance, eligibility, derivation, and event read observes that same database snapshot even if another transaction commits concurrently.

SQLite uses the caller session and reports `serializable` as a local best-effort isolation label. No concurrent SQLite snapshot guarantee is claimed.

## Concurrent acceptance proof

The PostgreSQL race probe:

1. creates an approved source schedule and a current proposed repair;
2. begins a support export and pauses after its schedule read;
3. accepts the proposal in another committed session;
4. resumes the original export;
5. requires the original export to retain the pre-acceptance view: source eligible, proposal proposed, no acceptance, and only the proposal `created` event;
6. creates a fresh export and requires the accepted-replacement view: source blocked, proposal accepted, acceptance present, replacement identity present, and `created → accepted` events;
7. requires different evidence hashes and exactly one acceptance/replacement.

This proves snapshot consistency. It does not imply that exports block lifecycle mutation.

## Operational CLI

```bash
python scripts/export_preparation_schedule_support_snapshot.py \
  --household-id HOUSEHOLD_ID \
  --schedule-id 123 \
  --output reports/preparation-schedule-123-support.json
```

The CLI writes JSON atomically through a temporary file and replacement. It prints only a compact identity/hash summary on success. A rejected resource or database error is emitted as structured JSON to stderr. Partial output files are removed.

The CLI is an operator tool and does not replace application authorization. The synchronized HTTP endpoint separately requires at least household viewer access.

## Viewer-authorized API

The support endpoint is:

`GET /api/v1/households/{household_id}/preparation-operations/schedules/{schedule_id}/support-export`

It requires authentication and household viewer access. Cross-household and unauthorized reads retain `404` non-disclosure through the standard household access boundary.

## Protected browser workspace

The protected route is:

`/preparation/operations/support-export`

The workspace:

- loads only household and persisted-schedule selectors initially;
- does not request or download evidence until the user activates **Generate read-only snapshot**;
- uses the typed GET-only support-export client and exposes no create/update/delete method;
- clears previously generated evidence whenever household or schedule scope changes;
- displays the server evidence hash, database dialect, snapshot isolation, read-only flag, derivation method, execution-eligibility reason, and evidence counts;
- preserves the complete server response object when serializing JSON;
- creates a filesystem-safe filename containing household, schedule ID, and evidence-hash prefix;
- revokes the temporary browser object URL after download;
- reports generation and download outcomes through an `aria-live` region;
- repeats the explicit no-mutation, no-execution-verification, and no-food-safety-verification boundary;
- uses the sole main landmark provided by `AppLayout` and does not create a duplicate `<main>` or `main-content` ID;
- uses no `localStorage`, `sessionStorage`, IndexedDB, or browser-side authority cache.

Focused Vitest coverage proves explicit generation, server identity/non-claims, complete hash-addressed download, stale-scope clearing, fail-closed errors, and URL-constructor preservation while mocking blob methods.

## Failure and non-claim boundary

- Missing or inaccessible resources return controlled HTTP errors.
- Contradictory derivation, acceptance, replacement, or task-history evidence fails closed rather than exporting a misleading package.
- Retryable database aborts and ambiguous connections use the common structured database failure boundary.
- The export does not sign, encrypt, upload, email, or retain a file on the server.
- The browser download is local user action and is not a server-side retention or support-case record.
- The export is not proof of task performance, human presence, appliance state, temperature, contamination status, food safety, clinical validity, or global optimization quality.
- Configured tests and workflows are not represented as hosted green evidence until the exact run and artifacts are observed.
