import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PreparationRepairProposalsPage from "@/pages/PreparationRepairProposals";

const mocks = vi.hoisted(() => ({
  households: vi.fn(),
  schedules: vi.fn(),
  calendars: vi.fn(),
  proposals: vi.fn(),
  events: vi.fn(),
  acceptance: vi.fn(),
  create: vi.fn(),
  accept: vi.fn(),
  reject: vi.fn(),
}));

vi.mock("@/components/AppLayout", () => ({
  default: ({ children }: { children: ReactNode }) => <main>{children}</main>,
}));
vi.mock("@/lib/platformApi", () => ({ householdApi: { list: mocks.households } }));
vi.mock("@/lib/preparationOperationsApi", () => ({
  preparationOperationsApi: {
    schedules: mocks.schedules,
    calendars: mocks.calendars,
  },
}));
vi.mock("@/lib/preparationRepairProposalApi", () => ({
  preparationRepairProposalApi: {
    list: mocks.proposals,
    events: mocks.events,
    acceptance: mocks.acceptance,
    create: mocks.create,
    accept: mocks.accept,
    reject: mocks.reject,
  },
}));

const request = {
  horizon_minutes: 120,
  granularity_minutes: 5,
  resources: [
    {
      resource_id: "person",
      capacity: 1,
      availability_windows: [{ start_minute: 0, end_minute: 120 }],
      label: "Available cook",
    },
  ],
  tasks: [
    {
      task_id: "dinner.prep",
      duration_minutes: 10,
      earliest_start_minute: 0,
      latest_finish_minute: 60,
      priority: 1,
      resource_demands: { person: 1 },
      dependencies: [],
      metadata: {
        occurrence_id: "dinner",
        preparation_profile_id: 9,
        preparation_profile_version: 2,
        servings: 2,
        batch_scale: 1,
      },
    },
  ],
};

const deterministicTask = {
  task_id: "dinner.prep",
  start_minute: 0,
  finish_minute: 10,
  duration_minutes: 10,
  priority: 1,
  resource_demands: { person: 1 },
  dependencies: [],
  metadata: request.tasks[0].metadata,
};

