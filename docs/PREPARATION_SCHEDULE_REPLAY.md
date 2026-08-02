# Method-Aware Preparation Schedule Replay

## Purpose

Preparation schedules can now originate from two deterministic algorithms with different authoritative inputs:

1. **Original deterministic scheduler replay** — `deterministic_dependency_aware_resource_scheduler_v2`.
2. **Minimal-change repair replay** — `deterministic_minimal_change_preparation_repair_v1`.

Replay never guesses which algorithm produced a response. Callers must provide the exact derivation method and the corresponding strict evidence envelope.

## Original deterministic scheduler replay

The original envelope contains:

- the complete strict scheduling request;
- the expected complete deterministic response;
- the canonical request SHA-256;
- the canonical response SHA-256.

The replay service:

1. hashes the supplied request and expected response;
2. verifies both expected hashes;
3. runs the original deterministic scheduler;
4. verifies method identity and deterministic output;
5. rejects unresolved tasks;
6. compares the full canonical replayed response and hash with stored evidence.

## Minimal-change repair replay

The repair envelope contains:

- the complete strict repair request, including previous request, previous response, revised request, immutable tasks, strategy, weights, and bounded-search limits;
- the complete expected advisory repair result;
- the canonical repair-request SHA-256;
- the canonical repair-result SHA-256;
- the canonical revised-request SHA-256;
- the canonical repaired-response SHA-256.

The replay service:

1. validates that the expected result remains complete, deterministic, human-review-required, non-accepted, and non-persisted;
2. verifies all supplied hashes before computation;
3. reruns the deterministic repair engine;
4. rejects computation errors and unresolved work;
5. compares the full replayed repair result with stored evidence;
6. verifies the result, revised-request, and response hashes independently;
7. returns only replay evidence and the replayed schedule response.

## Dispatch

The method registry contains exactly:

- `deterministic_dependency_aware_resource_scheduler_v2`;
- `deterministic_minimal_change_preparation_repair_v1`.

Unknown methods fail closed. An original method cannot receive a repair envelope, and a repair method cannot receive an original envelope. Mixed or missing envelopes fail with stable error codes.

## No database mutation

The replay service is side-effect-free:

- no database session;
- no ORM model access;
- no schedule creation;
- no schedule transition;
- no proposal mutation;
- no task-execution mutation;
- no acceptance or persistence claim.

This separation allows proposal acceptance and schedule approval to use identical deterministic evidence verification without embedding persistence inside algorithm execution.

## Relationship to an accepted repaired draft

Method-aware replay is a prerequisite, not acceptance itself. A future accepted repaired draft must still:

- revalidate proposal, source schedule, calendar, plan, occurrence, profile, and execution-history state;
- require exact acknowledgement of every changed task;
- rerun this repair replay and compare all hashes;
- create a new draft rather than mutate the source schedule;
- append acceptance and draft-creation evidence atomically;
- keep owner approval, task execution, and completion separate.

## Failure codes

Representative fail-closed codes include:

- `unknown_schedule_derivation_method`;
- `original_replay_request_hash_mismatch`;
- `original_replay_response_hash_mismatch`;
- `original_replay_output_mismatch`;
- `repair_replay_request_hash_mismatch`;
- `repair_replay_result_hash_mismatch`;
- `repair_replay_revised_request_hash_mismatch`;
- `repair_replay_stored_response_hash_mismatch`;
- `repair_replay_output_mismatch`;
- `repair_replay_result_hash_drift`;
- `repair_replay_response_hash_drift`.

## Verification

Configured verification covers:

- exact original replay;
- exact repair replay;
- unknown and mixed method dispatch;
- request, result, revised-request, and response hash drift;
- wrong response method;
- pre-accepted or pre-persisted repair results;
- tampered but schema-valid stored results;
- static absence of persistence imports and mutations.

Configured checks are not represented as hosted green evidence until the exact workflow run and artifacts are observed.
