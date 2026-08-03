import { apiRequest } from "@/lib/http";

export interface SupportExportSchedule {
  id: number;
  household_id: string;
  status: string;
  version: number;
  schedule_hash: string;
  calendar_version_id: number;
  calendar_content_hash: string;
  source_plan_id: number | null;
  source_plan_version: number | null;
  created_at: string;
  updated_at: string;
  [key: string]: unknown;
}

export interface SupportExportDerivation {
  schedule_id: number;
  household_id: string;
  schedule_version: number;
  schedule_status: string;
  schedule_hash: string;
  derivation_method: string;
  evidence_complete: boolean;
  source_repair_proposal_id: number | null;
  source_repair_acceptance_id: number | null;
  source_schedule_id: number | null;
  warnings: string[];
  [key: string]: unknown;
}

export interface SupportExportEligibility {
  schedule_id: number;
  household_id: string;
  schedule_version: number;
  schedule_status: string;
  eligible: boolean;
  reason_code: string;
  task_event_count: number;
  accepted_proposal_id: number | null;
  acceptance_id: number | null;
  replacement_schedule_id: number | null;
  replacement_schedule_status: string | null;
  replacement_schedule_version: number | null;
}

export interface SupportExportProposal {
  id: number;
  status: string;
  version: number;
  source_schedule_id: number;
  source_schedule_version: number;
  repair_request_hash: string;
  repair_result_hash: string;
  [key: string]: unknown;
}

export interface PreparationScheduleSupportExport {
  document_version: "preparation-schedule-support-export-v1";
  household_id: string;
  schedule_id: number;
  database_dialect: string;
  snapshot_isolation: "repeatable_read" | "serializable";
  snapshot_read_only: true;
  snapshot_marker: string | null;
  snapshot_started_at: string;
  snapshot_completed_at: string;
  schedule: SupportExportSchedule;
  schedule_events: Array<Record<string, unknown>>;
  derivation: SupportExportDerivation;
  task_execution_eligibility: SupportExportEligibility;
  task_execution: {
    schedule: SupportExportSchedule;
    tasks: Array<Record<string, unknown>>;
    events: Array<Record<string, unknown>>;
    planned_count: number;
    in_progress_count: number;
    completed_count: number;
    skipped_count: number;
    terminal_count: number;
    remaining_count: number;
  };
  related_repair_proposals: SupportExportProposal[];
  repair_acceptances: Array<Record<string, unknown>>;
  repair_proposal_events: Record<string, Array<Record<string, unknown>>>;
  evidence_hash: string;
  mutation_performed: false;
  actual_execution_verified: false;
  food_safety_verified: false;
}

const scope = (householdId: string) =>
  `/households/${encodeURIComponent(householdId)}/preparation-operations`;

export function supportExportFilename(
  value: PreparationScheduleSupportExport,
): string {
  const safeHousehold = value.household_id.replace(/[^A-Za-z0-9_.-]+/g, "-");
  return `preparation-support-${safeHousehold}-schedule-${value.schedule_id}-${value.evidence_hash.slice(0, 12)}.json`;
}

export function serializeSupportExport(
  value: PreparationScheduleSupportExport,
): string {
  return `${JSON.stringify(value, null, 2)}\n`;
}

export const preparationScheduleSupportExportApi = {
  get: (householdId: string, scheduleId: number) =>
    apiRequest<PreparationScheduleSupportExport>(
      `${scope(householdId)}/schedules/${scheduleId}/support-export`,
    ),
};
