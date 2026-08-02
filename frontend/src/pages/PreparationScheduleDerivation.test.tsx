import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PreparationScheduleDerivationPage from "@/pages/PreparationScheduleDerivation";

const mocks = vi.hoisted(() => ({
  households: vi.fn(),
  schedules: vi.fn(),
  derivation: vi.fn(),
  coverage: vi.fn(),
}));

vi.mock("@/components/AppLayout", () => ({
  default: ({ children }: { children: ReactNode }) => <main>{children}</main>,
}));
vi.mock("@/lib/platformApi", () => ({
  householdApi: { list: mocks.households },
}));
vi.mock("@/lib/preparationOperationsApi", () => ({
  preparationOperationsApi: { schedules: mocks.schedules },
}));
vi.mock("@/lib/preparationScheduleDerivationApi", () => ({
  preparationScheduleDerivationApi: {
    get: mocks.derivation,
    coverage: mocks.coverage,
  },
}));

const schedules = [
  { id: 10, status: "approved", version: 2 },
  { id: 22, status: "draft", version: 1 },
];

const coverage = {
  household_id: "home-1",
  generated_at: "2026-08-02T00:00:00Z",
  schedule_total: 2,
  original_schedule_count: 1,
  repair_schedule_count: 1,
  unknown_method_count: 0,
  complete_derivation_count: 2,
  incomplete_derivation_count: 0,
  accepted_proposal_count: 1,
  acceptance_record_count: 1,
  repaired_draft_count: 1,
  repaired_approved_count: 0,
  repaired_execution_history_count: 0,
  method_counts: {
    deterministic_dependency_aware_resource_scheduler_v2: 1,
    deterministic_minimal_change_preparation_repair_v1: 1,
  },
  derivation_coverage_ratio: 1,
  repair_acceptance_link_coverage_ratio: 1,
  latest_acceptance_at: "2026-08-02T01:00:00Z",
  warnings: [] as string[],
};

const originalEvidence = {
  schedule_id: 10,
  household_id: "home-1",
  schedule_version: 2,
  schedule_status: "approved",
  schedule_hash: "a".repeat(64),
  derivation_method: "deterministic_dependency_aware_resource_scheduler_v2",
  evidence_complete: true,
  source_repair_proposal_id: null,
  source_repair_proposal_version: null,
  source_repair_acceptance_id: null,
  source_schedule_id: null,
  source_schedule_version: null,
  source_schedule_hash: null,
  source_schedule_request_hash: null,
  target_calendar_content_hash: null,
  repair_request_hash: null,
  repair_result_hash: null,
  revised_request_hash: null,
  repaired_response_hash: null,
  accepted_by_user_id: null,
  accepted_at: null,
  acceptance_reason: null,
  warnings: [],
  created_at: "2026-08-02T00:00:00Z",
  updated_at: "2026-08-02T00:00:00Z",
};

const repairEvidence = {
  schedule_id: 22,
  household_id: "home-1",
  schedule_version: 1,
  schedule_status: "draft",
  schedule_hash: "b".repeat(64),
  derivation_method: "deterministic_minimal_change_preparation_repair_v1",
  evidence_complete: true,
  source_repair_proposal_id: 11,
  source_repair_proposal_version: 2,
  source_repair_acceptance_id: 31,
  source_schedule_id: 10,
  source_schedule_version: 2,
  source_schedule_hash: "c".repeat(64),
  source_schedule_request_hash: "d".repeat(64),
  target_calendar_content_hash: "e".repeat(64),
  repair_request_hash: "f".repeat(64),
  repair_result_hash: "1".repeat(64),
  revised_request_hash: "2".repeat(64),
  repaired_response_hash: "3".repeat(64),
  accepted_by_user_id: "editor@example.test",
  accepted_at: "2026-08-02T01:00:00Z",
  acceptance_reason: "Create a separately approvable repaired draft",
  warnings: [],
  created_at: "2026-08-02T01:00:00Z",
  updated_at: "2026-08-02T01:00:00Z",
};

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={client}>
        <PreparationScheduleDerivationPage />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  mocks.households.mockResolvedValue([
    { id: "home-1", name: "Home One", current_role: "viewer" },
    { id: "home-2", name: "Home Two", current_role: "owner" },
  ]);
  mocks.schedules.mockResolvedValue(schedules);
  mocks.coverage.mockResolvedValue(coverage);
  mocks.derivation.mockImplementation(
    async (_householdId: string, scheduleId: number) =>
      scheduleId === 22 ? repairEvidence : originalEvidence,
  );
});

