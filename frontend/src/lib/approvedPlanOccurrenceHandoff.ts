import type {
  ConfirmedPlanOccurrenceSetView,
} from "@/lib/householdPlanApi";
import type {
  PreparationOccurrenceSetDocument,
} from "@/lib/preparationOperationsApi";

export const APPROVED_PLAN_OCCURRENCE_HANDOFF_KEY =
  "nutriflavors.approved-plan-occurrence-handoff.v1";

export const APPROVED_PLAN_OCCURRENCE_HANDOFF_VERSION =
  "approved-plan-occurrence-handoff-v1" as const;

const MAX_HANDOFF_AGE_MS = 30 * 60 * 1000;
const PROFILE_VERSION_PATTERN =
  /^profile:[1-9][0-9]*\/version:[^/]+\/sha256:[a-f0-9]{64}$/;

export interface ApprovedPlanOccurrenceHandoff {
  document_version: typeof APPROVED_PLAN_OCCURRENCE_HANDOFF_VERSION;
  household_id: string;
  source_plan_id: number;
  source_plan_version: number;
  created_at: string;
  occurrence_set: PreparationOccurrenceSetDocument;
  profile_versions: Record<string, string>;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function assertPositiveInteger(value: unknown, label: string): asserts value is number {
  if (!Number.isInteger(value) || Number(value) < 1) {
    throw new Error(`${label} must be a positive integer`);
  }
}

function assertNonBlank(value: unknown, label: string): asserts value is string {
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(`${label} cannot be blank`);
  }
}

function assertOccurrenceSet(
  value: unknown,
  householdId: string,
): asserts value is PreparationOccurrenceSetDocument {
  if (!isRecord(value)) {
    throw new Error("Occurrence handoff requires a canonical occurrence document");
  }
  if (value.document_version !== "preparation-occurrence-set-v1") {
    throw new Error("Unsupported occurrence document version");
  }
  if (value.household_id !== householdId) {
    throw new Error("Occurrence document household does not match the handoff");
  }
  assertNonBlank(value.occurrence_set_version, "Occurrence-set version");
  if (
    value.duration_policy !== "conservative_max"
    && value.duration_policy !== "optimistic_min"
  ) {
    throw new Error("Unsupported occurrence duration policy");
  }
  if (!Array.isArray(value.occurrences) || value.occurrences.length === 0) {
    throw new Error("Occurrence document must contain at least one occurrence");
  }
  const identifiers = new Set<string>();
  for (const raw of value.occurrences) {
    if (!isRecord(raw)) {
      throw new Error("Occurrence entries must be objects");
    }
    assertNonBlank(raw.occurrence_id, "Occurrence ID");
    assertNonBlank(raw.recipe_id, "Occurrence recipe ID");
    if (identifiers.has(raw.occurrence_id)) {
      throw new Error(`Occurrence ID ${raw.occurrence_id} is duplicated`);
    }
    identifiers.add(raw.occurrence_id);
    if (
      typeof raw.servings !== "number"
      || !Number.isFinite(raw.servings)
      || raw.servings <= 0
      || raw.servings > 1000
    ) {
      throw new Error(`Occurrence ${raw.occurrence_id} has invalid servings`);
    }
    if (
      !Number.isInteger(raw.required_finish_minute)
      || Number(raw.required_finish_minute) < 1
      || Number(raw.required_finish_minute) > 10080
    ) {
      throw new Error(
        `Occurrence ${raw.occurrence_id} has an invalid required finish minute`,
      );
    }
    if (
      !Number.isInteger(raw.priority)
      || Number(raw.priority) < -1000
      || Number(raw.priority) > 1000
    ) {
      throw new Error(`Occurrence ${raw.occurrence_id} has an invalid priority`);
    }
  }
}

