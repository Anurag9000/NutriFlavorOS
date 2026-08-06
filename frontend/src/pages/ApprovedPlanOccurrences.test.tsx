import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ApprovedPlanOccurrencesPage from "@/pages/ApprovedPlanOccurrences";

const mocks = vi.hoisted(() => ({
  toast: vi.fn(),
  householdList: vi.fn(),
  householdGet: vi.fn(),
  planList: vi.fn(),
  occurrenceCandidates: vi.fn(),
  confirmOccurrences: vi.fn(),
}));

vi.mock("@/components/AppLayout", () => ({
  default: ({ children }: { children: ReactNode }) => <main>{children}</main>,
}));

vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({ toast: mocks.toast }),
}));

vi.mock("@/lib/platformApi", () => ({
  householdApi: {
    list: mocks.householdList,
    get: mocks.householdGet,
  },
}));

vi.mock("@/lib/householdPlanApi", () => ({
  householdPlanApi: {
    list: mocks.planList,
    occurrenceCandidates: mocks.occurrenceCandidates,
    confirmOccurrences: mocks.confirmOccurrences,
  },
}));

const household = {
  id: "occurrence-ui-home",
  owner_user_id: "owner@example.test",
  name: "Occurrence UI home",
  timezone: "UTC",
  version: 1,
  created_at: "2026-08-02T00:00:00Z",
  updated_at: "2026-08-02T00:00:00Z",
  current_role: "owner",
};

const approvedPlan = {
  id: 42,
  household_id: household.id,
  user_id: household.owner_user_id,
  schema_version: "2",
  plan: {
    user_id: household.owner_user_id,
    days: [],
    shopping_list: {},
    prep_timeline: {},
    overall_stats: {},
    optimization: null,
    warnings: [],
  },
  status: "approved" as const,
  version: 2,
  approved_by_user_id: household.owner_user_id,
  approved_at: "2026-08-02T01:00:00Z",
  cancelled_at: null,
  cancellation_reason: null,
  created_at: "2026-08-02T00:00:00Z",
  updated_at: "2026-08-02T01:00:00Z",
};

const compatibleCandidate = {
  occurrence_id: "day-1.dinner-compatible",
  day: 1,
  meal_slot: "Dinner",
  recipe_id: "recipe-compatible",
  recipe_name: "Compatible dinner",
  source_recipe_servings: 2,
  planned_servings: 2,
  recipe_batch_scale: 1,
  preparation_profile_status: "reviewed_compatible" as const,
  preparation_profile_id: 7,
  preparation_profile_version: "v1",
  preparation_profile_content_hash: "a".repeat(64),
  supported_servings_min: 1,
  supported_servings_max: 6,
  warnings: [],
};

const unresolvedCandidate = {
  occurrence_id: "day-1.late-snack-missing",
  day: 1,
  meal_slot: "Late Snack",
  recipe_id: "recipe-missing",
  recipe_name: "Unprofiled snack",
  source_recipe_servings: 1,
  planned_servings: 1,
  recipe_batch_scale: 1,
  preparation_profile_status: "missing_reviewed_profile" as const,
  preparation_profile_id: null,
  preparation_profile_version: null,
  preparation_profile_content_hash: null,
  supported_servings_min: null,
  supported_servings_max: null,
  warnings: ["No active reviewed preparation profile exists for this recipe"],
};

const candidateResponse = {
  household_id: household.id,
  source_plan_id: approvedPlan.id,
  source_plan_version: approvedPlan.version,
  generated_at: "2026-08-02T02:00:00Z",
  candidates: [compatibleCandidate, unresolvedCandidate],
  reviewed_compatible_count: 1,
  unresolved_profile_count: 1,
  warnings: [
    "Required finish minutes are not inferred from meal-slot names and must be entered explicitly",
  ],
};

const confirmedResponse = {
  household_id: household.id,
  source_plan_id: approvedPlan.id,
  source_plan_version: approvedPlan.version,
  occurrence_set: {
    document_version: "preparation-occurrence-set-v1" as const,
    household_id: household.id,
    occurrence_set_version: "plan-42-v2-occurrences-v1",
    duration_policy: "conservative_max" as const,
    occurrences: [
      {
        occurrence_id: compatibleCandidate.occurrence_id,
        recipe_id: compatibleCandidate.recipe_id,
        required_finish_minute: 180,
        servings: 2,
        priority: 3,
      },
    ],
  },
  profile_versions: {
    "recipe-compatible": `profile:7/version:v1/sha256:${"a".repeat(64)}`,
  },
  confirmed_count: 1,
  excluded_count: 1,
  warnings: ["Nothing was persisted"],
};

function renderPage(role: "owner" | "viewer" = "owner") {
  mocks.householdGet.mockResolvedValue({
    household: { ...household, current_role: role },
    role,
    members: [],
    active_servings_multiplier: 0,
    planning_status: "ready",
  });
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={client}>
        <ApprovedPlanOccurrencesPage />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  mocks.householdList.mockResolvedValue([household]);
  mocks.planList.mockResolvedValue([approvedPlan]);
  mocks.occurrenceCandidates.mockResolvedValue(candidateResponse);
  mocks.confirmOccurrences.mockResolvedValue(confirmedResponse);
});