describe("Preparation schedule derivation inspector", () => {
  it("shows household coverage with explicit denominators", async () => {
    renderPage();

    expect(
      await screen.findByText("Household derivation coverage"),
    ).toBeInTheDocument();
    expect(screen.getByText("Schedules")).toBeInTheDocument();
    expect(screen.getByText("Repair-derived")).toBeInTheDocument();
    expect(screen.getAllByText("100.0%")).toHaveLength(2);
    expect(screen.getByText("2 complete of 2")).toBeInTheDocument();
    expect(mocks.coverage).toHaveBeenCalledWith("home-1");
  });

  it("shows original scheduler evidence without fabricated repair links", async () => {
    renderPage();

    expect(
      await screen.findByRole("heading", { name: "Schedule derivation evidence" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByText("Original deterministic scheduler"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("No repair proposal or acceptance applies"),
    ).toBeInTheDocument();
    expect(screen.getByText(/Evidence complete: true/)).toBeInTheDocument();
    expect(mocks.derivation).toHaveBeenCalledWith("home-1", 10);
  });

  it("shows the full accepted repair chain", async () => {
    renderPage();
    await screen.findByText("Original deterministic scheduler");

    fireEvent.change(screen.getByLabelText("Schedule"), {
      target: { value: "22" },
    });

    expect(await screen.findByText("Accepted repair chain")).toBeInTheDocument();
    expect(screen.getByText("#11 · version 2")).toBeInTheDocument();
    expect(screen.getByText("#31")).toBeInTheDocument();
    expect(screen.getByText("#10 · version 2")).toBeInTheDocument();
    expect(screen.getByText("editor@example.test")).toBeInTheDocument();
    expect(
      screen.getByText("Create a separately approvable repaired draft"),
    ).toBeInTheDocument();
    expect(mocks.derivation).toHaveBeenCalledWith("home-1", 22);
  });

  it("surfaces incomplete derivation coverage warnings", async () => {
    mocks.coverage.mockResolvedValueOnce({
      ...coverage,
      complete_derivation_count: 1,
      incomplete_derivation_count: 1,
      derivation_coverage_ratio: 0.5,
      repair_acceptance_link_coverage_ratio: 0,
      warnings: ["schedule 22 has incomplete repair derivation evidence"],
    });
    renderPage();

    expect(
      await screen.findByText("Incomplete derivation chains"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("schedule 22 has incomplete repair derivation evidence"),
    ).toBeInTheDocument();
  });

  it("reloads schedule, coverage, and derivation scope after household change", async () => {
    renderPage();
    await screen.findByText("Original deterministic scheduler");

    fireEvent.change(screen.getByLabelText("Household"), {
      target: { value: "home-2" },
    });

    await waitFor(() => {
      expect(mocks.schedules).toHaveBeenCalledWith("home-2");
      expect(mocks.coverage).toHaveBeenCalledWith("home-2");
      expect(mocks.derivation).toHaveBeenCalledWith("home-2", 10);
    });
  });

  it("surfaces fail-closed derivation errors", async () => {
    mocks.derivation.mockRejectedValueOnce(
      new Error("Schedule derivation evidence disagrees for repair_result_hash"),
    );
    renderPage();

    expect(
      await screen.findByText("Derivation evidence unavailable"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Schedule derivation evidence disagrees for repair_result_hash",
      ),
    ).toBeInTheDocument();
  });
});
