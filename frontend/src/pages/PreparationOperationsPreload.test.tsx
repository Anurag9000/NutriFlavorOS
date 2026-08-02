import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PREPARATION_OPERATIONS_HANDOFF_KEY } from "@/lib/preparationOperationsHandoff";
import PreparationOperationsPage from "@/pages/PreparationOperations";

const mocks = vi.hoisted(() => ({
  calendar: vi.fn(),
  householdList: vi.fn(),
  householdGet: vi.fn(),
  schedules: vi.fn(),
  events: vi.fn(),
  createSchedule: vi.fn(),
  approve: vi.fn(),
  cancel: vi.fn(),
  invalidate: vi.fn(),
  toast: vi.fn(),
}));

vi.mock("@/components/AppLayout", () => ({
  default: ({ children }: { children: ReactNode }) => <div>{children}</div>,
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
    calendar: mocks.calendar,
    schedules: mocks.schedules,
    events: mocks.events,
    createSchedule: mocks.createSchedule,
    approve: mocks.approve,
    cancel: mocks.cancel,
    invalidate: mocks.invalidate,
  },
}));

const householdId = "preload-home";
const handoff = {
  document_version: "preparation-operations-handoff-v2",
  household_id: householdId,
  created_at: new Date().toISOString(),
  occurrence_set_hash_preview: "a".repeat(64),
  bundle: {
    calendar_version_id: 8,
    source_plan_id: null,
    source_plan_version: null,
    occurrence_set: {
      document_version: "preparation-occurrence-set-v1",
      household_id: householdId,
      occurrence_set_version: "preload-occurrences-v1",
      duration_policy: "conservative_max",
      occurrences: [
        {
          occurrence_id: "meal-1",
          recipe_id: "recipe-1",
          required_finish_minute: 120,
          servings: 1,
          priority: 1,
        },
      ],
    },
    profile_versions: {
      "recipe-1": `profile:1/version:v1/sha256:${"b".repeat(64)}`,
    },
    schedule_request: {
      horizon_minutes: 180,
      granularity_minutes: 5,
      resources: [
        {
          resource_id: "person",
          capacity: 1,
          availability_windows: [{ start_minute: 0, end_minute: 180 }],
          label: "Person",
        },
      ],
      tasks: [
        {
          task_id: "meal-1:prep",
          duration_minutes: 10,
          earliest_start_minute: 0,
          latest_finish_minute: 120,
          priority: 1,
          resource_demands: { person: 1 },
          dependencies: [],
          metadata: {},
        },
      ],
    },
    schedule_response: {
      method: "deterministic_dependency_aware_resource_scheduler_v2",
      deterministic: true,
      horizon_minutes: 180,
      granularity_minutes: 5,
      scheduled: [
        {
          task_id: "meal-1:prep",
          start_minute: 0,
          finish_minute: 10,
          duration_minutes: 10,
          priority: 1,
          resource_demands: { person: 1 },
          dependencies: [],
          metadata: {},
        },
      ],
      unscheduled: [],
      resource_utilization: { person: 0.055556 },
      resource_peak_usage: { person: 1 },
      makespan_minutes: 10,
      diagnostics: {},
    },
    notes: null,
  },
};

const calendar = {
  id: 8,
  household_id: householdId,
  calendar_version: "preload-calendar-v1",
  horizon_minutes: 180,
  timezone: "UTC",
  evidence_status: "reviewed" as const,
  reviewed_at: "2026-08-02T00:00:00Z",
  reviewed_by: "Reviewer",
  notes: null,
  content_hash: "c".repeat(64),
  supersedes_calendar_id: null,
  active: true,
  created_by_user_id: "owner@example.test",
  created_at: "2026-08-02T00:00:00Z",
  updated_at: "2026-08-02T00:00:00Z",
  resources: [
    {
      id: 1,
      calendar_version_id: 8,
      resource_id: "person",
      label: "Person",
      capacity: 1,
      resource_kind: "person",
      availability_windows: [{ start_minute: 0, end_minute: 180 }],
      metadata: {},
    },
  ],
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
        <PreparationOperationsPage />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  sessionStorage.clear();
  sessionStorage.setItem(PREPARATION_OPERATIONS_HANDOFF_KEY, JSON.stringify(handoff));
  mocks.householdList.mockResolvedValue([
    {
      id: householdId,
      owner_user_id: "owner@example.test",
      name: "Preload home",
      timezone: "UTC",
      version: 1,
      created_at: "2026-08-02T00:00:00Z",
      updated_at: "2026-08-02T00:00:00Z",
      current_role: "owner",
    },
  ]);
  mocks.householdGet.mockResolvedValue({
    household: {
      id: householdId,
      owner_user_id: "owner@example.test",
      name: "Preload home",
      timezone: "UTC",
      version: 1,
      created_at: "2026-08-02T00:00:00Z",
      updated_at: "2026-08-02T00:00:00Z",
      current_role: "owner",
    },
    role: "owner",
    members: [],
    active_servings_multiplier: 1,
    planning_status: "ready",
  });
  mocks.schedules.mockResolvedValue([]);
  mocks.events.mockResolvedValue([]);
});

describe("Preparation operations calendar preload", () => {
  it("does not consume the handoff until the exact calendar is loaded", async () => {
    let resolveCalendar: (value: typeof calendar) => void = () => undefined;
    mocks.calendar.mockImplementation(
      () => new Promise<typeof calendar>((resolve) => {
        resolveCalendar = resolve;
      }),
    );
    renderPage();

    expect(
      await screen.findByText(/Loading the exact reviewed calendar/),
    ).toBeInTheDocument();
    expect(sessionStorage.getItem(PREPARATION_OPERATIONS_HANDOFF_KEY)).not.toBeNull();

    resolveCalendar(calendar);

    expect(await screen.findByText("Structured persistence review")).toBeInTheDocument();
    expect(sessionStorage.getItem(PREPARATION_OPERATIONS_HANDOFF_KEY)).toBeNull();
    expect(mocks.calendar).toHaveBeenCalledWith(householdId, calendar.id);
  });
});
