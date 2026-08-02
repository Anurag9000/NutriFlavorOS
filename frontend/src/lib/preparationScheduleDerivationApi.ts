import { apiRequest } from "@/lib/http";

export type PreparationScheduleDerivationMethod =
  | "deterministic_dependency_aware_resource_scheduler_v2"
  | "deterministic_minimal_change_preparation_repair_v1";

export interface PreparationScheduleDerivationEvidenceView {
  schedule_id: number;
  household_id: string;
  schedule_version: number;
  schedule_status: string;
  schedule_hash: string;
  derivation_method: PreparationScheduleDerivationMethod;
  evidence_complete: true;

  source_repair_proposal_id: number | null;
  source_repair_proposal_version: number | null;
  source_repair_acceptance_id: number | null;
  source_schedule_id: number | null;
  source_schedule_version: number | null;

  source_schedule_hash: string | null;
  source_schedule_request_hash: string | null;
  target_calendar_content_hash: string | null;
  repair_request_hash: string | null;
  repair_result_hash: string | null;
  revised_request_hash: string | null;
  repaired_response_hash: string | null;

  accepted_by_user_id: string | null;
  accepted_at: string | null;
  acceptance_reason: string | null;
  warnings: string[];
  created_at: string;
  updated_at: string;
}

export interface PreparationScheduleDerivationCoverageView {
  household_id: string;
  generated_at: string;
  schedule_total: number;
  original_schedule_count: number;
  repair_schedule_count: number;
  unknown_method_count: number;
  complete_derivation_count: number;
  incomplete_derivation_count: number;
  accepted_proposal_count: number;
  acceptance_record_count: number;
  repaired_draft_count: number;
  repaired_approved_count: number;
  repaired_execution_history_count: number;
  method_counts: Record<string, number>;
  derivation_coverage_ratio: number;
  repair_acceptance_link_coverage_ratio: number;
  latest_acceptance_at: string | null;
  warnings: string[];
}

const scope = (householdId: string) =>
  `/households/${encodeURIComponent(householdId)}/preparation-operations`;

export const preparationScheduleDerivationApi = {
  get: (householdId: string, scheduleId: number) =>
    apiRequest<PreparationScheduleDerivationEvidenceView>(
      `${scope(householdId)}/schedules/${scheduleId}/derivation`,
    ),

  coverage: (householdId: string) =>
    apiRequest<PreparationScheduleDerivationCoverageView>(
      `${scope(householdId)}/schedule-derivation-coverage`,
    ),
};