const schedule = {
  id: 7,
  household_id: "home-1",
  calendar_version_id: 3,
  calendar_content_hash: "a".repeat(64),
  source_plan_id: null,
  source_plan_version: null,
  occurrence_set_version: "occurrences-v1",
  occurrence_set_hash: "b".repeat(64),
  occurrence_set: {},
  profile_versions: { dinner: 2 },
  schedule_request: request,
  schedule_request_hash: "c".repeat(64),
  replay_status: "replayable",
  schedule: {
    method: "deterministic_dependency_aware_resource_scheduler_v2",
    deterministic: true,
    horizon_minutes: 120,
    granularity_minutes: 5,
    scheduled: [deterministicTask],
    unscheduled: [],
    resource_utilization: { person: 1 / 12 },
    resource_peak_usage: { person: 1 },
    makespan_minutes: 10,
    diagnostics: {},
  },
  schedule_hash: "d".repeat(64),
  status: "approved",
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

const calendar = {
  id: 3,
  household_id: "home-1",
  calendar_version: "v1",
  horizon_minutes: 120,
  timezone: "UTC",
  evidence_status: "reviewed",
  reviewed_at: "2026-08-02T00:00:00Z",
  reviewed_by: "owner@example.test",
  notes: null,
  content_hash: "a".repeat(64),
  supersedes_calendar_id: null,
  active: true,
  created_by_user_id: "owner@example.test",
  created_at: "2026-08-02T00:00:00Z",
  updated_at: "2026-08-02T00:00:00Z",
  resources: request.resources,
};

const repairResult = {
  response: {
    ...schedule.schedule,
    method: "deterministic_minimal_change_preparation_repair_v1",
    scheduled: [{ ...deterministicTask, start_minute: 5, finish_minute: 15 }],
    makespan_minutes: 15,
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
  source_schedule_hash: schedule.schedule_hash,
  source_schedule_request_hash: schedule.schedule_request_hash,
  target_calendar_version_id: 3,
  target_calendar_content_hash: calendar.content_hash,
  repair_request_hash: "2".repeat(64),
  repair_result_hash: "3".repeat(64),
  revised_request_hash: repairResult.revised_request_hash,
  repaired_response_hash: repairResult.repaired_response_hash,
  required_acknowledgement_task_ids: ["dinner.prep"],
  repair_result: repairResult,
  status: "proposed",
  version: 1,
  notes: "Review the shift",
  created_by_user_id: "editor@example.test",
  rejected_by_user_id: null,
  rejected_at: null,
  rejection_reason: null,
  current: true,
  stale_reasons: [],
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

const acceptedProposal = {
  ...proposal,
  status: "accepted",
  version: 2,
  current: false,
  stale_reasons: ["proposal_status_accepted"],
  accepted: true,
  schedule_persistence_performed: true,
  accepted_schedule_id: 22,
  accepted_schedule_hash: "5".repeat(64),
  accepted_by_user_id: "editor@example.test",
  accepted_at: "2026-08-02T01:00:00Z",
  acceptance_reason: "Create a separately approvable draft",
};

const acceptance = {
  id: 31,
  household_id: "home-1",
  proposal_id: 11,
  proposal_version_before: 1,
  proposal_version_after: 2,
  source_schedule_id: 7,
  source_schedule_version: 2,
  created_schedule_id: 22,
  created_schedule_version: 1,
  created_schedule_status: "draft",
  created_schedule_hash: "5".repeat(64),
  derivation_method: "deterministic_minimal_change_preparation_repair_v1",
  source_schedule_hash: schedule.schedule_hash,
  source_schedule_request_hash: schedule.schedule_request_hash,
  target_calendar_content_hash: calendar.content_hash,
  repair_request_hash: proposal.repair_request_hash,
  repair_result_hash: proposal.repair_result_hash,
  revised_request_hash: proposal.revised_request_hash,
  repaired_response_hash: proposal.repaired_response_hash,
  acknowledged_task_ids: ["dinner.prep"],
  reason: "Create a separately approvable draft",
  actor_user_id: "editor@example.test",
  metadata: { reviewed_change_count: 1 },
  idempotency_key: "repair-accept:fixed-uuid",
  request_fingerprint: "6".repeat(64),
  created_at: "2026-08-02T01:00:00Z",
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
  request_fingerprint: "4".repeat(64),
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
        <PreparationRepairProposalsPage />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.stubGlobal("crypto", { randomUUID: vi.fn(() => "fixed-uuid") });
  mocks.households.mockResolvedValue([household("editor")]);
  mocks.schedules.mockResolvedValue([schedule]);
  mocks.calendars.mockResolvedValue([calendar]);
  mocks.proposals.mockResolvedValue([proposal]);
  mocks.events.mockResolvedValue([createdEvent]);
  mocks.acceptance.mockResolvedValue(acceptance);
  mocks.create.mockResolvedValue(proposal);
  mocks.accept.mockResolvedValue({
    proposal: acceptedProposal,
    acceptance,
    accepted: true,
    schedule_persistence_performed: true,
    approval_performed: false,
    execution_performed: false,
  });
  mocks.reject.mockResolvedValue({
    ...proposal,
    status: "rejected",
    version: 2,
    current: false,
    stale_reasons: ["proposal_status_rejected"],
    rejected_by_user_id: "editor@example.test",
    rejected_at: "2026-08-02T01:00:00Z",
    rejection_reason: "Not acceptable",
  });
});

describe("Preparation repair proposal registry", () => {
  it("shows the separated proposal, acceptance, and owner approval boundary", async () => {
    renderPage();

    expect(
      await screen.findByRole("heading", { name: "Repair proposal registry" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Two explicit lifecycle decisions")).toBeInTheDocument();
    expect(screen.getByText(/Draft persistence: false/)).toBeInTheDocument();
    expect(screen.getByText(createdEvent.reason)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Schedule approval" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Approve/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Execute/i })).not.toBeInTheDocument();
  });

  it("requires both advisory acknowledgements before proposal creation", async () => {
    renderPage();
    const button = await screen.findByRole("button", {
      name: "Create advisory proposal",
    });
    expect(button).toBeDisabled();

    fireEvent.click(
      screen.getByRole("checkbox", {
        name: /proposal creation is not acceptance or owner approval/i,
      }),
    );
    expect(button).toBeDisabled();
    fireEvent.click(
      screen.getByRole("checkbox", {
        name: /does not persist a replacement schedule/i,
      }),
    );
    expect(button).toBeEnabled();
  });

  it("submits exact proposal creation evidence", async () => {
    renderPage();
    await screen.findByLabelText("Strict revised request JSON");

    fireEvent.click(screen.getByRole("checkbox", { name: /dinner\.prep/i }));
    fireEvent.click(
      screen.getByRole("checkbox", {
        name: /proposal creation is not acceptance or owner approval/i,
      }),
    );
    fireEvent.click(
      screen.getByRole("checkbox", {
        name: /does not persist a replacement schedule/i,
      }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Create advisory proposal" }));

    await waitFor(() => expect(mocks.create).toHaveBeenCalledTimes(1));
    expect(mocks.create).toHaveBeenCalledWith("home-1", {
      source_schedule_id: 7,
      expected_source_version: 2,
      target_calendar_version_id: 3,
      revised_request: request,
      immutable_task_ids: ["dinner.prep"],
      strategy: "greedy_min_change",
      notes: null,
      acknowledge_non_acceptance: true,
      acknowledge_non_persistence: true,
      idempotency_key: "repair-proposal:fixed-uuid",
    });
  });

  it("requires every changed task, a reason, and draft-only confirmation", async () => {
    renderPage();
    const button = await screen.findByRole("button", {
      name: "Accept and create draft",
    });
    expect(button).toBeDisabled();

    fireEvent.click(
      screen.getByRole("checkbox", { name: /reviewed the change to dinner\.prep/i }),
    );
    expect(button).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Acceptance reason"), {
      target: { value: "Create a separately approvable draft" },
    });
    expect(button).toBeDisabled();
    fireEvent.click(
      screen.getByRole("checkbox", {
        name: /creates one new draft only; it does not approve, execute, or complete/i,
      }),
    );
    expect(button).toBeEnabled();
  });

  it("submits every exact proposal hash when accepting", async () => {
    renderPage();
    await screen.findByRole("button", { name: "Accept and create draft" });
    fireEvent.click(
      screen.getByRole("checkbox", { name: /reviewed the change to dinner\.prep/i }),
    );
    fireEvent.change(screen.getByLabelText("Acceptance reason"), {
      target: { value: "Create a separately approvable draft" },
    });
    fireEvent.click(
      screen.getByRole("checkbox", {
        name: /creates one new draft only; it does not approve, execute, or complete/i,
      }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Accept and create draft" }));

    await waitFor(() => expect(mocks.accept).toHaveBeenCalledTimes(1));
    expect(mocks.accept).toHaveBeenCalledWith("home-1", 11, {
      expected_proposal_version: 1,
      expected_source_schedule_version: 2,
      expected_source_schedule_hash: proposal.source_schedule_hash,
      expected_source_schedule_request_hash: proposal.source_schedule_request_hash,
      expected_target_calendar_content_hash: proposal.target_calendar_content_hash,
      expected_repair_request_hash: proposal.repair_request_hash,
      expected_repair_result_hash: proposal.repair_result_hash,
      expected_revised_request_hash: proposal.revised_request_hash,
      expected_repaired_response_hash: proposal.repaired_response_hash,
      acknowledged_task_ids: ["dinner.prep"],
      reason: "Create a separately approvable draft",
      acknowledge_creates_new_draft_only: true,
      idempotency_key: "repair-accept:fixed-uuid",
      metadata: { required_acknowledgement_task_count: 1 },
    });
  });

  it("shows immutable accepted draft evidence without auto-approval", async () => {
    mocks.proposals.mockResolvedValueOnce([acceptedProposal]);
    mocks.events.mockResolvedValueOnce([
      createdEvent,
      {
        ...createdEvent,
        id: 2,
        event_type: "accepted",
        from_status: "proposed",
        to_status: "accepted",
        reason: acceptance.reason,
        proposal_version_before: 1,
        proposal_version_after: 2,
      },
    ]);
    renderPage();

    expect(await screen.findByText("Accepted draft evidence")).toBeInTheDocument();
    expect(screen.getByText("#22")).toBeInTheDocument();
    expect(screen.getByText("Owner approval still required")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Review draft for approval" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Accept and create draft" })).not.toBeInTheDocument();
    expect(mocks.acceptance).toHaveBeenCalledWith("home-1", 11);
  });

  it("keeps viewers read-only while preserving proposal evidence", async () => {
    mocks.households.mockResolvedValueOnce([household("viewer")]);
    renderPage();

    expect(
      await screen.findByRole("heading", { name: "Repair proposal registry" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Create advisory proposal" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Accept and create draft" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reject proposal" })).not.toBeInTheDocument();
    expect(screen.getByText(/Draft persistence: false/)).toBeInTheDocument();
  });

  it("blocks acceptance controls for stale proposals", async () => {
    mocks.proposals.mockResolvedValueOnce([
      {
        ...proposal,
        current: false,
        stale_reasons: [
          "source_schedule_has_execution_history",
          "source_schedule_version_changed",
        ],
      },
    ]);
    renderPage();

    expect(await screen.findByText("Cannot accept while stale")).toBeInTheDocument();
    expect(screen.getByText("source schedule has execution history")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Accept and create draft" })).not.toBeInTheDocument();
  });
});
