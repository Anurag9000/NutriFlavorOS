import { apiRequest } from "@/lib/http";

export type PreparationTaskExecutionEligibilityReason =
  | "eligible"
  | "schedule_not_approved"
  | "source_schedule_has_accepted_replacement";

export interface PreparationTaskExecutionEligibilityView {
  schedule_id: number;
  household_id: string;
  schedule_version: number;
  schedule_status: string;
  eligible: boolean;
  reason_code: PreparationTaskExecutionEligibilityReason;
  task_event_count: number;
  accepted_proposal_id: number | null;
  acceptance_id: number | null;
  replacement_schedule_id: number | null;
  replacement_schedule_status: string | null;
  replacement_schedule_version: number | null;
}

const path = (householdId: string, scheduleId: number) =>
  `/households/${encodeURIComponent(householdId)}/preparation-operations/` +
  `schedules/${scheduleId}/task-execution-eligibility`;

export const preparationTaskExecutionEligibilityApi = {
  get: (householdId: string, scheduleId: number) =>
    apiRequest<PreparationTaskExecutionEligibilityView>(
      path(householdId, scheduleId),
    ),
};
