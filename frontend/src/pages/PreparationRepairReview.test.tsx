import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PreparationRepairReviewPage from "@/pages/PreparationRepairReview";

const mocks = vi.hoisted(() => ({
  householdList: vi.fn(),
  schedules: vi.fn(),
  repair: vi.fn(),
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
    schedules: mocks.schedules,
  },
}));

vi.mock("@/lib/preparationRepairApi", () => ({
  preparationRepairApi: {
    repair: mocks.repair,
  },
}));

const household = {
  id: "home-1",
  owner_user_id: "owner@example.test",
  name: "Home One",
  timezone: "UTC",
  version: 1,
  created_at: "2026-08-02T00:00:00Z",
  updated_at: "2026-08-02T00:00:00Z",
  current_role: "editor" as const,
};

const previousRequest = {
  horizon_minutes: 120,
  granularity_minutes: 5,
  resources: [
    {
      resource_id: "person",
      capacity: 2,
      availability_windows: [{ start_minute: 0, end_minute: 120 }],
      label: "Available cooks",
    },
  ],
  tasks: [
    {
      task_id: "task.a",
      duration_minutes: 10,
      earliest_start_minute: 0,
      latest_finish_minute: 60,
      priority: 1,
      resource_demands: { person: 1 },
      dependencies: [] as string[],
      metadata: {},
    },
    {
      task_id: "task.b",
      duration_minutes: 10,
      earliest_start_minute: 0,
      latest_finish_minute: 60,
      priority: 1,
      resource_demands: { person: 1 },
      dependencies: [] as string[],
      metadata: {},
    },
  ],
};

const previousResponse = {
  method: "deterministic_dependency_aware_resource_scheduler_v2",
  deterministic: true,
  horizon_minutes: 120,
  granularity_minutes: 5,
  scheduled: [
    {
      task_id: "task.a",
      start_minute: 0,
      finish_minute: 10,
      duration_minutes: 10,
      priority: 1,
      resource_demands: { person: 1 },
      dependencies: [] as string[],
      metadata: {},
    },
    {
      task_id: "task.b",
      start_minute: 0,
      finish_minute: 10,
      duration_minutes: 10,
      priority: 1,
      resource_demands: { person: 1 },
      dependencies: [] as string[],
      metadata: {},
    },
  ],
  unscheduled: [],
  resource_utilization: { person: 1 / 12 },
  resource_peak_usage: { person: 2 },
  makespan_minutes: 10,
  diagnostics: {},
};

const schedule = {
  id: 7,
  household_id: household.id,
  calendar_version_id: 3,
  calendar_content_hash: "b".repeat(64),
  source_plan_id: 42,
  source_plan_version: 2,
  occurrence_set_version: "occurrences-v1",
  occurrence_set_hash: "c".repeat(64),
  occurrence_set: null,
  profile_versions: {},
  schedule_request: previousRequest,
  schedule_request_hash: "d".repeat(64),
  replay_status: "replayable" as const,
  schedule: previousResponse,
  schedule_hash: "e".repeat(64),
  status: "approved" as const,
  version: 2,
  notes: null,
  created_by_user_id: "editor@example.test",
  approved_by_user_id: "owner@example.test",
  approved_at: "2026-08-02T00:00:00Z",
  invalidated_at: null,
  invalidation_reason: null,
  created_at: "2026-08-02T00:00:00Z",
  updated_at: "2026-08-02T00:00:00Z",
};

const repairResult = {
  response: {
    ...previousResponse,
    scheduled: [
      previousResponse.scheduled[0],
      {
        ...previousResponse.scheduled[1],
        start_minute: 10,
        finish_minute: 20,
      },
    ],
    resource_peak_usage: { person: 1 },
    makespan_minutes: 20,
  },
  complete: true,
  immutable_task_ids: ["task.a"],
  preserved_task_ids: ["task.a"],
  moved_tasks: [
    {
      task_id: "task.b",
      previous_start_minute: 0,
      repaired_start_minute: 10,
      displacement_minutes: 10,
    },
  ],
  added_task_ids: [],
  removed_task_ids: [],
  unscheduled_task_ids: [],
  objective: {
    unscheduled_task_count: 0,
    changed_task_count: 1,
    total_displacement_minutes: 10,
    makespan_minutes: 20,
    weighted_value: 10120,
  },
  diagnostics: {
    strategy: "greedy_min_change" as const,
    deterministic: true,
    explored_states: 0,
    pruned_states: 0,
    candidate_placements_considered: 4,
    preserved_attempt_count: 2,
    exact_search_truncated: false,
    tie_break_rule: "stable task ID and start minute",
    limitations: ["Greedy repair is not represented as globally optimal."],
  },
  warnings: ["Human review and explicit acceptance are required."],
  previous_schedule_hash: "f".repeat(64),
  revised_request_hash: "1".repeat(64),
  repaired_response_hash: "2".repeat(64),
  requires_human_acceptance: true as const,
  accepted: false as const,
  persistence_performed: false as const,
};

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
        <PreparationRepairReviewPage />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  mocks.householdList.mockResolvedValue([household]);
  mocks.schedules.mockResolvedValue([schedule]);
  mocks.repair.mockResolvedValue(repairResult);
});

