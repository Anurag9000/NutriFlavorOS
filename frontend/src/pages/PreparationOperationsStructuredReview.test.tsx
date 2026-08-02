import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PREPARATION_OPERATIONS_HANDOFF_KEY } from "@/lib/preparationOperationsHandoff";
import PreparationOperationsPage from "@/pages/PreparationOperations";

const mocks = vi.hoisted(() => ({
  toast: vi.fn(),
  householdList: vi.fn(),
  householdGet: vi.fn(),
  schedules: vi.fn(),
  calendar: vi.fn(),
  events: vi.fn(),
  createSchedule: vi.fn(),
  approve: vi.fn(),
  cancel: vi.fn(),
  invalidate: vi.fn(),
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
    calendar: mocks.calendar,
    events: mocks.events,
    createSchedule: mocks.createSchedule,
    approve: mocks.approve,
    cancel: mocks.cancel,
    invalidate: mocks.invalidate,
  },
}));

const household = {
  id: "structured-home",
  owner_user_id: "owner@example.test",
  name: "Structured home",
  timezone: "UTC",
  version: 1,
  created_at: "2026-08-02T00:00:00Z",
  updated_at: "2026-08-02T00:00:00Z",
  current_role: "owner" as const,
};

const calendar = {
  id: 7,
  household_id: household.id,
  calendar_version: "calendar-v1",
  horizon_minutes: 240,
  timezone: "UTC",
  evidence_status: "reviewed" as const,
  reviewed_at: "2026-08-02T00:00:00Z",
  reviewed_by: "Household reviewer",
  notes: null,
  content_hash: "a".repeat(64),
  supersedes_calendar_id: null,
  active: true,
  created_by_user_id: "owner@example.test",
  created_at: "2026-08-02T00:00:00Z",
  updated_at: "2026-08-02T00:00:00Z",
  resources: [
    {
      id: 1,
      calendar_version_id: 7,
      resource_id: "person",
      label: "Available cook",
      capacity: 1,
      resource_kind: "person",
      availability_windows: [{ start_minute: 0, end_minute: 240 }],
      metadata: {},
    },
  ],
};

const task = {
  task_id: "day-1.dinner:prep",
  duration_minutes: 15,
  earliest_start_minute: 0,
  latest_finish_minute: 180,
  priority: 3,
  resource_demands: { person: 1 },
  dependencies: [] as string[],
  metadata: {
    occurrence_id: "day-1.dinner",
    recipe_id: "recipe-1",
    profile_id: 3,
    profile_version: "v1",
    profile_content_hash: "b".repeat(64),
    servings: 2,
    duration_min_minutes: 10,
    duration_max_minutes: 15,
  },
};

function handoff(options: { extraProfile?: boolean; unscheduled?: boolean } = {}) {
  return {
    document_version: "preparation-operations-handoff-v2",
    household_id: household.id,
    created_at: new Date().toISOString(),
    occurrence_set_hash_preview: "c".repeat(64),
    bundle: {
      calendar_version_id: calendar.id,
      source_plan_id: 42,
      source_plan_version: 2,
      occurrence_set: {
        document_version: "preparation-occurrence-set-v1",
        household_id: household.id,
        occurrence_set_version: "plan-42-v2-occurrences-v1",
        duration_policy: "conservative_max",
        occurrences: [
          {
            occurrence_id: "day-1.dinner",
            recipe_id: "recipe-1",
            required_finish_minute: 180,
            servings: 2,
            priority: 3,
          },
        ],
      },
      profile_versions: {
        "recipe-1": `profile:3/version:v1/sha256:${"b".repeat(64)}`,
        ...(options.extraProfile
          ? { "recipe-extra": `profile:4/version:v1/sha256:${"d".repeat(64)}` }
          : {}),
      },
      schedule_request: {
        horizon_minutes: 240,
        granularity_minutes: 5,
        resources: [
          {
            resource_id: "person",
            capacity: 1,
            availability_windows: [{ start_minute: 0, end_minute: 240 }],
            label: "Available cook",
          },
        ],
        tasks: [task],
      },
      schedule_response: {
        method: "deterministic_dependency_aware_resource_scheduler_v2",
        deterministic: true,
        horizon_minutes: 240,
        granularity_minutes: 5,
        scheduled: options.unscheduled
          ? []
          : [
              {
                task_id: task.task_id,
                start_minute: 0,
                finish_minute: 15,
                duration_minutes: 15,
                priority: 3,
                resource_demands: { person: 1 },
                dependencies: [],
                metadata: task.metadata,
              },
            ],
        unscheduled: options.unscheduled
          ? [
              {
                task_id: task.task_id,
                reason_code: "missing_resource",
                message: "Required resource is unavailable",
                missing_resources: ["person"],
                blocked_by: [],
                capacity_violations: {},
                metadata: {},
              },
            ]
          : [],
        resource_utilization: { person: 0.0625 },
        resource_peak_usage: { person: 1 },
        makespan_minutes: options.unscheduled ? 0 : 15,
        diagnostics: {},
      },
      notes: "Approved-plan structured review fixture",
    },
  };
}

