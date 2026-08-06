import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  APPROVED_PLAN_OCCURRENCE_HANDOFF_KEY,
} from "@/lib/approvedPlanOccurrenceHandoff";
import ApprovedPlanPreparationPipelinePage from "@/pages/ApprovedPlanPreparationPipeline";

const mocks = vi.hoisted(() => ({
  toast: vi.fn(),
  householdGet: vi.fn(),
  calendars: vi.fn(),
  compilePreparation: vi.fn(),
  storeCompiledPlanPreparationHandoff: vi.fn(),
}));

vi.mock("@/components/AppLayout", () => ({
  default: ({ children }: { children: ReactNode }) => <main>{children}</main>,
}));

vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({ toast: mocks.toast }),
}));

vi.mock("@/lib/platformApi", () => ({
  householdApi: {
    get: mocks.householdGet,
  },
}));

vi.mock("@/lib/preparationOperationsApi", () => ({
  preparationOperationsApi: {
    calendars: mocks.calendars,
  },
}));

vi.mock("@/lib/householdPlanApi", () => ({
  householdPlanApi: {
    compilePreparation: mocks.compilePreparation,
  },
}));

vi.mock("@/lib/compiledPlanPreparationHandoff", () => ({
  storeCompiledPlanPreparationHandoff:
    mocks.storeCompiledPlanPreparationHandoff,
}));

const ASYNC_QUERY_TIMEOUT_MS = 5_000;
const householdId = "approved-pipeline-home";
const planId = 42;
const planVersion = 2;
const profileIdentity = `profile:7/version:v1/sha256:${"a".repeat(64)}`;

const calendar = {
  id: 9,
  household_id: householdId,
  calendar_version: "calendar-v1",
  horizon_minutes: 240,
  timezone: "UTC",
  evidence_status: "reviewed" as const,
  reviewed_at: "2026-08-02T00:00:00Z",
  reviewed_by: "Household reviewer",
  notes: null,
  content_hash: "b".repeat(64),
  supersedes_calendar_id: null,
  active: true,
  created_by_user_id: "owner@example.test",
  created_at: "2026-08-02T00:00:00Z",
  updated_at: "2026-08-02T00:00:00Z",
  resources: [
    {
      id: 1,
      calendar_version_id: 9,
      resource_id: "person",
      label: "Available cook",
      capacity: 1,
      resource_kind: "person",
      availability_windows: [{ start_minute: 0, end_minute: 240 }],
      metadata: {},
    },
  ],
};

const occurrenceSet = {
  document_version: "preparation-occurrence-set-v1" as const,
  household_id: householdId,
  occurrence_set_version: "plan-42-v2-occurrences-v1",
  duration_policy: "conservative_max" as const,
  occurrences: [
    {
      occurrence_id: "day-1.dinner",
      recipe_id: "recipe-1",
      required_finish_minute: 180,
      servings: 2,
      priority: 3,
    },
  ],
};

function storeOccurrenceHandoff() {
  sessionStorage.setItem(
    APPROVED_PLAN_OCCURRENCE_HANDOFF_KEY,
    JSON.stringify({
      document_version: "approved-plan-occurrence-handoff-v1",
      household_id: householdId,
      source_plan_id: planId,
      source_plan_version: planVersion,
      created_at: new Date().toISOString(),
      occurrence_set: occurrenceSet,
      profile_versions: { "recipe-1": profileIdentity },
    }),
  );
}

function completeCompilation() {
  return {
    household_id: householdId,
    source_plan_id: planId,
    source_plan_version: planVersion,
    calendar_version_id: calendar.id,
    calendar_version: calendar.calendar_version,
    calendar_content_hash: calendar.content_hash,
    occurrence_set: occurrenceSet,
    profile_versions: { "recipe-1": profileIdentity },
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
      tasks: [
        {
          task_id: "day-1.dinner:prep",
          duration_minutes: 15,
          earliest_start_minute: 0,
          latest_finish_minute: 180,
          priority: 3,
          resource_demands: { person: 1 },
          dependencies: [],
          metadata: {
            occurrence_id: "day-1.dinner",
            recipe_id: "recipe-1",
            profile_content_hash: "a".repeat(64),
          },
        },
      ],
    },
    schedule_response: {
      method: "deterministic_dependency_aware_resource_scheduler_v2",
      deterministic: true,
      horizon_minutes: 240,
      granularity_minutes: 5,
      scheduled: [
        {
          task_id: "day-1.dinner:prep",
          start_minute: 0,
          finish_minute: 15,
          duration_minutes: 15,
          priority: 3,
          resource_demands: { person: 1 },
          dependencies: [],
          metadata: {},
        },
      ],
      unscheduled: [],
      resource_utilization: { person: 0.0625 },
      resource_peak_usage: { person: 1 },
      makespan_minutes: 15,
      diagnostics: {},
    },
    partial: false,
    execution_status: "complete",
    warnings: ["Non-persisted deterministic compilation"],
  };
}

