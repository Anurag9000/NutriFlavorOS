import { apiRequest } from "@/lib/http";
import type { PreparationOccurrenceSetDocument } from "@/lib/preparationOperationsApi";

const request = apiRequest;
const encode = encodeURIComponent;
const body = (value: unknown) => JSON.stringify(value);

export type HouseholdPlanStatus = "draft" | "approved" | "cancelled";
export type HouseholdPlanEventType = "approved" | "cancelled";
export type DurationPolicy = "conservative_max" | "optimistic_min";
export type PreparationProfileAvailability =
  | "reviewed_compatible"
  | "reviewed_incompatible_servings"
  | "missing_reviewed_profile";

export interface PlanRecipe {
  id: string;
  name: string;
  description: string;
  image_url?: string | null;
  ingredients: string[];
  ingredient_lines: unknown[];
  servings: number;
  calories: number;
  macros: Record<string, number>;
  flavor_profile: Record<string, number>;
  tags: string[];
  cuisine?: string | null;
  instructions: string[];
  estimated_cost?: number | null;
  source_name?: string | null;
  source_url?: string | null;
  source_version?: string | null;
  nutrition_basis: string;
}

export interface PlanDay {
  day: number;
  meals: Record<string, PlanRecipe>;
  portions: Record<string, number>;
  total_stats: Record<string, unknown>;
  scores: Record<string, number>;
}

export interface HouseholdPlanDocument {
  user_id: string;
  days: PlanDay[];
  shopping_list?: Record<string, Record<string, unknown>> | null;
  prep_timeline?: Record<string, string[]> | null;
  overall_stats?: Record<string, unknown> | null;
  optimization?: Record<string, unknown> | null;
  warnings: string[];
}

export interface PersistedHouseholdPlanView {
  id: number;
  household_id: string;
  user_id: string;
  schema_version: string;
  plan: HouseholdPlanDocument;
  status: HouseholdPlanStatus;
  version: number;
  approved_by_user_id: string | null;
  approved_at: string | null;
  cancelled_at: string | null;
  cancellation_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface HouseholdPlanTransitionRequest {
  expected_version: number;
  reason: string;
  idempotency_key: string;
  metadata: Record<string, unknown>;
}

export interface HouseholdPlanEventView {
  id: number;
  plan_id: number;
  household_id: string;
  event_type: HouseholdPlanEventType;
  actor_user_id: string;
  from_status: HouseholdPlanStatus;
  to_status: HouseholdPlanStatus;
  reason: string;
  metadata: Record<string, unknown>;
  idempotency_key: string;
  request_fingerprint: string;
  created_at: string;
}

export interface ApprovedPlanOccurrenceCandidate {
  occurrence_id: string;
  day: number;
  meal_slot: string;
  recipe_id: string;
  recipe_name: string;
  source_recipe_servings: number;
  planned_portion_multiplier: number;
  planned_servings: number;
  preparation_profile_status: PreparationProfileAvailability;
  preparation_profile_id: number | null;
  preparation_profile_version: string | null;
  preparation_profile_content_hash: string | null;
  supported_servings_min: number | null;
  supported_servings_max: number | null;
  warnings: string[];
}

export interface ApprovedPlanOccurrenceCandidatesView {
  household_id: string;
  source_plan_id: number;
  source_plan_version: number;
  generated_at: string;
  candidates: ApprovedPlanOccurrenceCandidate[];
  reviewed_compatible_count: number;
  unresolved_profile_count: number;
  warnings: string[];
}

export interface PlanOccurrenceConfirmation {
  occurrence_id: string;
  include: boolean;
  servings: number | null;
  required_finish_minute: number | null;
  priority: number;
}

export interface ConfirmPlanOccurrenceSetRequest {
  expected_plan_version: number;
  occurrence_set_version: string;
  duration_policy: DurationPolicy;
  confirmations: PlanOccurrenceConfirmation[];
}

export interface ConfirmedPlanOccurrenceSetView {
  household_id: string;
  source_plan_id: number;
  source_plan_version: number;
  occurrence_set: PreparationOccurrenceSetDocument;
  profile_versions: Record<string, string>;
  confirmed_count: number;
  excluded_count: number;
  warnings: string[];
}

const base = (householdId: string) =>
  `/households/${encode(householdId)}/plans`;

export const householdPlanApi = {
  list: (householdId: string, statuses: HouseholdPlanStatus[] = []) => {
    const params = new URLSearchParams();
    for (const status of statuses) params.append("status", status);
    const suffix = params.size ? `?${params.toString()}` : "";
    return request<PersistedHouseholdPlanView[]>(
      `${base(householdId)}${suffix}`,
    );
  },
  get: (householdId: string, planId: number) =>
    request<PersistedHouseholdPlanView>(
      `${base(householdId)}/${planId}`,
    ),
  approve: (
    householdId: string,
    planId: number,
    payload: HouseholdPlanTransitionRequest,
  ) =>
    request<PersistedHouseholdPlanView>(
      `${base(householdId)}/${planId}/approve`,
      { method: "POST", body: body(payload) },
    ),
  cancel: (
    householdId: string,
    planId: number,
    payload: HouseholdPlanTransitionRequest,
  ) =>
    request<PersistedHouseholdPlanView>(
      `${base(householdId)}/${planId}/cancel`,
      { method: "POST", body: body(payload) },
    ),
  events: (householdId: string, planId: number) =>
    request<HouseholdPlanEventView[]>(
      `${base(householdId)}/${planId}/events`,
    ),
  occurrenceCandidates: (
    householdId: string,
    planId: number,
    expectedPlanVersion: number,
  ) =>
    request<ApprovedPlanOccurrenceCandidatesView>(
      `${base(householdId)}/${planId}/preparation-occurrences/candidates?expected_plan_version=${expectedPlanVersion}`,
    ),
  confirmOccurrences: (
    householdId: string,
    planId: number,
    payload: ConfirmPlanOccurrenceSetRequest,
  ) =>
    request<ConfirmedPlanOccurrenceSetView>(
      `${base(householdId)}/${planId}/preparation-occurrences/confirm`,
      { method: "POST", body: body(payload) },
    ),
};
