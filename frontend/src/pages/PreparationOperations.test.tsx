import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PREPARATION_OPERATIONS_HANDOFF_KEY } from "@/lib/preparationOperationsHandoff";
import PreparationOperationsPage from "@/pages/PreparationOperations";

const mocks = vi.hoisted(() => ({
  toast: vi.fn(),
  householdList: vi.fn(),
  householdGet: vi.fn(),
  calendars: vi.fn(),
  schedules: vi.fn(),
  events: vi.fn(),
  createCalendar: vi.fn(),
  createSchedule: vi.fn(),
  approve: vi.fn(),
  complete: vi.fn(),
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
    calendars: mocks.calendars,
    schedules: mocks.schedules,
    events: mocks.events,
    createCalendar: mocks.createCalendar,
    createSchedule: mocks.createSchedule,
    approve: mocks.approve,
    complete: mocks.complete,
    cancel: mocks.cancel,
    invalidate: mocks.invalidate,
  },
}));

const household = {
  id: "household-1",
  owner_user_id: "owner@example.test",
  name: "Home",
  timezone: "UTC",
  version: 1,
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:00Z",
  current_role: "owner",
};

const calendar = {
  id: 7,
  household_id: household.id,
  calendar_version: "calendar-v1",
  horizon_minutes: 240,
  timezone: "UTC",
  evidence_status: "reviewed",
  reviewed_at: "2026-08-01T00:00:00Z",
  reviewed_by: "Owner reviewer",
  notes: "Reviewed fixture",
  content_hash: "a".repeat(64),
  supersedes_calendar_id: null,
  active: true,
  created_by_user_id: "owner@example.test",
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:00Z",
  resources: [
    {
      id: 11,
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

function schedule(replayStatus: "replayable" | "legacy_request_missing") {
  return {
    id: replayStatus === "replayable" ? 21 : 22,
    household_id: household.id,
    calendar_version_id: calendar.id,
    calendar_content_hash: calendar.content_hash,
    source_plan_id: null,
    source_plan_version: null,
    occurrence_set_version: "occurrences-v1",
    occurrence_set_hash: "b".repeat(64),
    profile_versions: {},
    schedule_request: replayStatus === "replayable" ? {
      horizon_minutes: 240,
      granularity_minutes: 5,
      resources: [],
      tasks: [],
    } : null,
    schedule_request_hash: replayStatus === "replayable" ? "c".repeat(64) : null,
    replay_status: replayStatus,
    schedule: {
      method: "deterministic_dependency_aware_resource_scheduler_v3_multi_window",
      deterministic: true,
      horizon_minutes: 240,
      granularity_minutes: 5,
      scheduled: [
        {
          task_id: "prep",
          start_minute: 0,
          finish_minute: 20,
          duration_minutes: 20,
          priority: 1,
          resource_demands: { person: 1 },
          dependencies: [],
          metadata: {},
        },
      ],
      unscheduled: [],
      resource_utilization: { person: 0.1 },
      resource_peak_usage: { person: 1 },
      makespan_minutes: 20,
      diagnostics: {},
    },
    schedule_hash: "d".repeat(64),
    status: "draft",
    version: 1,
    notes: null,
    created_by_user_id: "owner@example.test",
    approved_by_user_id: null,
    approved_at: null,
    invalidated_at: null,
    invalidation_reason: null,
    created_at: "2026-08-01T00:00:00Z",
    updated_at: "2026-08-01T00:00:00Z",
  };
}

function handoffBundle() {
  return {
    document_version: "preparation-operations-handoff-v1",
    household_id: household.id,
    created_at: "2026-08-01T00:00:00Z",
    bundle: {
      calendar_version_id: calendar.id,
      source_plan_id: null,
      source_plan_version: null,
      occurrence_set_version: "occurrences-v1",
      occurrence_set_hash: "f".repeat(64),
      profile_versions: {
        recipe: `profile:1/version:1/sha256:${"e".repeat(64)}`,
      },
      schedule_request: {
        horizon_minutes: 240,
        granularity_minutes: 5,
        resources: [
          {
            resource_id: "person",
            label: "Available cook",
            capacity: 1,
            availability_windows: [{ start_minute: 0, end_minute: 240 }],
          },
        ],
        tasks: [
          {
            task_id: "prep",
            duration_minutes: 20,
            earliest_start_minute: 0,
            latest_finish_minute: 60,
            priority: 1,
            resource_demands: { person: 1 },
            dependencies: [],
            metadata: { profile_content_hash: "e".repeat(64) },
          },
        ],
      },
      schedule_response: schedule("replayable").schedule,
      notes: "Pipeline handoff",
    },
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
    <QueryClientProvider client={client}>
      <PreparationOperationsPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  sessionStorage.clear();
  mocks.householdList.mockResolvedValue([household]);
  mocks.householdGet.mockResolvedValue({
    household,
    role: "owner",
    members: [],
    active_servings_multiplier: 0,
    planning_status: "ready",
  });
  mocks.calendars.mockResolvedValue([calendar]);
  mocks.schedules.mockResolvedValue([
    schedule("replayable"),
    schedule("legacy_request_missing"),
  ]);
  mocks.events.mockResolvedValue([
    {
      id: 1,
      schedule_id: 21,
      household_id: household.id,
      event_type: "created",
      actor_user_id: "owner@example.test",
      from_status: null,
      to_status: "draft",
      reason: "Persisted deterministic preparation schedule created",
      metadata: {},
      idempotency_key: "created-21",
      request_fingerprint: "e".repeat(64),
      created_at: "2026-08-01T00:00:00Z",
    },
  ]);
  mocks.createCalendar.mockResolvedValue(calendar);
  mocks.createSchedule.mockResolvedValue(schedule("replayable"));
});

describe("Preparation operations workspace", () => {
  it("shows replay provenance and blocks approval for legacy schedules", async () => {
    renderPage();
    expect(await screen.findByText("Schedule #21")).toBeInTheDocument();
    expect(screen.getByText("Schedule #22")).toBeInTheDocument();
    expect(screen.getByText("Approval blocked")).toBeInTheDocument();
    expect(screen.getAllByText("replayable").length).toBeGreaterThan(0);
    expect(screen.getByTitle("c".repeat(64))).toBeInTheDocument();

    const approveButtons = screen.getAllByRole("button", { name: "Approve" });
    expect(approveButtons).toHaveLength(2);
    expect(approveButtons[0]).toBeEnabled();
    expect(approveButtons[1]).toBeDisabled();
  });

  it("forms an active reviewed calendar with explicit windows", async () => {
    renderPage();
    await screen.findByText("Schedule #21");
    fireEvent.click(screen.getByRole("tab", { name: "Resource calendars" }));
    expect(await screen.findByText("Register and activate a reviewed calendar")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Reviewed by"), {
      target: { value: "Household owner" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Register active reviewed calendar" }));

    await waitFor(() => expect(mocks.createCalendar).toHaveBeenCalledTimes(1));
    const [householdId, payload] = mocks.createCalendar.mock.calls[0];
    expect(householdId).toBe(household.id);
    expect(payload.evidence_status).toBe("reviewed");
    expect(payload.activate).toBe(true);
    expect(payload.resources[0].availability_windows).toEqual([
      { start_minute: 0, end_minute: 60 },
      { start_minute: 90, end_minute: 240 },
    ]);
    expect(payload.reviewed_at).toMatch(/Z$/);
  });

  it("loads append-only event history for one schedule", async () => {
    renderPage();
    await screen.findByText("Schedule #21");
    fireEvent.click(screen.getAllByRole("button", { name: "Load event history" })[0]);
    expect(await screen.findByText(/Persisted deterministic preparation schedule created/)).toBeInTheDocument();
    expect(mocks.events).toHaveBeenCalledWith(household.id, 21);
  });

  it("loads a one-time pipeline handoff without auto-persisting", async () => {
    sessionStorage.setItem(
      PREPARATION_OPERATIONS_HANDOFF_KEY,
      JSON.stringify(handoffBundle()),
    );
    renderPage();

    expect(await screen.findByText("Reviewed pipeline handoff loaded")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Persist reviewed output" })).toHaveAttribute("data-state", "active");
    expect(screen.getByLabelText("Schedule creation bundle JSON")).toHaveValue(
      JSON.stringify(handoffBundle().bundle, null, 2),
    );
    expect(sessionStorage.getItem(PREPARATION_OPERATIONS_HANDOFF_KEY)).toBeNull();
    expect(mocks.createSchedule).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Persist replayable draft" }));
    await waitFor(() => expect(mocks.createSchedule).toHaveBeenCalledTimes(1));
    const [householdId, payload] = mocks.createSchedule.mock.calls[0];
    expect(householdId).toBe(household.id);
    expect(payload.calendar_version_id).toBe(calendar.id);
    expect(payload.occurrence_set_hash).toBe("f".repeat(64));
    expect(payload.idempotency_key).toMatch(/^schedule-create-/);
  });

  it("hides calendar registration and approval from a viewer", async () => {
    mocks.householdList.mockResolvedValue([{ ...household, current_role: "viewer" }]);
    mocks.householdGet.mockResolvedValue({
      household: { ...household, current_role: "viewer" },
      role: "viewer",
      members: [],
      active_servings_multiplier: 0,
      planning_status: "ready",
    });
    renderPage();
    expect(await screen.findByText("Schedule #21")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Resource calendars" }));
    expect(screen.queryByText("Register and activate a reviewed calendar")).not.toBeInTheDocument();
  });
});