function persistedDraft() {
  const value = handoff().bundle;
  return {
    id: 19,
    household_id: household.id,
    calendar_version_id: calendar.id,
    calendar_content_hash: calendar.content_hash,
    source_plan_id: 42,
    source_plan_version: 2,
    occurrence_set_version: value.occurrence_set.occurrence_set_version,
    occurrence_set_hash: "c".repeat(64),
    occurrence_set: value.occurrence_set,
    profile_versions: value.profile_versions,
    schedule_request: value.schedule_request,
    schedule_request_hash: "e".repeat(64),
    replay_status: "replayable" as const,
    schedule: value.schedule_response,
    schedule_hash: "f".repeat(64),
    status: "draft" as const,
    version: 1,
    notes: value.notes,
    created_by_user_id: "owner@example.test",
    approved_by_user_id: null,
    approved_at: null,
    invalidated_at: null,
    invalidation_reason: null,
    created_at: "2026-08-02T00:00:00Z",
    updated_at: "2026-08-02T00:00:00Z",
  };
}

function storeHandoff(value = handoff()) {
  sessionStorage.setItem(PREPARATION_OPERATIONS_HANDOFF_KEY, JSON.stringify(value));
}

function renderPage(role: "owner" | "viewer" = "owner") {
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
        <PreparationOperationsPage />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  sessionStorage.clear();
  storeHandoff();
  mocks.householdList.mockResolvedValue([household]);
  mocks.schedules.mockResolvedValue([]);
  mocks.calendar.mockResolvedValue(calendar);
  mocks.events.mockResolvedValue([]);
  mocks.createSchedule.mockResolvedValue(persistedDraft());
  mocks.approve.mockResolvedValue({ ...persistedDraft(), status: "approved", version: 2 });
  mocks.cancel.mockResolvedValue({ ...persistedDraft(), status: "cancelled", version: 2 });
  mocks.invalidate.mockResolvedValue({ ...persistedDraft(), status: "invalidated", version: 2 });
});

describe("Structured preparation operations review", () => {
  it("consumes the handoff without automatically persisting or approving", async () => {
    renderPage();

    expect(await screen.findByText("Structured persistence review")).toBeInTheDocument();
    expect(screen.getByText("Occurrences and reviewed profiles")).toBeInTheDocument();
    expect(screen.getByText("Deterministic task DAG")).toBeInTheDocument();
    expect(screen.getByText(/Source plan/)).toBeInTheDocument();
    expect(screen.getByText(/minute 0–15/)).toBeInTheDocument();
    expect(screen.getByLabelText("Schedule bundle JSON")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Persist reviewed schedule draft" }),
    ).toBeDisabled();
    expect(mocks.createSchedule).not.toHaveBeenCalled();
    expect(mocks.approve).not.toHaveBeenCalled();
    expect(
      sessionStorage.getItem(PREPARATION_OPERATIONS_HANDOFF_KEY),
    ).toBeNull();
  });

  it("requires all confirmations and persists the exact structured bundle", async () => {
    renderPage();
    await screen.findByText("Structured persistence review");

    const confirmations = screen.getAllByRole("checkbox");
    expect(confirmations).toHaveLength(4);
    confirmations.forEach((value) => fireEvent.click(value));
    const persist = screen.getByRole("button", {
      name: "Persist reviewed schedule draft",
    });
    expect(persist).toBeEnabled();
    fireEvent.click(persist);

    await waitFor(() => expect(mocks.createSchedule).toHaveBeenCalledTimes(1));
    const [householdId, payload] = mocks.createSchedule.mock.calls[0];
    expect(householdId).toBe(household.id);
    expect(payload.calendar_version_id).toBe(calendar.id);
    expect(payload.source_plan_id).toBe(42);
    expect(payload.source_plan_version).toBe(2);
    expect(payload.occurrence_set.occurrences).toHaveLength(1);
    expect(payload.schedule_request.tasks).toEqual([task]);
    expect(payload.schedule_response.unscheduled).toEqual([]);
    expect(payload.notes).toBe("Approved-plan structured review fixture");
    expect(payload.idempotency_key).toMatch(/^persist-preparation-schedule-/);
    expect(await screen.findByText("Schedule #19")).toBeInTheDocument();
    expect(mocks.approve).not.toHaveBeenCalled();
  });

  it("blocks profile drift and unresolved deterministic work", async () => {
    sessionStorage.clear();
    storeHandoff(handoff({ extraProfile: true, unscheduled: true }));
    renderPage();

    expect(await screen.findByText("Structured review blocked")).toBeInTheDocument();
    expect(
      screen.getByText(/Preparation-profile recipes do not exactly match/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Deterministic response still contains unscheduled tasks/),
    ).toBeInTheDocument();
    screen.getAllByRole("checkbox").forEach((value) => fireEvent.click(value));
    expect(
      screen.getByRole("button", { name: "Persist reviewed schedule draft" }),
    ).toBeDisabled();
    expect(mocks.createSchedule).not.toHaveBeenCalled();
  });

  it("keeps persistence read-only for viewers", async () => {
    renderPage("viewer");
    await screen.findByText("Structured persistence review");
    screen.getAllByRole("checkbox").forEach((value) => fireEvent.click(value));

    expect(
      screen.getByRole("button", { name: "Persist reviewed schedule draft" }),
    ).toBeDisabled();
    expect(screen.getByText(/Editor or owner access is required/)).toBeInTheDocument();
  });
});
