import { ApiClientError, apiRequest } from "@/lib/http";

export { ApiClientError as PlatformApiError };

const request = apiRequest;

export type HouseholdRole = "viewer" | "editor" | "owner";
export type ReservationStatus = "active" | "released" | "consumed" | "expired";
export type EvidenceRecordStatus =
  | "draft"
  | "external_unverified"
  | "reviewed"
  | "legacy_unreviewed";

export interface QuantityRange {
  quantity_min: number;
  quantity_max: number;
  unit: string;
}

export interface Household {
  id: string;
  owner_user_id: string;
  name: string;
  timezone: string;
  version: number;
  created_at: string;
  updated_at: string;
  current_role?: HouseholdRole | null;
}

export interface HouseholdMember {
  id: number;
  household_id: string;
  display_name: string;
  linked_user_id?: string | null;
  role: HouseholdRole;
  servings_multiplier: number;
  allergies: string[];
  dietary_restrictions: string[];
  disliked_ingredients: string[];
  target_calories?: number | null;
  target_protein_g?: number | null;
  target_carbs_g?: number | null;
  target_fat_g?: number | null;
  active: boolean;
  created_at: string;
}

export interface HouseholdDetail {
  household: Household;
  role: HouseholdRole;
  members: HouseholdMember[];
  active_servings_multiplier: number;
  planning_status: string;
}

export interface HouseholdInvitation {
  id: string;
  household_id: string;
  invited_email: string;
  role: HouseholdRole;
  expires_at: string;
  accepted_at?: string | null;
  revoked_at?: string | null;
  created_by_user_id?: string | null;
  created_at: string;
  acceptance_token?: string | null;
}

