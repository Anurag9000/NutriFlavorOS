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
  metadata: Record<string, unknown>;
}

export interface UnscheduledPreparationTask {
  task_id: string;
  reason_code: string;
  message: string;
  missing_resources: string[];
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

export const preparationApi = {
  schedule: (payload: PreparationScheduleRequest) =>
    apiRequest<PreparationScheduleResponse>("/preparation/schedule", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