describe("Advisory preparation repair review", () => {
  it("loads a replayable source without accepting or persisting anything", async () => {
    renderPage();

    expect(
      await screen.findByRole("heading", { name: "Advisory schedule repair" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Human review boundary")).toBeInTheDocument();
    const revisedRequest = await screen.findByLabelText(
      "Strict revised request JSON",
    );
    expect(revisedRequest).toHaveValue(JSON.stringify(previousRequest, null, 2));
    expect(mocks.schedules).toHaveBeenCalledWith("home-1", [
      "draft",
      "approved",
    ]);
    expect(mocks.repair).not.toHaveBeenCalled();
    expect(screen.queryByText("Complete advisory candidate")).not.toBeInTheDocument();
  });

  it("submits exact previous evidence, revised problem, strategy, and immutable tasks", async () => {
    renderPage();
    await screen.findByLabelText("Strict revised request JSON");

    fireEvent.click(screen.getByRole("checkbox", { name: /task\.a/i }));
    fireEvent.click(
      screen.getByRole("button", { name: "Compute advisory repair" }),
    );

    await waitFor(() => expect(mocks.repair).toHaveBeenCalledTimes(1));
    expect(mocks.repair).toHaveBeenCalledWith({
      previous_request: previousRequest,
      previous_response: previousResponse,
      revised_request: previousRequest,
      immutable_task_ids: ["task.a"],
      strategy: "greedy_min_change",
      allow_partial: false,
    });
  });

  it("renders an accessible change ledger and explicit advisory flags", async () => {
    renderPage();
    await screen.findByLabelText("Strict revised request JSON");
    fireEvent.click(
      screen.getByRole("button", { name: "Compute advisory repair" }),
    );

    expect(
      await screen.findByText("Complete advisory candidate"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Human acceptance required: true\./),
    ).toBeInTheDocument();
    expect(screen.getByText(/Accepted: false\./)).toBeInTheDocument();
    expect(screen.getByText(/Persistence performed: false\./)).toBeInTheDocument();
    expect(
      screen.getByRole("table", {
        name: "Previous and repaired preparation task placements",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("rowheader", { name: /task\.a/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("rowheader", { name: /task\.b/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("+10 min")).toBeInTheDocument();
  });

  it("keeps export disabled until the user reviews changes and the boundary", async () => {
    renderPage();
    await screen.findByLabelText("Strict revised request JSON");
    fireEvent.click(
      screen.getByRole("button", { name: "Compute advisory repair" }),
    );

    const exportButton = await screen.findByRole("button", {
      name: "Export reviewed candidate JSON",
    });
    expect(exportButton).toBeDisabled();

    fireEvent.click(
      screen.getByRole("checkbox", {
        name: /reviewed every moved, added, removed, and unresolved task/i,
      }),
    );
    expect(exportButton).toBeDisabled();

    fireEvent.click(
      screen.getByRole("checkbox", {
        name: /remains unaccepted, unpersisted, unapproved, and unexecuted/i,
      }),
    );
    expect(exportButton).toBeEnabled();
  });

  it("does not offer completed schedules as repairable inputs", async () => {
    mocks.schedules.mockResolvedValueOnce([
      { ...schedule, id: 8, status: "completed" as const },
    ]);
    renderPage();

    expect(
      await screen.findByText("No repairable schedule"),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("Strict revised request JSON")).not.toBeInTheDocument();
    expect(mocks.repair).not.toHaveBeenCalled();
  });
});
