import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PreparationOperationsCoveragePage from "@/pages/PreparationOperationsCoverage";

const mocks = vi.hoisted(() => ({
  householdList: vi.fn(),
  coverage: vi.fn(),
}));

vi.mock("@/components/AppLayout", () => ({
  default: ({ children }: { children: ReactNode }) => <main>{children}</main>,
}));

vi.mock("@/lib/platformApi", () => ({
  householdApi: {
    list: mocks.householdList,
  },
}));

vi.mock("@/lib/preparationOperationsApi", () => ({
  preparationOperationsApi: {
    coverage: mocks.coverage,
  },
}));

const households = [
  {
    id: "home-a",
    owner_user_id: "owner@example.test",
    name: "Home A",
    timezone: "UTC",
    version: 1,
    created_at: "2026-08-01T00:00:00Z",
    updated_at: "2026-08-01T00:00:00Z",
    current_role: "owner",
  },
  {
    id: "home-b",
    owner_user_id: "owner@example.test",
    name: "Home B",
    timezone: "UTC",
    version: 1,
    created_at: "2026-08-01T00:00:00Z",
    updated_at: "2026-08-01T00:00:00Z",
    current_role: "viewer",
  },
];

function coverage(householdId: string) {
  return {
    household_id: householdId,
    generated_at: "2026-08-02T00:00:00Z",
    calendar_total: 2,
    reviewed_calendar_total: 1,
    active_reviewed_calendar_count: 1,
    schedule_total: 4,
    schedule_status_counts: {
      draft: 1,
      approved: 1,
      invalidated: 1,
      completed: 0,
      cancelled: 1,
    },
    replay_status_counts: {
      replayable: 3,
      legacy_request_missing: 0,
      legacy_occurrence_set_missing: 1,
    },
    occurrence_document_count: 3,
    scheduler_request_count: 4,
    replayable_schedule_count: 3,
    replayable_draft_count: 1,
    source_plan_linked_count: 2,
    event_total: 9,
    occurrence_document_coverage: 0.75,
    scheduler_request_coverage: 1,
    replayable_schedule_coverage: 0.75,
    execution_scope_schedule_count: 2,
    execution_active_schedule_count: 1,
    execution_history_schedule_count: 1,
    execution_invalid_schedule_count: 1,
    deterministic_task_count: 4,
    task_state_counts: {
      planned: 1,
      in_progress: 1,
      completed: 1,
      skipped: 1,
    },
    terminal_task_count: 2,
    fully_terminal_schedule_count: 1,
    task_event_total: 5,
    nonzero_deviation_event_count: 2,
    skipped_task_event_count: 1,
    skip_reason_count: 1,
    task_event_schedule_coverage: 0.5,
    terminal_task_coverage: 0.5,
    latest_calendar_created_at: "2026-08-01T00:00:00Z",
    latest_schedule_created_at: "2026-08-01T00:00:00Z",
    latest_task_event_at: "2026-08-02T00:30:00Z",
    warnings: [
      "One or more legacy schedules lack complete replay provenance",
      "One or more schedules are not linked to a source plan version",
      "One or more execution schedules or task histories are structurally invalid",
    ],
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
        <PreparationOperationsCoveragePage />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  mocks.householdList.mockResolvedValue(households);
  mocks.coverage.mockImplementation(async (householdId: string) =>
    coverage(householdId),
  );
});

describe("Preparation provenance coverage dashboard", () => {
  it("shows separate provenance and execution denominators", async () => {
    renderPage();

    expect(
      await screen.findByText("Preparation provenance coverage"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Coverage is not correctness, observation, or safety"),
    ).toBeInTheDocument();
    expect(screen.getByText("Coverage gaps detected")).toBeInTheDocument();
    expect(screen.getByText("Calendars")).toBeInTheDocument();
    expect(screen.getByText("Schedules")).toBeInTheDocument();
    expect(screen.getByText("Replayable drafts")).toBeInTheDocument();
    expect(screen.getByText("Schedule events")).toBeInTheDocument();
    expect(
      screen.getByRole("progressbar", { name: "Occurrence documents" }),
    ).toHaveAttribute("aria-valuenow", "75");
    expect(
      screen.getByRole("progressbar", {
        name: "Deterministic scheduler requests",
      }),
    ).toHaveAttribute("aria-valuenow", "100");
    expect(screen.getByText(/2 of 4 schedules link/)).toBeInTheDocument();
    expect(screen.getByText("Missing occurrence document: 1")).toBeInTheDocument();

    expect(screen.getByText("Task execution evidence")).toBeInTheDocument();
    expect(screen.getByText("Execution scope")).toBeInTheDocument();
    expect(screen.getByText("Deterministic tasks")).toBeInTheDocument();
    expect(screen.getByText("Task events")).toBeInTheDocument();
    expect(screen.getByText("Skipped tasks")).toBeInTheDocument();
    expect(
      screen.getByRole("progressbar", {
        name: "Execution-scope schedules with task events",
      }),
    ).toHaveAttribute("aria-valuenow", "50");
    expect(
      screen.getByRole("progressbar", {
        name: "Deterministic tasks explicitly terminal",
      }),
    ).toHaveAttribute("aria-valuenow", "50");
    expect(screen.getByText("Structurally invalid schedules or histories: 1")).toBeInTheDocument();
    expect(screen.getByText("planned: 1")).toBeInTheDocument();
    expect(screen.getByText("in progress: 1")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open task execution" })).toHaveAttribute(
      "href",
      "/preparation/operations/execution",
    );
    expect(mocks.coverage).toHaveBeenCalledWith("home-a");
  });

  it("reloads coverage when the household changes", async () => {
    renderPage();
    await screen.findByText("Preparation provenance coverage");

    fireEvent.change(screen.getByLabelText("Household"), {
      target: { value: "home-b" },
    });

    await waitFor(() => expect(mocks.coverage).toHaveBeenCalledWith("home-b"));
  });

  it("surfaces transport failures without inventing metrics", async () => {
    mocks.coverage.mockRejectedValueOnce(new Error("Coverage service unavailable"));
    renderPage();

    expect(await screen.findByText("Coverage unavailable")).toBeInTheDocument();
    expect(screen.getByText("Coverage service unavailable")).toBeInTheDocument();
    expect(screen.queryByText("Provenance completeness")).not.toBeInTheDocument();
    expect(screen.queryByText("Task execution evidence")).not.toBeInTheDocument();
  });
});