function assertProfileVersions(
  value: unknown,
  occurrenceSet: PreparationOccurrenceSetDocument,
): asserts value is Record<string, string> {
  if (!isRecord(value)) {
    throw new Error("Occurrence handoff requires preparation profile versions");
  }
  const expectedRecipeIds = [
    ...new Set(occurrenceSet.occurrences.map((item) => item.recipe_id)),
  ].sort();
  const suppliedRecipeIds = Object.keys(value).sort();
  if (JSON.stringify(expectedRecipeIds) !== JSON.stringify(suppliedRecipeIds)) {
    throw new Error(
      "Profile-version recipes must exactly match confirmed occurrence recipes",
    );
  }
  for (const [recipeId, profileVersion] of Object.entries(value)) {
    if (
      typeof profileVersion !== "string"
      || !PROFILE_VERSION_PATTERN.test(profileVersion)
    ) {
      throw new Error(`Recipe ${recipeId} has an invalid profile-version identity`);
    }
  }
}

export function validateApprovedPlanOccurrenceHandoff(
  value: unknown,
  now = Date.now(),
): ApprovedPlanOccurrenceHandoff {
  if (!isRecord(value)) {
    throw new Error("Approved-plan occurrence handoff must be an object");
  }
  if (value.document_version !== APPROVED_PLAN_OCCURRENCE_HANDOFF_VERSION) {
    throw new Error("Unsupported approved-plan occurrence handoff version");
  }
  assertNonBlank(value.household_id, "Handoff household ID");
  assertPositiveInteger(value.source_plan_id, "Source plan ID");
  assertPositiveInteger(value.source_plan_version, "Source plan version");
  assertNonBlank(value.created_at, "Handoff creation time");
  const createdAt = new Date(value.created_at).getTime();
  if (!Number.isFinite(createdAt)) {
    throw new Error("Handoff creation time is invalid");
  }
  if (createdAt > now + 60_000) {
    throw new Error("Handoff creation time is unexpectedly in the future");
  }
  if (now - createdAt > MAX_HANDOFF_AGE_MS) {
    throw new Error("Approved-plan occurrence handoff has expired");
  }
  assertOccurrenceSet(value.occurrence_set, value.household_id);
  assertProfileVersions(value.profile_versions, value.occurrence_set);
  return value as unknown as ApprovedPlanOccurrenceHandoff;
}

export function buildApprovedPlanOccurrenceHandoff(
  confirmed: ConfirmedPlanOccurrenceSetView,
  createdAt = new Date().toISOString(),
): ApprovedPlanOccurrenceHandoff {
  return validateApprovedPlanOccurrenceHandoff({
    document_version: APPROVED_PLAN_OCCURRENCE_HANDOFF_VERSION,
    household_id: confirmed.household_id,
    source_plan_id: confirmed.source_plan_id,
    source_plan_version: confirmed.source_plan_version,
    created_at: createdAt,
    occurrence_set: confirmed.occurrence_set,
    profile_versions: confirmed.profile_versions,
  });
}

export function storeApprovedPlanOccurrenceHandoff(
  handoff: ApprovedPlanOccurrenceHandoff,
  storage: Storage = window.sessionStorage,
): void {
  storage.setItem(
    APPROVED_PLAN_OCCURRENCE_HANDOFF_KEY,
    JSON.stringify(validateApprovedPlanOccurrenceHandoff(handoff)),
  );
}

export function peekApprovedPlanOccurrenceHandoff(
  storage: Storage = window.sessionStorage,
): ApprovedPlanOccurrenceHandoff | null {
  const raw = storage.getItem(APPROVED_PLAN_OCCURRENCE_HANDOFF_KEY);
  if (!raw) return null;
  return validateApprovedPlanOccurrenceHandoff(JSON.parse(raw));
}

export function consumeApprovedPlanOccurrenceHandoff(
  storage: Storage = window.sessionStorage,
): ApprovedPlanOccurrenceHandoff | null {
  const raw = storage.getItem(APPROVED_PLAN_OCCURRENCE_HANDOFF_KEY);
  if (!raw) return null;
  storage.removeItem(APPROVED_PLAN_OCCURRENCE_HANDOFF_KEY);
  return validateApprovedPlanOccurrenceHandoff(JSON.parse(raw));
}
