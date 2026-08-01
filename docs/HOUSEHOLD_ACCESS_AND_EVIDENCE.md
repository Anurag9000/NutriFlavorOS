# Household Access, Reservations, and Evidence

**Database migration head:** `20260801_0008`

## Household roles

- **Owner:** manage household invitations, roles, unlinked members, household
  planning, reservations, and household inventory.
- **Editor:** mutate pantry lots, leftovers, plans, and reservation workflow
  state.
- **Viewer:** read authorized household state only.

Household roles do **not** authorize mutation of global conversion,
storage-policy, preparation, or lifecycle evidence. Global evidence
registration, review, rejection, deactivation, and supersession remain offline
controlled operations with explicit reviewer and operator identities.

Unauthorized household access returns `404` to avoid disclosing household
existence. Ownership transfer remains intentionally absent until a separately
reviewed workflow handles recovery, outstanding invitations, reservations, and
audit history.

## Invitations

Invitation secrets are generated once, returned once, stored only as SHA-256
hashes, bound to the invited email, and expire. Repeated acceptance by the same
eligible account is retry-safe. Creating a replacement invitation revokes
earlier active invitations for the same household and email.

## Household targets

Every active member contributes one target source:

1. a complete linked-user profile;
2. explicit member target overrides;
3. for an unlinked planning-only member, the declared serving multiplier
   applied to the owner's explicit complete profile.

A linked account with an incomplete profile and no explicit member targets
fails planning instead of inheriting fabricated physiology.

## Stock reservations

Reservations allocate expiry-ordered lots and subtract other active
reservations from availability. They do not mutate pantry quantities until an
explicit commit. Release, expiration, and commit are versioned states. Commit
locks the lot, validates the reserved unit and quantity, updates inventory, and
writes an append-only event.

## Immutable ingredient conversions

Automatic cross-unit conversion requires one exact active reviewed immutable
record for:

- canonical ingredient;
- source unit;
- target unit.

Each version retains:

- immutable record version;
- multiplier interval;
- source name, URL, and source version;
- evidence status;
- reviewer and UTC-normalized review time;
- notes and limitations;
- SHA-256 content hash;
- supersession link;
- active state.

Identical same-version registration is idempotent. Contradictory reuse fails.
A new active reviewed version supersedes the latest reviewed predecessor even
when that predecessor was already deactivated or rejected. At most one active
reviewed version exists per ingredient and unit direction.

FoodData Central portion gram weights may be imported only for that exact FDC
food and measure label. External records remain unverified until reviewed and
promoted into immutable history. Generic densities, package sizes, and
cross-food conversions are never inferred.

The reviewed-conversion API returns the exact evidence ID, version, hash,
source, reviewer, and output interval used for the result.

## Immutable storage policies

Every storage-policy version retains:

- policy key and immutable policy version;
- food category and storage state;
- duration interval and temperature assumption;
- source name, URL, and source version;
- evidence status, reviewer, and UTC-normalized review time;
- safety scope and limitations;
- SHA-256 content hash;
- supersession link;
- active state.

One active reviewed version is permitted per policy key. Built-in reviewed
policies seed as version `official-2026-07-31`. Legacy records are migrated
conservatively; unreviewed or ambiguous evidence remains preserved but cannot
be used automatically.

When a new leftover selects a policy:

1. the service resolves one active reviewed immutable version;
2. storage state must match refrigerated or frozen state;
3. an explicit expiry cannot exceed the reviewed upper bound;
4. non-quality guidance may derive a conservative expiry when none is supplied;
5. quality guidance never becomes a safety-expiry timestamp;
6. the leftover, exact policy-version link, and event provenance are committed
   atomically.

The inventory event retains policy ID, policy version, and content hash. Later
supersession, rejection, or deactivation does not rewrite the historical
leftover link.

Policies are conditional guidance under their stated assumptions, not safety
guarantees. Unknown foods receive no fabricated expiry, and NutriFlavorOS does
not autonomously declare food safe to eat.

## Manifest-driven reviewed imports

Conversions and storage policies can be validated and imported together as one
typed document:

```bash
python scripts/import_food_evidence.py reviewed-food-evidence.json
python scripts/import_food_evidence.py reviewed-food-evidence.json \
  --apply --operator reviewer@example.org
```

Dry run performs schema validation, exact natural-version conflict checks, and
planned supersession analysis without mutation. Apply mode requires an
operator and:

- writes a durable pre-apply manifest before database mutation;
- acquires natural-key locks in deterministic order;
- commits all conversion and storage-policy records in one transaction;
- collapses identical existing versions as idempotent outcomes;
- rejects contradictory version reuse;
- records input SHA-256, repository commit, operator, reviewers, natural keys,
  content hashes, planned actions, record IDs, supersession IDs, and outcomes;
- reports post-commit manifest-write failure honestly as an already committed
  database state.

Reapplying the same document is safe and returns the same immutable records.

## Append-only evidence lifecycle

Migration `20260801_0008` adds `evidence_lifecycle_events`. Lifecycle actions do
not edit registered evidence content. They only switch an exact target version
to inactive and append an audited event.

Supported actions:

- `deactivated`;
- `rejected`.

Every lifecycle event retains:

- exact conversion or storage-policy target;
- action;
- actor and reason;
- metadata;
- globally unique idempotency key;
- SHA-256 request fingerprint;
- whether the target was active at the time;
- creation time.

A lifecycle batch is validated and applied offline:

```bash
python scripts/manage_food_evidence_lifecycle.py lifecycle-actions.json
python scripts/manage_food_evidence_lifecycle.py lifecycle-actions.json \
  --apply --operator reviewer@example.org
```

Apply mode requires every action actor to exactly match the operator. The whole
document is atomic. An invalid target, contradictory idempotency-key reuse, or
concurrent conflict prevents partial lifecycle mutation. Identical retries
return the original events.

Reactivation is intentionally unsupported. Corrected evidence must be
registered as a new immutable reviewed version that supersedes the latest
reviewed predecessor.

## Read-only authenticated evidence APIs

Authenticated clients can read exact immutable history and lifecycle events:

- `GET /api/v1/food-evidence/history/conversions`
- `POST /api/v1/food-evidence/history/convert-reviewed`
- `GET /api/v1/food-evidence/history/storage-policies`
- `GET /api/v1/food-evidence/history/storage-policies/{policy_key}/active-reviewed`
- `GET /api/v1/food-evidence/history/lifecycle-events`
- `GET /api/v1/food-evidence/history/households/{household_id}/leftovers/{leftover_id}/storage-policy`

The lifecycle endpoint is read-only. No product API route registers,
supersedes, rejects, deactivates, or reactivates global evidence.

A household viewer may read exact policy provenance only for a leftover in an
accessible household. Cross-household and outsider requests return `404`.

## Concurrency guarantees

PostgreSQL transaction advisory locks serialize immutable evidence natural
keys, including first-version races where no row exists to lock. Separate
idempotency-key locks serialize lifecycle retries.

Concurrency probes cover:

- identical version registration retries;
- contradictory same-version registration;
- concurrent successor versions;
- identical lifecycle retries;
- contradictory lifecycle idempotency reuse;
- concurrent withdrawal and successor registration;
- preservation of one coherent supersession chain and one active reviewed
  version.

SQLite remains the local-development path. PostgreSQL is the required hosted
concurrency reference.
