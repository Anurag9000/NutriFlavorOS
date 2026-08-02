import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PreparationRepairProposalInvalidationPage from "@/pages/PreparationRepairProposalInvalidation";

const mocks = vi.hoisted(() => ({
  households: vi.fn(),
  proposals: vi.fn(),
  events: vi.fn(),
  invalidate: vi.fn(),
}));

vi.mock("@/components/AppLayout", () => ({
  default: ({ children }: { children: ReactNode }) => <main>{children}</main>,
}));
vi.mock("@/lib/platformApi", () => ({
  householdApi: { list: mocks.households },
}));
vi.mock("@/lib/preparationRepairProposalApi", () => ({
  preparationRepairProposalApi: {
    list: mocks.proposals,
    events: mocks.events,
    invalidate: mocks.invalidate,
  },
}));

const repairResult = {
  response: {
    method: "deterministic_minimal_change_preparation_repair_v1",
    deterministic: true,
    horizon_minutes: 120,
    granularity_minutes: 5,
    scheduled: [],
    unscheduled: [],
    resource_utilization: {},
    resource_peak_usage: {},
    makespan_minutes: 0,
    diagnostics: {},
  },
  complete: true,
  immutable_task_ids: [],
  preserved_task_ids: [],
  moved_tasks: [
    {
      task_id: "dinner.prep",
      previous_start_minute: 0,
      repaired_start_minute: 5,
      displacement_minutes: 5,
    },
  ],
  added_task_ids: [],
  removed_task_ids: [],
  unscheduled_task_ids: [],
  objective: {
    unscheduled_task_count: 0,
    changed_task_count: 1,
    total_displacement_minutes: 5,
    makespan_minutes: 15,
    weighted_value: 10065,
  },
  diagnostics: {
    strategy: "greedy_min_change",
    deterministic: true,
    explored_states: 0,
    pruned_states: 0,
    candidate_placements_considered: 2,
    preserved_attempt_count: 1,
    exact_search_truncated: false,
    tie_break_rule: "stable task ID and start minute",
    limitations: [],
  },
  warnings: ["Human review and explicit acceptance are required."],
  previous_schedule_hash: "e".repeat(64),
  revised_request_hash: "f".repeat(64),
  repaired_response_hash: "1".repeat(64),
  requires_human_acceptance: true,
  accepted: false,
  persistence_performed: false,
};

const proposal = {
  id: 11,
  household_id: "home-1",
  source_schedule_id: 7,
  source_schedule_version: 2,
  source_schedule_hash: "a".repeat(64),
  source_schedule_request_hash: "b".repeat(64),
  target_calendar_version_id: 3,
  target_calendar_content_hash: "c".repeat(64),
  repair_request_hash: "d".repeat(64),
  repair_result_hash: "e".repeat(64),
  revised_request_hash: "f".repeat(64),
  repaired_response_hash: "1".repeat(64),
  required_acknowledgement_task_ids: ["dinner.prep"],
  repair_result: repairResult,
  status: "proposed",
  version: 1,
  notes: "Review the shift",
  created_by_user_id: "editor@example.test",
  rejected_by_user_id: null,
  rejected_at: null,
  rejection_reason: null,
  current: false,
  stale_reasons: [
    "target_calendar_not_active",
    "source_schedule_version_changed",
  ],
  accepted: false,
  schedule_persistence_performed: false,
  accepted_schedule_id: null,
  accepted_schedule_hash: null,
  accepted_by_user_id: null,
  accepted_at: null,
  acceptance_reason: null,
  created_at: "2026-08-02T00:00:00Z",
  updated_at: "2026-08-02T00:00:00Z",
};

const createdEvent = {
  id: 1,
  proposal_id: 11,
  household_id: "home-1",
  event_type: "created",
  actor_user_id: "editor@example.test",
  from_status: null,
  to_status: "proposed",
  reason: "Server-recomputed preparation repair proposal created",
  metadata: {},
  proposal_version_before: 0,
  proposal_version_after: 1,
  idempotency_key: "repair-proposal-created:11",
  request_fingerprint: "2".repeat(64),
  created_at: "2026-08-02T00:00:00Z",
};

function household(role: "owner" | "editor" | "viewer") {
  return {
    id: "home-1",
    owner_user_id: "owner@example.test",
    name: "Home One",
    timezone: "UTC",
    version: 1,
    created_at: "2026-08-02T00:00:00Z",
    updated_at: "2026-08-02T00:00:00Z",
    current_role: role,
  };
}

function renderPage() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={client}>
        <PreparationRepairProposalInvalidationPage />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.stubGlobal("crypto", { randomUUID: vi.fn(() => "fixed-uuid") });
  mocks.households.mockResolvedValue([household("owner")]);
  mocks.proposals.mockResolvedValue([proposal]);
  mocks.events.mockResolvedValue([createdEvent]);
  mocks.invalidate.mockResolvedValue({
    ...proposal,
    status: "invalidated",
    version: 2,
    stale_reasons: ["proposal_status_invalidated"],
  });
});

describe("Preparation repair proposal invalidation administration", () => {
  it("shows stale evidence and keeps owner submission disabled until confirmed", async () => {
    renderPage();

    expect(
      await screen.findByRole("heading", {
        name: "Proposal invalidation administration",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("target calendar not active")).toBeInTheDocument();
    expect(screen.getByText("source schedule version changed")).toBeInTheDocument();
    const button = screen.getByRole("button", { name: "Invalidate proposal" });
    expect(button).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Invalidation reason"), {
      target: { value: "Withdraw superseded evidence" },
    });
    expect(button).toBeDisabled();
    fireEvent.click(
      screen.getByRole("checkbox", {
        name: /keeps immutable history, creates no schedule/i,
      }),
    );
    expect(button).toBeEnabled();
  });

  it("submits exact owner historical-only invalidation evidence", async () => {
    renderPage();
    await screen.findByText("Owner invalidation");

    fireEvent.change(screen.getByLabelText("Invalidation reason"), {
      target: { value: "Withdraw superseded evidence" },
    });
    fireEvent.click(
      screen.getByRole("checkbox", {
        name: /keeps immutable history, creates no schedule/i,
      }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Invalidate proposal" }));

    await waitFor(() => expect(mocks.invalidate).toHaveBeenCalledTimes(1));
    expect(mocks.invalidate).toHaveBeenCalledWith("home-1", 11, {
      expected_version: 1,
      reason: "Withdraw superseded evidence",
      acknowledge_historical_only: true,
      idempotency_key: "repair-proposal-invalidate:fixed-uuid",
      metadata: {
        source: "repair_proposal_invalidation_workspace",
        observed_client_stale_reasons: [
          "target_calendar_not_active",
          "source_schedule_version_changed",
        ],
      },
    });
    expect(
      await screen.findByText("The record is historical-only. No replacement schedule was created."),
    ).toBeInTheDocument();
  });

  it("keeps editors read-only", async () => {
    mocks.households.mockResolvedValueOnce([household("editor")]);
    renderPage();

    expect(await screen.findByText("Read-only role")).toBeInTheDocument();
    expect(
      screen.getByText(/Only a household owner can perform this permanent/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Invalidate proposal" }),
    ).not.toBeInTheDocument();
    expect(mocks.invalidate).not.toHaveBeenCalled();
  });

  it("shows append-only history without invoking other lifecycle mutations", async () => {
    renderPage();

    expect(
      await screen.findByText(createdEvent.reason),
    ).toBeInTheDocument();
    expect(screen.getByText("Version 0 → 1")).toBeInTheDocument();
    expect(mocks.invalidate).not.toHaveBeenCalled();
  });
});
