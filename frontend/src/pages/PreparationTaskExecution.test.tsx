import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PreparationTaskExecutionPage from "@/pages/PreparationTaskExecution";

const mocks = vi.hoisted(() => ({
  toast: vi.fn(),
  householdList: vi.fn(),
  householdGet: vi.fn(),
  schedules: vi.fn(),
  taskExecution: vi.fn(),
  eligibility: vi.fn(),
  startTask: vi.fn(),
  completeTask: vi.fn(),
  skipTask: vi.fn(),
  completeSchedule: vi.fn(),
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

vi.mock("@/lib/preparationOperationsApi", () => ({
  preparationOperationsApi: {
    schedules: mocks.schedules,
    taskExecution: mocks.taskExecution,
    startTask: mocks.startTask,
    completeTask: mocks.completeTask,
    skipTask: mocks.skipTask,
    complete: mocks.completeSchedule,
  },
}));

vi.mock("@/lib/preparationTaskExecutionEligibilityApi", () => ({
  preparationTaskExecutionEligibilityApi: {
    get: mocks.eligibility,
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

const scheduledTask = {
  task_id: "dinner.prep",
  start_minute: 10,
  finish_minute: 25,
  duration_minutes: 15,
  priority: 2,
  resource_demands: { person: 1 },
  dependencies: [] as string[],
  metadata: { recipe_id: "recipe-1" },
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
  schedule_request: null,
  schedule_request_hash: null,
  replay_status: "replayable" as const,
  schedule: {
    method: "deterministic_dependency_aware_resource_scheduler_v2",
    deterministic: true,
    horizon_minutes: 120,
    granularity_minutes: 5,
    scheduled: [scheduledTask],
    unscheduled: [],
    resource_utilization: { person: 0.125 },
    resource_peak_usage: { person: 1 },
    makespan_minutes: 25,
    diagnostics: {},
  },
  schedule_hash: "d".repeat(64),
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

const eligible = {
  schedule_id: 7,
  household_id: "home-1",
  schedule_version: 2,
  schedule_status: "approved",
  eligible: true,
  reason_code: "eligible" as const,
  task_event_count: 0,
  accepted_proposal_id: null,
  acceptance_id: null,
  replacement_schedule_id: null,
  replacement_schedule_status: null,
  replacement_schedule_version: null,
};

function overview(options: {
  roleState?: "planned" | "in_progress" | "completed" | "skipped";
  remaining?: number;
} = {}) {
  const state = options.roleState ?? "planned";
  const remaining = options.remaining
    ?? (state === "completed" || state === "skipped" ? 0 : 1);
  return {
    schedule,
    tasks: [
      {
        task: scheduledTask,
        state,
        latest_event_id: state === "planned" ? null : 1,
        started_actual_minute:
          state === "in_progress" || state === "completed" ? 10 : null,
        completed_actual_minute: state === "completed" ? 25 : null,
        skipped_actual_minute: state === "skipped" ? 10 : null,
        terminal_reason: state === "skipped" ? "Household skipped task" : null,
      },
    ],
    events: [],
    planned_count: state === "planned" ? 1 : 0,
    in_progress_count: state === "in_progress" ? 1 : 0,
    completed_count: state === "completed" ? 1 : 0,
    skipped_count: state === "skipped" ? 1 : 0,
    terminal_count: remaining === 0 ? 1 : 0,
    remaining_count: remaining,
  };
}

function renderPage(role: "owner" | "editor" | "viewer" = "editor") {
  mocks.householdGet.mockResolvedValue({
    household: { ...household, current_role: role },
    role,
    members: [],
    active_servings_multiplier: 1,
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
        <PreparationTaskExecutionPage />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.stubGlobal("crypto", { randomUUID: vi.fn(() => "fixed-uuid") });
  mocks.householdList.mockResolvedValue([household]);
  mocks.schedules.mockResolvedValue([schedule]);
  mocks.taskExecution.mockResolvedValue(overview());
  mocks.eligibility.mockResolvedValue(eligible);
  mocks.startTask.mockResolvedValue({
    schedule: { ...schedule, version: 3 },
    task: {
      ...overview({ roleState: "in_progress" }).tasks[0],
    },
    event: {
      id: 1,
      schedule_id: schedule.id,
      household_id: household.id,
      task_id: scheduledTask.task_id,
      event_type: "started",
      actor_user_id: "editor@example.test",
      from_state: "planned",
      to_state: "in_progress",
      planned_start_minute: 10,
      planned_finish_minute: 25,
      actual_minute: 10,
      deviation_minutes: 0,
      reason: null,
      notes: null,
      metadata: {},
      idempotency_key: "task-start-0001",
      request_fingerprint: "e".repeat(64),
      schedule_version_before: 2,
      schedule_version_after: 3,
      created_at: "2026-08-02T00:00:00Z",
    },
  });
  mocks.completeTask.mockResolvedValue({});
  mocks.skipTask.mockResolvedValue({});
  mocks.completeSchedule.mockResolvedValue({
    ...schedule,
    status: "completed",
    version: 3,
  });
});

describe("Preparation task execution workspace", () => {
  it("loads explicit state and authoritative eligibility without mutation", async () => {
    renderPage();

    expect(
      await screen.findByText("Preparation task execution"),
    ).toBeInTheDocument();
    expect(screen.getByText("Human-confirmed evidence only")).toBeInTheDocument();
    expect(screen.getByText("dinner.prep")).toBeInTheDocument();
    expect(screen.getByText(/Planned minute 10–25/)).toBeInTheDocument();
    expect(await screen.findByText("execution eligible")).toBeInTheDocument();
    expect(mocks.taskExecution).toHaveBeenCalledWith("home-1", 7);
    expect(mocks.eligibility).toHaveBeenCalledWith("home-1", 7);
    expect(mocks.startTask).not.toHaveBeenCalled();
    expect(mocks.completeTask).not.toHaveBeenCalled();
    expect(mocks.skipTask).not.toHaveBeenCalled();
    expect(mocks.completeSchedule).not.toHaveBeenCalled();
  });

  it("submits the exact optimistic schedule version and horizon minute", async () => {
    renderPage();
    await screen.findByText("execution eligible");

    fireEvent.click(screen.getByRole("button", { name: "Confirm start" }));

    await waitFor(() => expect(mocks.startTask).toHaveBeenCalledTimes(1));
    expect(mocks.startTask).toHaveBeenCalledWith(
      "home-1",
      7,
      "dinner.prep",
      expect.objectContaining({
        expected_schedule_version: 2,
        actual_minute: 10,
        reason: null,
        metadata: { source: "preparation_task_execution_ui" },
      }),
    );
  });

  it("requires a reason before a skipped task or timing deviation", async () => {
    renderPage();
    await screen.findByText("execution eligible");

    fireEvent.change(screen.getByLabelText("Actual horizon minute"), {
      target: { value: "15" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirm start" }));

    await waitFor(() =>
      expect(mocks.toast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Task execution event rejected",
          variant: "destructive",
        }),
      ),
    );
    expect(mocks.startTask).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Confirm skip" }));
    await waitFor(() => expect(mocks.skipTask).not.toHaveBeenCalled());
  });

  it("keeps task mutations read-only for viewers", async () => {
    renderPage("viewer");
    await screen.findByText("execution eligible");

    expect(screen.getByRole("button", { name: "Confirm start" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Confirm skip" })).toBeDisabled();
    expect(screen.getByLabelText("Actual horizon minute")).toBeDisabled();
  });

  it("blocks a source after accepted replacement and exposes exact identities", async () => {
    mocks.eligibility.mockResolvedValueOnce({
      ...eligible,
      eligible: false,
      reason_code: "source_schedule_has_accepted_replacement",
      accepted_proposal_id: 31,
      acceptance_id: 41,
      replacement_schedule_id: 17,
      replacement_schedule_status: "draft",
      replacement_schedule_version: 1,
    });
    renderPage();

    expect(
      await screen.findByText("Execution blocked by accepted replacement"),
    ).toBeInTheDocument();
    expect(screen.getByText(/repair proposal #31/)).toBeInTheDocument();
    expect(screen.getByText(/acceptance #41/)).toBeInTheDocument();
    expect(screen.getByText(/replacement schedule #17/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm start" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Confirm skip" })).toBeDisabled();
    expect(screen.getByLabelText("Actual horizon minute")).toBeDisabled();
    expect(mocks.startTask).not.toHaveBeenCalled();
  });

  it("enables schedule completion only when terminal and eligible", async () => {
    mocks.taskExecution.mockResolvedValueOnce(
      overview({ roleState: "completed", remaining: 0 }),
    );
    renderPage();

    const button = await screen.findByRole("button", {
      name: "Complete schedule",
    });
    await screen.findByText("execution eligible");
    expect(button).toBeEnabled();
    fireEvent.click(button);

    await waitFor(() => expect(mocks.completeSchedule).toHaveBeenCalledTimes(1));
    expect(mocks.completeSchedule).toHaveBeenCalledWith(
      "home-1",
      7,
      expect.objectContaining({
        expected_version: 2,
        reason: "Every deterministic task was explicitly completed or skipped",
        metadata: { source: "preparation_task_execution_ui" },
      }),
    );
  });
});
