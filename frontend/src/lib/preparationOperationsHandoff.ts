import type {
  CompileAndScheduleRequest,
  CompileAndScheduleResponse,
} from "@/lib/preparationApi";
import type {
  PersistedScheduleCreateRequest,
  PreparationResource,
  ResourceCalendarVersionView,
} from "@/lib/preparationOperationsApi";

export const PREPARATION_OPERATIONS_HANDOFF_KEY =
  "nutriflavos.preparation-operations.handoff.v1";

export interface PreparationOperationsHandoff {
  document_version: "preparation-operations-handoff-v1";
  household_id: string;
  created_at: string;
  bundle: Omit<PersistedScheduleCreateRequest, "idempotency_key">;
}

function canonicalValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonicalValue);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, item]) => [key, canonicalValue(item)]),
    );
  }
  return value;
}

export function canonicalJson(value: unknown): string {
  return JSON.stringify(canonicalValue(value));
}

export async function sha256Hex(value: unknown): Promise<string> {
  if (!globalThis.crypto?.subtle) {
    throw new Error("This browser cannot calculate the required SHA-256 fingerprint");
  }
  const encoded = new TextEncoder().encode(canonicalJson(value));
  const digest = await globalThis.crypto.subtle.digest("SHA-256", encoded);
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

export function calendarPreparationResources(
  calendar: ResourceCalendarVersionView,
): PreparationResource[] {
  return [...calendar.resources]
    .sort((left, right) => left.resource_id.localeCompare(right.resource_id))
    .map((resource) => ({
      resource_id: resource.resource_id,
      label: resource.label,
      capacity: resource.capacity,
      availability_windows: resource.availability_windows.map((window) => ({
        start_minute: window.start_minute,
        end_minute: window.end_minute,
      })),
    }));
}

export async function buildPreparationOperationsHandoff(options: {
  householdId: string;
  calendar: ResourceCalendarVersionView;
  compileRequest: CompileAndScheduleRequest;
  compileResponse: CompileAndScheduleResponse;
  occurrenceSetVersion: string;
  notes?: string | null;
}): Promise<PreparationOperationsHandoff> {
  const householdId = options.householdId.trim();
  const occurrenceSetVersion = options.occurrenceSetVersion.trim();
  if (!householdId) throw new Error("Select a household before creating a handoff");
  if (!occurrenceSetVersion) throw new Error("Occurrence-set version cannot be blank");
  if (!options.calendar.active || options.calendar.evidence_status !== "reviewed") {
    throw new Error("A handoff requires the household's active reviewed calendar");
  }
  if (
    options.compileResponse.execution_status !== "scheduled"
    || options.compileResponse.partial
    || options.compileResponse.compilation.unresolved.length > 0
    || !options.compileResponse.schedule
    || options.compileResponse.schedule.unscheduled.length > 0
  ) {
    throw new Error("Only a complete fail-closed pipeline result can be handed off");
  }
  if (options.compileRequest.allow_partial) {
    throw new Error("Partial scheduling must be disabled for persisted operations");
  }
  if (options.compileRequest.horizon_minutes !== options.calendar.horizon_minutes) {
    throw new Error("Pipeline horizon does not match the active calendar");
  }

  const resources = calendarPreparationResources(options.calendar);
  const occurrenceDocument = {
    document_version: "preparation-occurrence-set-v1",
    occurrence_set_version: occurrenceSetVersion,
    household_id: householdId,
    duration_policy: options.compileRequest.duration_policy,
    occurrences: [...options.compileRequest.occurrences].sort((left, right) =>
      left.occurrence_id.localeCompare(right.occurrence_id),
    ),
  };
  const occurrenceSetHash = await sha256Hex(occurrenceDocument);

  return {
    document_version: "preparation-operations-handoff-v1",
    household_id: householdId,
    created_at: new Date().toISOString(),
    bundle: {
      calendar_version_id: options.calendar.id,
      source_plan_id: null,
      source_plan_version: null,
      occurrence_set_version: occurrenceSetVersion,
      occurrence_set_hash: occurrenceSetHash,
      profile_versions: Object.fromEntries(
        Object.entries(options.compileResponse.compilation.profile_versions).sort(
          ([left], [right]) => left.localeCompare(right),
        ),
      ),
      schedule_request: {
        horizon_minutes: options.compileRequest.horizon_minutes,
        granularity_minutes: options.compileRequest.granularity_minutes,
        resources,
        tasks: options.compileResponse.compilation.tasks.map((task) => ({
          ...task,
          metadata: task.metadata ?? {},
        })),
      },
      schedule_response: options.compileResponse.schedule,
      notes: options.notes?.trim() || null,
    },
  };
}

export function storePreparationOperationsHandoff(
  handoff: PreparationOperationsHandoff,
): void {
  sessionStorage.setItem(
    PREPARATION_OPERATIONS_HANDOFF_KEY,
    JSON.stringify(handoff),
  );
}

export function consumePreparationOperationsHandoff(): PreparationOperationsHandoff | null {
  const raw = sessionStorage.getItem(PREPARATION_OPERATIONS_HANDOFF_KEY);
  if (!raw) return null;
  sessionStorage.removeItem(PREPARATION_OPERATIONS_HANDOFF_KEY);
  const parsed = JSON.parse(raw) as PreparationOperationsHandoff;
  if (
    parsed.document_version !== "preparation-operations-handoff-v1"
    || !parsed.household_id
    || !parsed.bundle
  ) {
    throw new Error("Stored preparation-operations handoff is invalid");
  }
  return parsed;
}
