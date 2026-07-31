import { apiRequest } from "@/lib/http";

export interface PreparationResourceInput {
  resource_id: string;
  capacity: number;
  available_from_minute: number;
  available_until_minute?: number | null;
  label?: string | null;
}

export interface PreparationTaskInput {
  task_id: string;
  duration_minutes: number;
  earliest_start_minute: number;
  latest_finish_minute?: number | null;
  priority: number;
  resource_demands: Record<string, number>;
  dependencies: string[];
  metadata?: Record<string, unknown>;
}

export interface PreparationScheduleRequest {
  horizon_minutes: number;
  granularity_minutes: number;
  resources: PreparationResourceInput[];
  tasks: PreparationTaskInput[];
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
  capacity_violations: Record<string, { requested: number; capacity: number }>;
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

export interface PreparationTaskTemplate {
  template_id: string;
  name: string;
  duration_min_minutes: number;
  duration_max_minutes: number;
  resource_demands: Record<string, number>;
  dependencies: string[];
  active_work: boolean;
  unattended_allowed?: boolean | null;
  notes?: string | null;
}

export interface RecipePreparationProfile {
  id: number;
  recipe_id: string;
  profile_version: string;
  schema_version: string;
  supported_servings_min: number;
  supported_servings_max: number;
  task_templates: PreparationTaskTemplate[];
  source_name: string;
  source_url: string;
  source_version: string;
  evidence_status: "draft" | "external_unverified" | "reviewed";
  reviewed_at?: string | null;
  reviewed_by?: string | null;
  notes?: string | null;
  content_hash: string;
  supersedes_profile_id?: number | null;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PreparationOccurrenceInput {
  occurrence_id: string;
  recipe_id: string;
  required_finish_minute: number;
  servings: number;
  priority: number;
}

export interface UnresolvedPreparationOccurrence {
  occurrence_id: string;
  recipe_id: string;
  reason_code: string;
  message: string;
}

export interface BuildPreparationTasksResponse {
  tasks: PreparationTaskInput[];
  unresolved: UnresolvedPreparationOccurrence[];
  profile_versions: Record<string, string>;
  duration_policy: "conservative_max" | "optimistic_min";
  warnings: string[];
}

export interface CompileAndScheduleRequest {
  occurrences: PreparationOccurrenceInput[];
  duration_policy: "conservative_max" | "optimistic_min";
  reviewed_only: boolean;
  allow_partial: boolean;
  horizon_minutes: number;
  granularity_minutes: number;
  resources: PreparationResourceInput[];
}

export interface CompileAndScheduleResponse {
  compilation: BuildPreparationTasksResponse;
  schedule: PreparationScheduleResponse | null;
  partial: boolean;
  execution_status: "scheduled" | "blocked_unresolved" | "no_compilable_tasks";
}

export const preparationApi = {
  schedule: (payload: PreparationScheduleRequest) =>
    apiRequest<PreparationScheduleResponse>("/preparation/schedule", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  profiles: (reviewedOnly = true, activeOnly = true) =>
    apiRequest<RecipePreparationProfile[]>(
      `/preparation/profiles?reviewed_only=${reviewedOnly}&active_only=${activeOnly}`,
    ),
  profile: (recipeId: string, reviewedOnly = true) =>
    apiRequest<RecipePreparationProfile>(
      `/preparation/recipes/${encodeURIComponent(recipeId)}/profile?reviewed_only=${reviewedOnly}`,
    ),
  buildTasks: (
    occurrences: PreparationOccurrenceInput[],
    durationPolicy: "conservative_max" | "optimistic_min" = "conservative_max",
    reviewedOnly = true,
  ) =>
    apiRequest<BuildPreparationTasksResponse>("/preparation/build-tasks", {
      method: "POST",
      body: JSON.stringify({
        occurrences,
        duration_policy: durationPolicy,
        reviewed_only: reviewedOnly,
      }),
    }),
  compileAndSchedule: (payload: CompileAndScheduleRequest) =>
    apiRequest<CompileAndScheduleResponse>(
      "/preparation/compile-and-schedule",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),
};
