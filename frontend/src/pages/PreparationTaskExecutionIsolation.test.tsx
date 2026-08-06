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
  id: "isolation-home",
  owner_user_id: "owner@example.test",
  name: "Isolation home",
  timezone: "UTC",
  version: 1,
  created_at: "2026-08-02T00:00:00Z",
  updated_at: "2026-08-02T00:00:00Z",
  current_role: "editor" as const,
};

function scheduledTask(start: number, finish: number) {
  return {
    task_id: "shared.task",
    start_minute: start,
    finish_minute: finish,
    duration_minutes: finish - start,
    priority: 1,
    resource_demands: { person: 1 },
    dependencies: [] as string[],
    metadata: {},
  };
}

function schedule(id: number, start: number, finish: number) {
  return {
    id,
    household_id: household.id,
    calendar_version_id: id,
    calendar_content_hash: "a".repeat(64),
    source_plan_id: null,
    source_plan_version: null,
    occurrence_set_version: `occurrence-${id}`,
    occurrence_set_hash: "b".repeat(64),
    occurrence_set: null,
    profile_versions: {},
    schedule_request: null,
    schedule_request_hash: null,
    replay_status: "replayable" as const,
    schedule: {
      method: "deterministic_dependency_aware_resource_scheduler_v2",
      deterministic: true,
      horizon_minutes: 240,
      granularity_minutes: 5,
      scheduled: [scheduledTask(start, finish)],
      unscheduled: [],
      resource_utilization: { person: 0.1 },
      resource_peak_usage: { person: 1 },
      makespan_minutes: finish,
      diagnostics: {},
    },
    schedule_hash: "c".repeat(64),
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
}

const firstSchedule = schedule(11, 10, 25);
const secondSchedule = schedule(12, 80, 100);

function overview(value: ReturnType<typeof schedule>) {
  return {
    schedule: value,
    tasks: [
      {
        task: value.schedule.scheduled[0],
        state: "planned" as const,
        latest_event_id: null,
        started_actual_minute: null,
        completed_actual_minute: null,
        skipped_actual_minute: null,
        terminal_reason: null,
      },
    ],
    events: [],
    planned_count: 1,
    in_progress_count: 0,
    completed_count: 0,
    skipped_count: 0,
    terminal_count: 0,
    remaining_count: 1,
  };
}

function eligibleSchedule(id: number) {
  return {
    schedule_id: id,
    household_id: household.id,
    schedule_version: 2,
    schedule_status: "approved" as const,
    eligible: true,
    reason_code: "eligible" as const,
    task_event_count: 0,
    accepted_proposal_id: null,
    acceptance_id: null,
    replacement_schedule_id: null,
    replacement_schedule_status: null,
    replacement_schedule_version: null,
  };
}

function renderPage({ retry = false }: { retry?: boolean } = {}) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: retry ? 1 : false },
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
  mocks.householdGet.mockResolvedValue({
    household,
    role: "editor",
    members: [],
    active_servings_multiplier: 1,
    planning_status: "ready",
  });
  mocks.schedules.mockResolvedValue([firstSchedule, secondSchedule]);
  mocks.taskExecution.mockImplementation(async (_householdId: string, id: number) =>
    overview(id === secondSchedule.id ? secondSchedule : firstSchedule),
  );
  mocks.eligibility.mockImplementation(async (_householdId: string, id: number) =>
    eligibleSchedule(id),
  );
  mocks.completeTask.mockResolvedValue({});
  mocks.skipTask.mockResolvedValue({});
  mocks.completeSchedule.mockResolvedValue({});
});

describe("Preparation task execution isolation", () => {
  it("clears actual minute, reason, and notes when schedules share a task ID", async () => {
    renderPage();
    expect(await screen.findByText(/Planned minute 10–25/)).toBeInTheDocument();
    await screen.findByText("execution eligible");

    fireEvent.change(screen.getByLabelText("Actual horizon minute"), {
      target: { value: "17" },
    });
    fireEvent.change(screen.getByLabelText("Skip or deviation reason"), {
      target: { value: "First schedule delay" },
    });
    fireEvent.change(screen.getByLabelText("Notes"), {
      target: { value: "First schedule note" },
    });

    fireEvent.change(screen.getByLabelText("Schedule"), {
      target: { value: String(secondSchedule.id) },
    });

    expect(await screen.findByText(/Planned minute 80–100/)).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByLabelText("Actual horizon minute")).toHaveValue(80),
    );
    expect(screen.getByLabelText("Skip or deviation reason")).toHaveValue("");
    expect(screen.getByLabelText("Notes")).toHaveValue("");
  });

  it("reuses one idempotency key across an automatic mutation retry", async () => {
    const success = {
      schedule: { ...firstSchedule, version: 3 },
      task: {
        ...overview(firstSchedule).tasks[0],
        state: "in_progress" as const,
        latest_event_id: 1,
        started_actual_minute: 10,
      },
      event: {
        id: 1,
        schedule_id: firstSchedule.id,
        household_id: household.id,
        task_id: "shared.task",
        event_type: "started" as const,
        actor_user_id: "editor@example.test",
        from_state: "planned" as const,
        to_state: "in_progress" as const,
        planned_start_minute: 10,
        planned_finish_minute: 25,
        actual_minute: 10,
        deviation_minutes: 0,
        reason: null,
        notes: null,
        metadata: {},
        idempotency_key: "server-returned-key",
        request_fingerprint: "d".repeat(64),
        schedule_version_before: 2,
        schedule_version_after: 3,
        created_at: "2026-08-02T00:00:00Z",
      },
    };
    mocks.startTask
      .mockRejectedValueOnce(new Error("Ambiguous transport failure"))
      .mockResolvedValueOnce(success);
    renderPage({ retry: true });
    await screen.findByText(/Planned minute 10–25/);
    await screen.findByText("execution eligible");
    const startButton = screen.getByRole("button", { name: "Confirm start" });
    await waitFor(() => expect(startButton).toBeEnabled());

    fireEvent.click(startButton);

    await waitFor(() => expect(mocks.startTask).toHaveBeenCalledTimes(2));
    const firstPayload = mocks.startTask.mock.calls[0][3];
    const secondPayload = mocks.startTask.mock.calls[1][3];
    expect(firstPayload.idempotency_key).toMatch(/^task-started-/);
    expect(secondPayload.idempotency_key).toBe(firstPayload.idempotency_key);
    expect(firstPayload.expected_schedule_version).toBe(2);
    expect(secondPayload.expected_schedule_version).toBe(2);
  });
});