import { apiRequest } from "@/lib/http";
import type { PreparationScheduleRepairResult } from "@/lib/preparationRepairApi";
import type { PreparationScheduleRequest } from "@/lib/preparationOperationsApi";

export type PreparationRepairProposalStatus =
  | "proposed"
  | "accepted"
  | "rejected"
  | "invalidated";

export type PreparationRepairProposalEventType =
  | "created"
  | "accepted"
  | "rejected"
  | "invalidated";

export interface PreparationRepairProposalCreateRequest {
  source_schedule_id: number;
  expected_source_version: number;
  target_calendar_version_id: number;
  revised_request: PreparationScheduleRequest;
  immutable_task_ids: string[];
  strategy: "greedy_min_change" | "bounded_exact_min_change";
  weights?: {
    unscheduled_task: number;
    changed_task: number;
    displacement_minute: number;
    makespan_minute: number;
  };
  exact_task_limit?: number;
  exact_candidate_limit_per_task?: number;
  notes?: string | null;
  acknowledge_non_acceptance: true;
  acknowledge_non_persistence: true;
  idempotency_key: string;
}

export interface PreparationRepairProposalRejectRequest {
  expected_version: number;
  reason: string;
  idempotency_key: string;
  metadata?: Record<string, unknown>;
}

export interface PreparationRepairProposalAcceptRequest {
  expected_proposal_version: number;
  expected_source_schedule_version: number;
  expected_source_schedule_hash: string;
  expected_source_schedule_request_hash: string;
  expected_target_calendar_content_hash: string;
  expected_repair_request_hash: string;
  expected_repair_result_hash: string;
  expected_revised_request_hash: string;
  expected_repaired_response_hash: string;
  acknowledged_task_ids: string[];
  reason: string;
  acknowledge_creates_new_draft_only: true;
  idempotency_key: string;
  metadata?: Record<string, unknown>;
}

export interface PreparationRepairProposalView {
  id: number;
  household_id: string;
  source_schedule_id: number;
  source_schedule_version: number;
  source_schedule_hash: string;
  source_schedule_request_hash: string;
  target_calendar_version_id: number;
  target_calendar_content_hash: string;
  repair_request_hash: string;
  repair_result_hash: string;
  revised_request_hash: string;
  repaired_response_hash: string;
  required_acknowledgement_task_ids: string[];
  repair_result: PreparationScheduleRepairResult;
  status: PreparationRepairProposalStatus;
  version: number;
  notes: string | null;
  created_by_user_id: string;
  rejected_by_user_id: string | null;
  rejected_at: string | null;
  rejection_reason: string | null;
  current: boolean;
  stale_reasons: string[];
  accepted: boolean;
  schedule_persistence_performed: boolean;
  accepted_schedule_id: number | null;
  accepted_schedule_hash: string | null;
  accepted_by_user_id: string | null;
  accepted_at: string | null;
  acceptance_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface PreparationRepairProposalEventView {
  id: number;
  proposal_id: number;
  household_id: string;
  event_type: PreparationRepairProposalEventType;
  actor_user_id: string;
  from_status: PreparationRepairProposalStatus | null;
  to_status: PreparationRepairProposalStatus;
  reason: string;
  metadata: Record<string, unknown>;
  proposal_version_before: number;
  proposal_version_after: number;
  idempotency_key: string;
  request_fingerprint: string;
  created_at: string;
}

export interface PreparationRepairProposalAcceptanceView {
  id: number;
  household_id: string;
  proposal_id: number;
  proposal_version_before: number;
  proposal_version_after: number;
  source_schedule_id: number;
  source_schedule_version: number;
  created_schedule_id: number;
  created_schedule_version: 1;
  created_schedule_status: "draft";
  created_schedule_hash: string;
  derivation_method: "deterministic_minimal_change_preparation_repair_v1";
  source_schedule_hash: string;
  source_schedule_request_hash: string;
  target_calendar_content_hash: string;
  repair_request_hash: string;
  repair_result_hash: string;
  revised_request_hash: string;
  repaired_response_hash: string;
  acknowledged_task_ids: string[];
  reason: string;
  actor_user_id: string;
  metadata: Record<string, unknown>;
  idempotency_key: string;
  request_fingerprint: string;
  created_at: string;
}

export interface PreparationRepairProposalAcceptedDraftView {
  proposal: PreparationRepairProposalView;
  acceptance: PreparationRepairProposalAcceptanceView;
  accepted: true;
  schedule_persistence_performed: true;
  approval_performed: false;
  execution_performed: false;
}

function collection(householdId: string): string {
  return `/households/${householdId}/preparation-operations/repair-proposals`;
}

export const preparationRepairProposalApi = {
  create: (
    householdId: string,
    payload: PreparationRepairProposalCreateRequest,
  ) =>
    apiRequest<PreparationRepairProposalView>(collection(householdId), {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  list: (
    householdId: string,
    statuses?: PreparationRepairProposalStatus[],
  ) => {
    const query = new URLSearchParams();
    for (const status of statuses ?? []) query.append("status", status);
    const suffix = query.size ? `?${query.toString()}` : "";
    return apiRequest<PreparationRepairProposalView[]>(
      `${collection(householdId)}${suffix}`,
    );
  },

  get: (householdId: string, proposalId: number) =>
    apiRequest<PreparationRepairProposalView>(
      `${collection(householdId)}/${proposalId}`,
    ),

  acceptance: (householdId: string, proposalId: number) =>
    apiRequest<PreparationRepairProposalAcceptanceView>(
      `${collection(householdId)}/${proposalId}/acceptance`,
    ),

  events: (householdId: string, proposalId: number) =>
    apiRequest<PreparationRepairProposalEventView[]>(
      `${collection(householdId)}/${proposalId}/events`,
    ),

  accept: (
    householdId: string,
    proposalId: number,
    payload: PreparationRepairProposalAcceptRequest,
  ) =>
    apiRequest<PreparationRepairProposalAcceptedDraftView>(
      `${collection(householdId)}/${proposalId}/accept`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),

  reject: (
    householdId: string,
    proposalId: number,
    payload: PreparationRepairProposalRejectRequest,
  ) =>
    apiRequest<PreparationRepairProposalView>(
      `${collection(householdId)}/${proposalId}/reject`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),
};