function renderPage(role: "owner" | "viewer" = "owner") {
  mocks.householdGet.mockResolvedValue({
    household: {
      id: householdId,
      owner_user_id: "owner@example.test",
      name: "Approved pipeline home",
      timezone: "UTC",
      version: 1,
      created_at: "2026-08-02T00:00:00Z",
      updated_at: "2026-08-02T00:00:00Z",
      current_role: role,
    },
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
    <MemoryRouter initialEntries={["/preparation/pipeline/approved-plan"]}>
      <QueryClientProvider client={client}>
        <ApprovedPlanPreparationPipelinePage />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

async function waitForPipelineInputs() {
  await waitFor(
    () => {
      expect(mocks.householdGet).toHaveBeenCalledWith(householdId);
      expect(mocks.calendars).toHaveBeenCalledWith(householdId);
    },
    { timeout: ASYNC_QUERY_TIMEOUT_MS },
  );
  expect(
    await screen.findByText(
      profileIdentity,
      {},
      { timeout: ASYNC_QUERY_TIMEOUT_MS },
    ),
  ).toBeInTheDocument();
  return screen.findByRole(
    "button",
    { name: "Compile deterministic preparation schedule" },
    { timeout: ASYNC_QUERY_TIMEOUT_MS },
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  sessionStorage.clear();
  storeOccurrenceHandoff();
  mocks.calendars.mockResolvedValue([
    calendar,
    {
      ...calendar,
      id: 10,
      calendar_version: "historical-calendar",
      content_hash: "c".repeat(64),
      active: false,
    },
  ]);
  mocks.compilePreparation.mockResolvedValue(completeCompilation());
  mocks.storeCompiledPlanPreparationHandoff.mockResolvedValue({});
});

describe("Approved-plan preparation pipeline", () => {
  it("consumes the one-time occurrence handoff without compiling automatically", async () => {
    renderPage();

    expect(
      await screen.findByText("Approved-plan preparation pipeline"),
    ).toBeInTheDocument();
    await waitForPipelineInputs();
    expect(
      sessionStorage.getItem(APPROVED_PLAN_OCCURRENCE_HANDOFF_KEY),
    ).toBeNull();
    expect(mocks.compilePreparation).not.toHaveBeenCalled();
    expect(screen.getByText(/Source plan #42 · version 2/)).toBeInTheDocument();
    expect(screen.getByText(/Finish minute 180/)).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /calendar-v1/ })).toBeInTheDocument();
    expect(
      screen.queryByRole("option", { name: /historical-calendar/ }),
    ).not.toBeInTheDocument();
  });

  it("submits the exact plan, occurrence, profile, calendar, and granularity inputs", async () => {
    renderPage();
    const compile = await waitForPipelineInputs();

    fireEvent.click(compile);

    await waitFor(() =>
      expect(mocks.compilePreparation).toHaveBeenCalledTimes(1),
    );
    expect(mocks.compilePreparation).toHaveBeenCalledWith(
      householdId,
      planId,
      {
        expected_plan_version: planVersion,
        calendar_version_id: calendar.id,
        occurrence_set: occurrenceSet,
        profile_versions: { "recipe-1": profileIdentity },
        granularity_minutes: 5,
      },
    );
    expect(
      await screen.findByText(
        "complete",
        {},
        { timeout: ASYNC_QUERY_TIMEOUT_MS },
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("day-1.dinner:prep")).toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: "Open preparation operations review",
      }),
    ).toBeEnabled();
  });

  it("requires a separate explicit action before staging operations", async () => {
    renderPage();
    const compile = await waitForPipelineInputs();
    fireEvent.click(compile);
    await screen.findByText(
      "complete",
      {},
      { timeout: ASYNC_QUERY_TIMEOUT_MS },
    );

    expect(mocks.storeCompiledPlanPreparationHandoff).not.toHaveBeenCalled();
    fireEvent.click(
      screen.getByRole("button", {
        name: "Open preparation operations review",
      }),
    );
    await waitFor(() =>
      expect(mocks.storeCompiledPlanPreparationHandoff).toHaveBeenCalledWith(
        completeCompilation(),
      ),
    );
  });

  it("invalidates compiled output when calendar inputs change", async () => {
    renderPage();
    const compile = await waitForPipelineInputs();
    fireEvent.click(compile);
    await screen.findByText(
      "complete",
      {},
      { timeout: ASYNC_QUERY_TIMEOUT_MS },
    );

    fireEvent.change(
      screen.getByLabelText("Scheduling granularity minutes"),
      { target: { value: "10" } },
    );

    expect(
      screen.queryByRole("button", {
        name: "Open preparation operations review",
      }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("day-1.dinner:prep")).not.toBeInTheDocument();
  });

  it("shows partial work and blocks the operations handoff", async () => {
    const partial = completeCompilation();
    partial.partial = true;
    partial.execution_status = "partial_unscheduled";
    partial.schedule_response.scheduled = [];
    partial.schedule_response.unscheduled = [
      {
        task_id: "day-1.dinner:prep",
        reason_code: "missing_resource",
        message: "Required resource is missing",
        missing_resources: ["person"],
        blocked_by: [],
        capacity_violations: {},
        metadata: {},
      },
    ];
    partial.warnings = ["Unscheduled work remains: missing_resource=1"];
    mocks.compilePreparation.mockResolvedValueOnce(partial);

    renderPage();
    const compile = await waitForPipelineInputs();
    fireEvent.click(compile);

    expect(
      await screen.findByText(
        "partial_unscheduled",
        {},
        { timeout: ASYNC_QUERY_TIMEOUT_MS },
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/missing_resource:/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: "Open preparation operations review",
      }),
    ).toBeDisabled();
    expect(mocks.storeCompiledPlanPreparationHandoff).not.toHaveBeenCalled();
  });

  it("keeps compilation unavailable to viewers", async () => {
    renderPage("viewer");

    expect(
      await screen.findByText(
        /Editor or owner access is required/,
        {},
        { timeout: ASYNC_QUERY_TIMEOUT_MS },
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: "Compile deterministic preparation schedule",
      }),
    ).toBeDisabled();
  });

  it("shows an explicit recovery path when no handoff exists", async () => {
    sessionStorage.clear();
    renderPage();

    expect(
      await screen.findByText("No current approved-plan occurrence handoff is available"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Open approved-plan occurrences" }),
    ).toHaveAttribute("href", "/household/plans/occurrences");
    expect(mocks.householdGet).not.toHaveBeenCalled();
    expect(mocks.calendars).not.toHaveBeenCalled();
  });
});
