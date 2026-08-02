import { apiRequest } from "@/lib/http";

const request = apiRequest;
const encode = encodeURIComponent;
const body = (value: unknown) => JSON.stringify(value);

export type CalendarEvidenceStatus = "draft" | "reviewed";
export type PreparationScheduleStatus =
  | "draft"
  | "approved"
  | "invalidated"
  | "completed"
  | "cancelled";
export type PreparationScheduleEventType =
  | "created"
  | "approved"
  | "invalidated"
  | "completed"
  | "cancelled";
export type PreparationTaskExecutionEventType =
  | "started"
  | "completed"
  | "skipped";
export type PreparationTaskExecutionState =
  | "planned"
  | "in_progress"
  | "completed"
  | "skipped";
export type DurationPolicy = "conservative_max" | "optimistic_min";
export type ScheduleReplayStatus =
  | "replayable"
  | "legacy_request_missing"
  | "legacy_occurrence_set_missing";

export interface PreparationAvailabilityWindow {
  start_minute: number;
  end_minute: number;
}

export interface HouseholdResourceInput {
  resource_id: string;
  label: string;
  capacity: number;
  resource_kind: string;
  availability_windows: PreparationAvailabilityWindow[];
  metadata: Record<string, unknown>;
}

export interface HouseholdResourceView extends HouseholdResourceInput {
  id: number;
  calendar_version_id: number;
}

export interface ResourceCalendarVersionCreate {
  calendar_version: string;
  horizon_minutes: number;
  timezone: string;
  resources: HouseholdResourceInput[];
  evidence_status: CalendarEvidenceStatus;
  reviewed_at?: string | null;
  reviewed_by?: string | null;
  notes?: string | null;
  activate: boolean;
  idempotency_key: string;
}

export interface ResourceCalendarVersionView {
  id: number;
  household_id: string;
  calendar_version: string;
  horizon_minutes: number;
  timezone: string;
  evidence_status: CalendarEvidenceStatus;
  reviewed_at: string | null;
  reviewed_by: string | null;
  notes: string | null;
  content_hash: string;
  supersedes_calendar_id: number | null;
  active: boolean;
  created_by_user_id: string;
  created_at: string;
  updated_at: string;
  resources: HouseholdResourceView[];
}

export interface PreparationResource {
  resource_id: string;
  capacity: number;
  available_from_minute?: number;
  available_until_minute?: number | null;
  availability_windows?: PreparationAvailabilityWindow[];
  label?: string | null;
}

export interface PreparationTask {
  task_id: string;
  duration_minutes: number;
  earliest_start_minute: number;
  latest_finish_minute?: number | null;
  priority: number;
  resource_demands: Record<string, number>;
  dependencies: string[];
  metadata: Record<string, unknown>;
}

export interface PreparationScheduleRequest {
  horizon_minutes: number;
  granularity_minutes: number;
  resources: PreparationResource[];
  tasks: PreparationTask[];
}

export interface ScheduledPreparationTask {
  task_id: string;
  start_minute: number;
  finish_minute: number;
  duration_minutes: number;
  priority: number;
  resource_demands: Record<string, number>;
  dependencies: string[];
  metadata: Record<string, unknown>;
}

export interface UnscheduledPreparationTask {
  task_id: string;
  reason_code: string;
  message: string;
  missing_resources: string[];
  blocked_by: string[];
  capacity_violations: Record<string, Record<string, number>>;
  metadata: Record<string, unknown>;
}

export interface PreparationScheduleResponse {
  method: string;
  deterministic: boolean;
  horizon_minutes: number;
  granularity_minutes: number;
  scheduled: ScheduledPreparationTask[];
  unscheduled: UnscheduledPreparationTask[];
  resource_utilization: Record<string, number>;
  resource_peak_usage: Record<string, number>;
  makespan_minutes: number;
  diagnostics: Record<string, unknown>;
}

export interface RecipePreparationOccurrence {
  occurrence_id: string;
  recipe_id: string;
  required_finish_minute: number;
  servings: number;
  priority: number;
}

export interface PreparationOccurrenceSetDocument {
  document_version: "preparation-occurrence-set-v1";
  household_id: string;
  occurrence_set_version: string;
  duration_policy: DurationPolicy;
  occurrences: RecipePreparationOccurrence[];
}