describe("Approved-plan occurrence confirmation", () => {
  it("uses the stored serving count and requires an explicit finish minute", async () => {
    renderPage();

    expect(
      await screen.findByText("Approved-plan preparation occurrences"),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(mocks.planList).toHaveBeenCalledWith(household.id, ["approved"]);
      expect(mocks.occurrenceCandidates).toHaveBeenCalledWith(
        household.id,
        approvedPlan.id,
        approvedPlan.version,
      );
    });

    const compatible = (await screen.findByText("Compatible dinner")).closest("fieldset");
    expect(compatible).not.toBeNull();
    expect(
      within(compatible as HTMLElement).getByLabelText("Include this occurrence"),
    ).toBeChecked();
    expect(
      within(compatible as HTMLElement).getByLabelText("Confirmed servings"),
    ).toHaveValue(2);
    expect(
      within(compatible as HTMLElement).getByLabelText("Required finish minute"),
    ).toHaveValue(null);
    expect(
      within(compatible as HTMLElement).getByText(
        /Source recipe yield 2 servings · planned 2 servings · batch scale 1\.000×/,
      ),
    ).toBeInTheDocument();

    const unresolved = screen.getByText("Unprofiled snack").closest("fieldset");
    expect(unresolved).not.toBeNull();
    expect(
      within(unresolved as HTMLElement).getByLabelText("Include this occurrence"),
    ).not.toBeChecked();
    expect(screen.getByText("1 unresolved profile")).toBeInTheDocument();

    expect(
      screen.getByRole("button", {
        name: "Confirm canonical occurrence document",
      }),
    ).toBeDisabled();
  });

  it("submits an explicit decision for every candidate and renders non-persisted output", async () => {
    renderPage();
    await screen.findByText("Compatible dinner");

    const compatible = screen.getByText("Compatible dinner").closest("fieldset");
    expect(compatible).not.toBeNull();
    fireEvent.change(
      within(compatible as HTMLElement).getByLabelText("Required finish minute"),
      { target: { value: "180" } },
    );
    fireEvent.change(
      within(compatible as HTMLElement).getByLabelText("Priority"),
      { target: { value: "3" } },
    );

    const confirm = screen.getByRole("button", {
      name: "Confirm canonical occurrence document",
    });
    expect(confirm).toBeEnabled();
    fireEvent.click(confirm);

    await waitFor(() =>
      expect(mocks.confirmOccurrences).toHaveBeenCalledTimes(1),
    );
    const [householdId, planId, payload] =
      mocks.confirmOccurrences.mock.calls[0];
    expect(householdId).toBe(household.id);
    expect(planId).toBe(approvedPlan.id);
    expect(payload.expected_plan_version).toBe(approvedPlan.version);
    expect(payload.occurrence_set_version).toBe(
      "plan-42-v2-occurrences-v1",
    );
    expect(payload.duration_policy).toBe("conservative_max");
    expect(payload.confirmations).toEqual([
      {
        occurrence_id: compatibleCandidate.occurrence_id,
        include: true,
        servings: 2,
        required_finish_minute: 180,
        priority: 3,
      },
      {
        occurrence_id: unresolvedCandidate.occurrence_id,
        include: false,
        servings: null,
        required_finish_minute: null,
        priority: 0,
      },
    ]);

    expect(
      await screen.findByLabelText("Confirmed occurrence bundle JSON"),
    ).toHaveValue(JSON.stringify(confirmedResponse, null, 2));
    expect(mocks.toast).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Occurrence document confirmed",
      }),
    );
  });

  it("lets the household explicitly include a previously unresolved meal but relies on server rejection", async () => {
    mocks.confirmOccurrences.mockRejectedValueOnce(
      new Error("Every included occurrence requires reviewed preparation evidence"),
    );
    renderPage();
    await screen.findByText("Compatible dinner");

    const compatible = screen.getByText("Compatible dinner").closest("fieldset");
    const unresolved = screen.getByText("Unprofiled snack").closest("fieldset");
    expect(compatible).not.toBeNull();
    expect(unresolved).not.toBeNull();

    fireEvent.change(
      within(compatible as HTMLElement).getByLabelText("Required finish minute"),
      { target: { value: "180" } },
    );
    fireEvent.click(
      within(unresolved as HTMLElement).getByLabelText("Include this occurrence"),
    );
    fireEvent.change(
      within(unresolved as HTMLElement).getByLabelText("Required finish minute"),
      { target: { value: "240" } },
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "Confirm canonical occurrence document",
      }),
    );

    await waitFor(() =>
      expect(mocks.confirmOccurrences).toHaveBeenCalledTimes(1),
    );
    expect(mocks.toast).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Occurrence confirmation failed",
        variant: "destructive",
      }),
    );
    expect(
      screen.queryByLabelText("Confirmed occurrence bundle JSON"),
    ).not.toBeInTheDocument();
  });

  it("keeps confirmation unavailable to viewers", async () => {
    renderPage("viewer");

    expect(await screen.findByText("Compatible dinner")).toBeInTheDocument();
    expect(
      screen.getByText(/Editor or owner access is required/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: "Confirm canonical occurrence document",
      }),
    ).toBeDisabled();
  });

  it("shows an explicit empty state when no approved plan exists", async () => {
    mocks.planList.mockResolvedValueOnce([]);
    renderPage();

    expect(await screen.findByText("No approved household plan")).toBeInTheDocument();
    expect(mocks.occurrenceCandidates).not.toHaveBeenCalled();
  });
});