export interface PantryItem {
  id: number;
  household_id: string;
  canonical_name: string;
  display_name: string;
  quantity_min: number;
  quantity_max: number;
  unit: string;
  expires_at?: string | null;
  opened_at?: string | null;
  source: string;
  metadata: Record<string, unknown>;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface Leftover {
  id: number;
  household_id: string;
  recipe_id: string;
  source_plan_id?: number | null;
  portions_available: number;
  cooked_at: string;
  expires_at?: string | null;
  frozen: boolean;
  storage_policy_key?: string | null;
  notes?: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface InventoryEvent {
  id: number;
  household_id: string;
  pantry_item_id?: number | null;
  leftover_id?: number | null;
  event_type: string;
  quantity_min: number;
  quantity_max: number;
  unit: string;
  reason?: string | null;
  metadata: Record<string, unknown>;
  idempotency_key?: string | null;
  created_at: string;
}

export interface Reservation {
  id: number;
  household_id: string;
  pantry_item_id?: number | null;
  plan_id: number;
  canonical_name: string;
  quantity_min: number;
  quantity_max: number;
  unit: string;
  status: ReservationStatus;
  expires_at: string;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface ReconciledShoppingItem {
  canonical_name: string;
  display_name: string;
  unit: string;
  required_min: number;
  required_max: number;
  pantry_min: number;
  pantry_max: number;
  buy_min: number;
  buy_max: number;
  coverage_status: string;
  expiring_quantity_max: number;
  source_recipe_ids: string[];
  notes: string[];
}

export interface BatchPrepTask {
  recipe_id: string;
  recipe_name: string;
  total_portions: number;
  first_day: number;
  scheduled_day: number;
  occurrences: number;
  meal_slots: string[];
  storage_guidance_status: string;
  applicable_storage_policies?: string[];
}

export interface HouseholdPlanResult {
  household_id: string;
  plan_id: number;
  plan_schema_version: string;
  household_plan_schema_version: string;
  plan: Record<string, unknown>;
  target_summary: {
    calories: number;
    protein_g: number;
    carbs_g: number;
    fat_g: number;
    member_count: number;
    servings_multiplier: number;
    source_status: string;
    member_sources: Record<string, string>;
  };
  pantry_coverage_score: number;
  reservations: Reservation[];
  warnings: string[];
  diagnostics: Record<string, unknown>;
}

/** Legacy mutable compatibility record. New UI should prefer history types. */
export interface IngredientConversion {
  id: number;
  canonical_name: string;
  from_unit: string;
  to_unit: string;
  multiplier_min: number;
  multiplier_max: number;
  source_name: string;
  source_url: string;
  source_version: string;
  evidence_status: string;
  reviewed_at?: string | null;
  notes?: string | null;
  active: boolean;
}

/** Legacy mutable compatibility record. New UI should prefer history types. */
export interface StoragePolicy {
  id: number;
  policy_key: string;
  food_category: string;
  storage_state: string;
  duration_min_hours?: number | null;
  duration_max_hours?: number | null;
  maximum_temperature_c?: number | null;
  source_name: string;
  source_url: string;
  reviewed_at: string;
  safety_scope: string;
  notes?: string | null;
  active: boolean;
}

export interface IngredientConversionVersion {
  id: number;
  canonical_name: string;
  from_unit: string;
  to_unit: string;
  record_version: string;
  multiplier_min: number;
  multiplier_max: number;
  source_name: string;
  source_url: string;
  source_version: string;
  evidence_status: EvidenceRecordStatus;
  reviewed_at?: string | null;
  reviewed_by?: string | null;
  notes?: string | null;
  content_hash: string;
  supersedes_conversion_id?: number | null;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface StoragePolicyVersion {
  id: number;
  policy_key: string;
  policy_version: string;
  food_category: string;
  storage_state: string;
  duration_min_hours?: number | null;
  duration_max_hours?: number | null;
  maximum_temperature_c?: number | null;
  source_name: string;
  source_url: string;
  source_version: string;
  evidence_status: EvidenceRecordStatus;
  reviewed_at?: string | null;
  reviewed_by?: string | null;
  safety_scope: string;
  notes?: string | null;
  content_hash: string;
  supersedes_policy_id?: number | null;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ReviewedConversionResult {
  canonical_name: string;
  from_unit: string;
  to_unit: string;
  input_quantity_min: number;
  input_quantity_max: number;
  output_quantity_min: number;
  output_quantity_max: number;
  conversion_record_id: number;
  conversion_record_version: string;
  conversion_content_hash: string;
  source_name: string;
  source_url: string;
  source_version: string;
  evidence_status: EvidenceRecordStatus;
  reviewed_at?: string | null;
  reviewed_by?: string | null;
}

export interface SubstitutionCandidate {
  ingredient: string;
  replacement: string;
  role: string;
  ratio?: number | null;
  score: number;
  reasons: string[];
  warnings: string[];
}

export interface ResearchCollection<T = Record<string, unknown>> {
  collection: string;
  count: number;
  items: T[];
}

export interface ResearchCatalogResponse {
  catalog: Record<string, unknown>;
  summary: Record<string, Record<string, number>>;
  implemented_components: Record<string, unknown>;
}

const encode = encodeURIComponent;
const body = (value: unknown) => JSON.stringify(value);

export const householdApi = {
  create: (name: string, timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC") =>
    request<Household>("/households", { method: "POST", body: body({ name, timezone }) }),
  list: () => request<Household[]>("/households"),
  get: (id: string) => request<HouseholdDetail>(`/households/${encode(id)}`),
  addMember: (id: string, payload: Record<string, unknown>) =>
    request<HouseholdMember>(`/households/${encode(id)}/members`, { method: "POST", body: body(payload) }),
  updateMember: (id: string, memberId: number, payload: Record<string, unknown>) =>
    request<HouseholdMember>(`/households/${encode(id)}/members/${memberId}`, { method: "PATCH", body: body(payload) }),
  createInvitation: (id: string, payload: { email: string; role: Exclude<HouseholdRole, "owner">; expires_in_hours?: number }) =>
    request<HouseholdInvitation>(`/households/${encode(id)}/invitations`, { method: "POST", body: body(payload) }),
  invitations: (id: string, includeClosed = false) =>
    request<HouseholdInvitation[]>(`/households/${encode(id)}/invitations?include_closed=${includeClosed}`),
  revokeInvitation: (id: string, invitationId: string) =>
    request<HouseholdInvitation>(`/households/${encode(id)}/invitations/${encode(invitationId)}`, { method: "DELETE" }),
  acceptInvitation: (token: string) =>
    request<HouseholdMember>("/households/invitations/accept", { method: "POST", body: body({ token }) }),
  pantry: (id: string, includeEmpty = false) =>
    request<PantryItem[]>(`/households/${encode(id)}/pantry?include_empty=${includeEmpty}`),
  addPantry: (id: string, payload: Record<string, unknown>) =>
    request<PantryItem>(`/households/${encode(id)}/pantry`, { method: "POST", body: body(payload) }),
  consumePantry: (id: string, itemId: number, payload: Record<string, unknown>) =>
    request<PantryItem>(`/households/${encode(id)}/pantry/${itemId}/consume`, { method: "POST", body: body(payload) }),
  discardPantry: (id: string, itemId: number, payload: Record<string, unknown>) =>
    request<PantryItem>(`/households/${encode(id)}/pantry/${itemId}/discard`, { method: "POST", body: body(payload) }),
  adjustPantry: (id: string, itemId: number, payload: Record<string, unknown>) =>
    request<PantryItem>(`/households/${encode(id)}/pantry/${itemId}`, { method: "PUT", body: body(payload) }),
  events: (id: string, limit = 100) =>
    request<InventoryEvent[]>(`/households/${encode(id)}/inventory-events?limit=${limit}`),
  leftovers: (id: string, includeEmpty = false) =>
    request<Leftover[]>(`/households/${encode(id)}/leftovers?include_empty=${includeEmpty}`),
  leftoverStoragePolicy: (id: string, leftoverId: number) =>
    request<StoragePolicyVersion>(
      `/food-evidence/history/households/${encode(id)}/leftovers/${leftoverId}/storage-policy`,
    ),
  addLeftover: (id: string, payload: Record<string, unknown>) =>
    request<Leftover>(`/households/${encode(id)}/leftovers`, { method: "POST", body: body(payload) }),
  consumeLeftover: (id: string, leftoverId: number, payload: Record<string, unknown>) =>
    request<Leftover>(`/households/${encode(id)}/leftovers/${leftoverId}/consume`, { method: "POST", body: body(payload) }),
  generatePlan: (id: string, payload: { days?: number; reserve_inventory?: boolean; reservation_hours?: number; include_inactive_members?: boolean }) =>
    request<HouseholdPlanResult>(`/households/${encode(id)}/plans`, { method: "POST", body: body(payload) }),
  reconcileShopping: (id: string) =>
    request<ReconciledShoppingItem[]>(`/households/${encode(id)}/shopping-reconciliation`),
  batchPrep: (id: string) => request<BatchPrepTask[]>(`/households/${encode(id)}/batch-prep`),
  reservations: (id: string, includeClosed = false) =>
    request<Reservation[]>(`/households/${encode(id)}/reservations?include_closed=${includeClosed}`),
  releaseReservations: (id: string, planId: number, payload: Record<string, unknown> = {}) =>
    request<Reservation[]>(`/households/${encode(id)}/plans/${planId}/reservations/release`, { method: "POST", body: body(payload) }),
  commitReservations: (id: string, planId: number, payload: Record<string, unknown> = {}) =>
    request<Reservation[]>(`/households/${encode(id)}/plans/${planId}/reservations/commit`, { method: "POST", body: body(payload) }),
};

export const evidenceApi = {
  conversions: (ingredient?: string) =>
    request<IngredientConversion[]>(`/food-evidence/conversions${ingredient ? `?ingredient=${encode(ingredient)}` : ""}`),
  convert: (payload: Record<string, unknown>) =>
    request<Record<string, unknown>>("/food-evidence/convert", { method: "POST", body: body(payload) }),
  storagePolicies: (foodCategory?: string, storageState?: string) => {
    const params = new URLSearchParams();
    if (foodCategory) params.set("food_category", foodCategory);
    if (storageState) params.set("storage_state", storageState);
    const suffix = params.size ? `?${params.toString()}` : "";
    return request<StoragePolicy[]>(`/food-evidence/storage-policies${suffix}`);
  },
};

export const evidenceHistoryApi = {
  conversions: (options: { activeOnly?: boolean; reviewedOnly?: boolean } = {}) => {
    const params = new URLSearchParams();
    params.set("active_only", String(options.activeOnly ?? true));
    params.set("reviewed_only", String(options.reviewedOnly ?? false));
    return request<IngredientConversionVersion[]>(
      `/food-evidence/history/conversions?${params.toString()}`,
    );
  },
  convertReviewed: (payload: {
    canonical_name: string;
    quantity_min: number;
    quantity_max: number;
    from_unit: string;
    to_unit: string;
  }) =>
    request<ReviewedConversionResult>("/food-evidence/history/convert-reviewed", {
      method: "POST",
      body: body(payload),
    }),
  storagePolicies: (options: { activeOnly?: boolean; reviewedOnly?: boolean } = {}) => {
    const params = new URLSearchParams();
    params.set("active_only", String(options.activeOnly ?? true));
    params.set("reviewed_only", String(options.reviewedOnly ?? false));
    return request<StoragePolicyVersion[]>(
      `/food-evidence/history/storage-policies?${params.toString()}`,
    );
  },
  activeStoragePolicy: (policyKey: string) =>
    request<StoragePolicyVersion>(
      `/food-evidence/history/storage-policies/${encode(policyKey)}/active-reviewed`,
    ),
};

export const substitutionApi = {
  suggest: (payload: Record<string, unknown>) =>
    request<SubstitutionCandidate[]>("/substitutions/suggest", { method: "POST", body: body(payload) }),
};

export const nutritionDataApi = {
  search: (query: string, pageSize = 25) =>
    request<Record<string, unknown>>(`/nutrition-data/search?q=${encode(query)}&page_size=${pageSize}`),
  food: (fdcId: number) => request<Record<string, unknown>>(`/nutrition-data/foods/${fdcId}`),
};

export const researchApi = {
  catalog: () => request<ResearchCatalogResponse>("/research/catalog"),
  implementedComponents: () => request<Record<string, unknown>>("/research/implemented-components"),
  collection: <T = Record<string, unknown>>(name: string, readiness?: string, risk?: string) => {
    const params = new URLSearchParams();
    if (readiness) params.set("readiness", readiness);
    if (risk) params.set("risk", risk);
    const suffix = params.size ? `?${params.toString()}` : "";
    return request<ResearchCollection<T>>(`/research/${encode(name)}${suffix}`);
  },
  item: (collection: string, id: string) =>
    request<Record<string, unknown>>(`/research/${encode(collection)}/${encode(id)}`),
  datasetCard: (id: string, version = "unversioned") =>
    request<Record<string, unknown>>(`/research/cards/datasets/${encode(id)}?version=${encode(version)}`),
  modelCard: (id: string, version = "unversioned") =>
    request<Record<string, unknown>>(`/research/cards/models/${encode(id)}?version=${encode(version)}`),
  validateRun: (config: Record<string, unknown>) =>
    request<Record<string, unknown>>("/research/validate-run-config", { method: "POST", body: body(config) }),
  numericDrift: (payload: Record<string, unknown>) =>
    request<Record<string, unknown>>("/research/drift/numeric", { method: "POST", body: body(payload) }),
};
