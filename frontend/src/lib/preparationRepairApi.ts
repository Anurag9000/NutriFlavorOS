import { apiRequest } from "@/lib/http";
import type {
  PreparationScheduleRequest,
  PreparationScheduleResponse,
} from "@/lib/preparationOperationsApi";

export type PreparationRepairStrategy =
  | "greedy_min_change"
  | "bounded_exact_min_change";

export interface PreparationRepairWeights {
  unscheduled_task: number;
  changed_task: number;
  displacement_minute: number;
  makespan_minute: number;
}

export interface PreparationScheduleRepairRequest {
  previous_request: PreparationScheduleRequest;
  previous_response: PreparationScheduleResponse;
  revised_request: PreparationScheduleRequest;
  immutable_task_ids: string[];
  strategy: PreparationRepairStrategy;
  allow_partial: boolean;
  weights?: PreparationRepairWeights;
  exact_task_limit?: number;
  exact_candidate_limit_per_task?: number;
}

export interface PreparationTaskMovement {
  task_id: string;
  previous_start_minute: number;
  repaired_start_minute: number;
  displacement_minutes: number;
}

export interface PreparationRepairObjective {
  unscheduled_task_count: number;
  changed_task_count: number;
  total_displacement_minutes: number;
  makespan_minutes: number;
  weighted_value: number;
}

export interface PreparationRepairDiagnostics {
  strategy: PreparationRepairStrategy;
  deterministic: boolean;
  explored_states: number;
  pruned_states: number;
  candidate_placements_considered: number;
  preserved_attempt_count: number;
  exact_search_truncated: boolean;
  tie_break_rule: string;
  limitations: string[];
}

export interface PreparationScheduleRepairResult {
  response: PreparationScheduleResponse;
  complete: boolean;
  immutable_task_ids: string[];
  preserved_task_ids: string[];
  moved_tasks: PreparationTaskMovement[];
  added_task_ids: string[];
  removed_task_ids: string[];
  unscheduled_task_ids: string[];
  objective: PreparationRepairObjective;
  diagnostics: PreparationRepairDiagnostics;
  warnings: string[];
  previous_schedule_hash: string | null;
  revised_request_hash: string | null;
  repaired_response_hash: string | null;
  requires_human_acceptance: true;
  accepted: false;
  persistence_performed: false;
}

export const preparationRepairApi = {
  repair: (payload: PreparationScheduleRepairRequest) =>
    apiRequest<PreparationScheduleRepairResult>(
      "/preparation/schedule/repair",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),
};
