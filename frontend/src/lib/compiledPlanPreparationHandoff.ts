import type {
  ApprovedPlanPreparationCompileView,
} from "@/lib/householdPlanApi";
import {
  storePreparationOperationsHandoff,
  type PreparationOperationsHandoff,
} from "@/lib/preparationOperationsHandoff";

function canonicalize(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (typeof value === "object" && value !== null) {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, nested]) => [key, canonicalize(nested)]),
    );
  }
  return value;
}

function canonicalJson(value: unknown): string {
  return JSON.stringify(canonicalize(value));
}

async function sha256(value: unknown): Promise<string> {
  const encoded = new TextEncoder().encode(canonicalJson(value));
  const digest = await crypto.subtle.digest("SHA-256", encoded);
  return Array.from(new Uint8Array(digest))
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
}

function assertCompleteCompilation(
  compiled: ApprovedPlanPreparationCompileView,
): void {
  if (compiled.partial || compiled.schedule_response.unscheduled.length > 0) {
    throw new Error(
      "Partial or unscheduled preparation output cannot be handed to operations",
    );
  }
  if (compiled.execution_status !== "complete") {
    throw new Error("Preparation compilation is not complete");
  }
  if (compiled.schedule_request.tasks.length === 0) {
    throw new Error("Preparation compilation contains no tasks");
  }
  if (
    compiled.schedule_response.scheduled.length
    !== compiled.schedule_request.tasks.length
  ) {
    throw new Error(
      "Every compiled preparation task must be present in the deterministic schedule",
    );
  }
  if (
    compiled.occurrence_set.household_id !== compiled.household_id
    || compiled.source_plan_id < 1
    || compiled.source_plan_version < 1
    || compiled.calendar_version_id < 1
  ) {
    throw new Error("Compiled preparation provenance is internally inconsistent");
  }
}

export async function buildCompiledPlanPreparationHandoff(
  compiled: ApprovedPlanPreparationCompileView,
  createdAt = new Date().toISOString(),
): Promise<PreparationOperationsHandoff> {
  assertCompleteCompilation(compiled);
  const occurrenceSetHashPreview = await sha256(compiled.occurrence_set);
  return {
    document_version: "preparation-operations-handoff-v2",
    household_id: compiled.household_id,
    created_at: createdAt,
    occurrence_set_hash_preview: occurrenceSetHashPreview,
    bundle: {
      calendar_version_id: compiled.calendar_version_id,
      source_plan_id: compiled.source_plan_id,
      source_plan_version: compiled.source_plan_version,
      occurrence_set: compiled.occurrence_set,
      profile_versions: compiled.profile_versions,
      schedule_request: compiled.schedule_request,
      schedule_response: compiled.schedule_response,
      notes: (
        `Approved plan #${compiled.source_plan_id} version `
        + `${compiled.source_plan_version}; reviewed calendar `
        + `${compiled.calendar_version} (${compiled.calendar_content_hash})`
      ),
    },
  };
}

export async function storeCompiledPlanPreparationHandoff(
  compiled: ApprovedPlanPreparationCompileView,
  storage: Storage = window.sessionStorage,
): Promise<PreparationOperationsHandoff> {
  const handoff = await buildCompiledPlanPreparationHandoff(compiled);
  storePreparationOperationsHandoff(handoff, storage);
  return handoff;
}
