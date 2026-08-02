import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import HouseholdPlanReviewPage from "@/pages/HouseholdPlanReview";

const mocks = vi.hoisted(() => ({
  toast: vi.fn(),
  householdList: vi.fn(),
  householdGet: vi.fn(),
  planList: vi.fn(),
  approve: vi.fn(),
  cancel: vi.fn(),
  events: vi.fn(),
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
    approve: mocks.approve,
    cancel: mocks.cancel,
    events: mocks.events,
  },
}));

const household = {
  id: "review-home",
  owner_user_id: "owner@example.test",
  name: "Review home",
  timezone: "UTC",
  version: 1,
  created_at: "2026-08-02T00:00:00Z",
  updated_at: "2026-08-02T00:00:00Z",
  current_role: "owner",
};

const recipe = {
  id: "recipe-1",
  name: "Reviewed dinner",
  description: "Fixture",
  ingredients: [],
  ingredient_lines: [],
  servings: 2,
  calories: 400,
  macros: {},
  flavor_profile: {},
  tags: [],
  instructions: ["Cook"],
  estimated_cost: 100,
  nutrition_basis: "per_serving",
};

function plan(
  id: number,
  status: "draft" | "approved" | "cancelled",
  version: number,
) {
  return {
    id,
    household_id: household.id,
    user_id: household.owner_user_id,
    schema_version: "2",
    plan: {
      user_id: household.owner_user_id,
      days: [
        {
          day: 1,
          meals: { dinner: recipe },
          portions: { dinner: 2 },
          total_stats: {},
          scores: {},
        },
      ],
      shopping_list: {},
      prep_timeline: { "1": [] },
      overall_stats: {},
      optimization: null,
      warnings: ["Experimental planner output"],
    },
    status,
    version,
    approved_by_user_id: status === "approved" ? household.owner_user_id : null,
    approved_at: status === "approved" ? "2026-08-02T01:00:00Z" : null,
    cancelled_at: status === "cancelled" ? "2026-08-02T02:00:00Z" : null,
    cancellation_reason: status === "cancelled" ? "Obsolete plan" : null,
    created_at: "2026-08-02T00:00:00Z",
    updated_at: "2026-08-02T00:00:00Z",
  };
}

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
        <HouseholdPlanReviewPage />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  mocks.householdList.mockResolvedValue([household]);
  mocks.planList.mockResolvedValue([
    plan(10, "draft", 1),
    plan(11, "approved", 2),
  ]);
  mocks.approve.mockResolvedValue(plan(10, "approved", 2));
  mocks.cancel.mockResolvedValue(plan(11, "cancelled", 3));
  mocks.events.mockResolvedValue([
    {
      id: 1,
      plan_id: 11,
      household_id: household.id,
      event_type: "approved",
      actor_user_id: household.owner_user_id,
      from_status: "draft",
      to_status: "approved",
      reason: "Reviewed household plan",
      metadata: {},
      idempotency_key: "approve-event-1",
      request_fingerprint: "a".repeat(64),
      created_at: "2026-08-02T01:00:00Z",
    },
  ]);
});

describe("Household plan review workspace", () => {
  it("requires an explicit reason and submits the exact optimistic version", async () => {
    renderPage();

    expect(await screen.findByText("Household plan #10")).toBeInTheDocument();
    expect(screen.getByText("Household plan #11")).toBeInTheDocument();
    expect(screen.getByText("Eligible exact source plan")).toBeInTheDocument();

    const approve = screen.getByRole("button", {
      name: "Approve exact plan version",
    });
    expect(approve).toBeDisabled();

    const reasonInputs = screen.getAllByLabelText("Human decision reason");
    fireEvent.change(reasonInputs[0], {
      target: { value: "Reviewed meals, portions, and household constraints" },
    });
    expect(approve).toBeEnabled();
    fireEvent.click(approve);

    await waitFor(() => expect(mocks.approve).toHaveBeenCalledTimes(1));
    const [householdId, planId, payload] = mocks.approve.mock.calls[0];
    expect(householdId).toBe(household.id);
    expect(planId).toBe(10);
    expect(payload.expected_version).toBe(1);
    expect(payload.reason).toBe(
      "Reviewed meals, portions, and household constraints",
    );
    expect(payload.idempotency_key).toMatch(/^household-plan-approved-/);
    expect(payload.metadata).toEqual({ source: "household_plan_review_ui" });
  });

  it("records cancellation through the same reviewed reason surface", async () => {
    renderPage();
    await screen.findByText("Household plan #10");

    const reasonInputs = screen.getAllByLabelText("Human decision reason");
    fireEvent.change(reasonInputs[1], {
      target: { value: "Approved plan is no longer applicable" },
    });
    const cancelButtons = screen.getAllByRole("button", { name: "Cancel plan" });
    fireEvent.click(cancelButtons[1]);

    await waitFor(() => expect(mocks.cancel).toHaveBeenCalledTimes(1));
    const [, planId, payload] = mocks.cancel.mock.calls[0];
    expect(planId).toBe(11);
    expect(payload.expected_version).toBe(2);
    expect(payload.reason).toBe("Approved plan is no longer applicable");
    expect(payload.idempotency_key).toMatch(/^household-plan-cancelled-/);
  });

  it("loads append-only transition evidence", async () => {
    renderPage();
    await screen.findByText("Household plan #10");

    const historyButtons = screen.getAllByRole("button", {
      name: "Load transition history",
    });
    fireEvent.click(historyButtons[1]);

    expect(await screen.findByText(/Reviewed household plan/)).toBeInTheDocument();
    expect(mocks.events).toHaveBeenCalledWith(household.id, 11);
    expect(screen.getByText(/draft → approved/)).toBeInTheDocument();
  });

  it("keeps mutation controls hidden from a viewer", async () => {
    renderPage("viewer");

    expect(await screen.findByText("Household plan #10")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Approve exact plan version" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Cancel plan" }),
    ).not.toBeInTheDocument();
  });
});