export interface PersistedScheduleCreateRequest {
  calendar_version_id: number;
  source_plan_id?: number | null;
  source_plan_version?: number | null;
  occurrence_set: PreparationOccurrenceSetDocument;
  profile_versions: Record<string, string>;
  schedule_request: PreparationScheduleRequest;
  schedule_response: PreparationScheduleResponse;
  notes?: string | null;
  idempotency_key: string;
}

export interface PersistedPreparationScheduleView {
  id: number;
  household_id: string;
  calendar_version_id: number;
  calendar_content_hash: string;
  source_plan_id: number | null;
  source_plan_version: number | null;
  occurrence_set_version: string;
  occurrence_set_hash: string;
  occurrence_set?: PreparationOccurrenceSetDocument | null;
  profile_versions: Record<string, string>;
  schedule_request?: PreparationScheduleRequest | null;
  schedule_request_hash?: string | null;
  replay_status?: ScheduleReplayStatus;
  schedule: PreparationScheduleResponse;
  schedule_hash: string;
  status: PreparationScheduleStatus;
  version: number;
  notes: string | null;
  created_by_user_id: string;
  approved_by_user_id: string | null;
  approved_at: string | null;
  invalidated_at: string | null;
  invalidation_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface ScheduleStateTransitionRequest {
  expected_version: number;
  reason: string;
  idempotency_key: string;
  metadata: Record<string, unknown>;
}

export interface PreparationScheduleEventView {
  id: number;
  schedule_id: number;
  household_id: string;
  event_type: PreparationScheduleEventType;
  actor_user_id: string;
  from_status: PreparationScheduleStatus | null;
  to_status: PreparationScheduleStatus;
  reason: string;
  metadata: Record<string, unknown>;
  idempotency_key: string;
  request_fingerprint: string;
  created_at: string;
}

export interface PreparationTaskExecutionEventCreate {
  expected_schedule_version: number;
  actual_minute: number;
  reason?: string | null;
  notes?: string | null;
  idempotency_key: string;
  metadata: Record<string, unknown>;
}

export interface PreparationTaskExecutionEventView {
  id: number;
  schedule_id: number;
  household_id: string;
  task_id: string;
  event_type: PreparationTaskExecutionEventType;
  actor_user_id: string;
  from_state: PreparationTaskExecutionState;
  to_state: PreparationTaskExecutionState;
  planned_start_minute: number;
  planned_finish_minute: number;
  actual_minute: number;
  deviation_minutes: number;
  reason: string | null;
  notes: string | null;
  metadata: Record<string, unknown>;
  idempotency_key: string;
  request_fingerprint: string;
  schedule_version_before: number;
  schedule_version_after: number;
  created_at: string;
}

export interface PreparationTaskExecutionTaskView {
  task: ScheduledPreparationTask;
  state: PreparationTaskExecutionState;
  latest_event_id: number | null;
  started_actual_minute: number | null;
  completed_actual_minute: number | null;
  skipped_actual_minute: number | null;
  terminal_reason: string | null;
}

export interface PreparationTaskExecutionOverview {
  schedule: PersistedPreparationScheduleView;
  tasks: PreparationTaskExecutionTaskView[];
  events: PreparationTaskExecutionEventView[];
  planned_count: number;
  in_progress_count: number;
  completed_count: number;
  skipped_count: number;
  terminal_count: number;
  remaining_count: number;
}

export interface PreparationTaskExecutionMutationView {
  schedule: PersistedPreparationScheduleView;
  task: PreparationTaskExecutionTaskView;
  event: PreparationTaskExecutionEventView;
}

export interface PreparationOperationsCoverageView {
  household_id: string;
  generated_at: string;
  calendar_total: number;
  reviewed_calendar_total: number;
  active_reviewed_calendar_count: number;
  schedule_total: number;
  schedule_status_counts: Record<PreparationScheduleStatus, number>;
  replay_status_counts: Record<ScheduleReplayStatus, number>;
  occurrence_document_count: number;
  scheduler_request_count: number;
  replayable_schedule_count: number;
  replayable_draft_count: number;
  source_plan_linked_count: number;
  event_total: number;
  occurrence_document_coverage: number;
  scheduler_request_coverage: number;
  replayable_schedule_coverage: number;
  latest_calendar_created_at: string | null;
  latest_schedule_created_at: string | null;
  warnings: string[];
}

const base = (householdId: string) =>
  `/households/${encode(householdId)}/preparation-operations`;
const schedulePath = (householdId: string, scheduleId: number) =>
  `${base(householdId)}/schedules/${scheduleId}`;
const taskPath = (
  householdId: string,
  scheduleId: number,
  taskId: string,
) => `${schedulePath(householdId, scheduleId)}/tasks/${encode(taskId)}`;

export const preparationOperationsApi = {
  coverage: (householdId: string) =>
    request<PreparationOperationsCoverageView>(`${base(householdId)}/coverage`),
  createCalendar: (householdId: string, payload: ResourceCalendarVersionCreate) =>
    request<ResourceCalendarVersionView>(`${base(householdId)}/resource-calendars`, {
      method: "POST",
      body: body(payload),
    }),
  calendars: (householdId: string, activeOnly = false) =>
    request<ResourceCalendarVersionView[]>(
      `${base(householdId)}/resource-calendars?active_only=${activeOnly}`,
    ),
  calendar: (householdId: string, calendarId: number) =>
    request<ResourceCalendarVersionView>(
      `${base(householdId)}/resource-calendars/${calendarId}`,
    ),
  createSchedule: (householdId: string, payload: PersistedScheduleCreateRequest) =>
    request<PersistedPreparationScheduleView>(`${base(householdId)}/schedules`, {
      method: "POST",
      body: body(payload),
    }),
  schedules: (householdId: string, statuses: PreparationScheduleStatus[] = []) => {
    const params = new URLSearchParams();
    for (const status of statuses) params.append("status", status);
    const suffix = params.size ? `?${params.toString()}` : "";
    return request<PersistedPreparationScheduleView[]>(
      `${base(householdId)}/schedules${suffix}`,
    );
  },
  schedule: (householdId: string, scheduleId: number) =>
    request<PersistedPreparationScheduleView>(
      schedulePath(householdId, scheduleId),
    ),
  taskExecution: (householdId: string, scheduleId: number) =>
    request<PreparationTaskExecutionOverview>(
      `${schedulePath(householdId, scheduleId)}/task-execution`,
    ),
  startTask: (
    householdId: string,
    scheduleId: number,
    taskId: string,
    payload: PreparationTaskExecutionEventCreate,
  ) =>
    request<PreparationTaskExecutionMutationView>(
      `${taskPath(householdId, scheduleId, taskId)}/start`,
      { method: "POST", body: body(payload) },
    ),
  completeTask: (
    householdId: string,
    scheduleId: number,
    taskId: string,
    payload: PreparationTaskExecutionEventCreate,
  ) =>
    request<PreparationTaskExecutionMutationView>(
      `${taskPath(householdId, scheduleId, taskId)}/complete`,
      { method: "POST", body: body(payload) },
    ),
  skipTask: (
    householdId: string,
    scheduleId: number,
    taskId: string,
    payload: PreparationTaskExecutionEventCreate,
  ) =>
    request<PreparationTaskExecutionMutationView>(
      `${taskPath(householdId, scheduleId, taskId)}/skip`,
      { method: "POST", body: body(payload) },
    ),
  approve: (
    householdId: string,
    scheduleId: number,
    payload: ScheduleStateTransitionRequest,
  ) =>
    request<PersistedPreparationScheduleView>(
      `${schedulePath(householdId, scheduleId)}/approve`,
      { method: "POST", body: body(payload) },
    ),
  complete: (
    householdId: string,
    scheduleId: number,
    payload: ScheduleStateTransitionRequest,
  ) =>
    request<PersistedPreparationScheduleView>(
      `${schedulePath(householdId, scheduleId)}/complete`,
      { method: "POST", body: body(payload) },
    ),
  cancel: (
    householdId: string,
    scheduleId: number,
    payload: ScheduleStateTransitionRequest,
  ) =>
    request<PersistedPreparationScheduleView>(
      `${schedulePath(householdId, scheduleId)}/cancel`,
      { method: "POST", body: body(payload) },
    ),
  invalidate: (
    householdId: string,
    scheduleId: number,
    payload: ScheduleStateTransitionRequest,
  ) =>
    request<PersistedPreparationScheduleView>(
      `${schedulePath(householdId, scheduleId)}/invalidate`,
      { method: "POST", body: body(payload) },
    ),
  events: (householdId: string, scheduleId: number) =>
    request<PreparationScheduleEventView[]>(
      `${schedulePath(householdId, scheduleId)}/events`,
    ),
};
