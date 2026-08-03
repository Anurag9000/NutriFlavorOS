import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { PreparationScheduleSupportExport } from "@/lib/preparationScheduleSupportExportApi";
import PreparationScheduleSupportExportPage from "@/pages/PreparationScheduleSupportExport";

const mocks = vi.hoisted(() => ({
  households: vi.fn(),
  schedules: vi.fn(),
  getExport: vi.fn(),
}));

vi.mock("@/components/AppLayout", () => ({
  default: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));
vi.mock("@/lib/platformApi", () => ({
  householdApi: { list: mocks.households },
}));
vi.mock("@/lib/preparationOperationsApi", () => ({
  preparationOperationsApi: { schedules: mocks.schedules },
}));
vi.mock("@/lib/preparationScheduleSupportExportApi", async (importOriginal) => {
  const actual = await importOriginal<
    typeof import("@/lib/preparationScheduleSupportExportApi")
  >();
  return {
    ...actual,
    preparationScheduleSupportExportApi: { get: mocks.getExport },
  };
});

const originalCreateObjectURL = Object.getOwnPropertyDescriptor(
  URL,
  "createObjectURL",
);
const originalRevokeObjectURL = Object.getOwnPropertyDescriptor(
  URL,
  "revokeObjectURL",
);

const exportFixture = {
  document_version: "preparation-schedule-support-export-v1",
  household_id: "home-1",
  schedule_id: 10,
  database_dialect: "postgresql",
  snapshot_isolation: "repeatable_read",
  snapshot_read_only: true,
  snapshot_marker: "100:100:",
  snapshot_started_at: "2026-08-03T00:00:00Z",
  snapshot_completed_at: "2026-08-03T00:00:01Z",
  schedule: {
    id: 10,
    household_id: "home-1",
    status: "approved",
    version: 2,
    schedule_hash: "b".repeat(64),
    calendar_version_id: 5,
    calendar_content_hash: "c".repeat(64),
    source_plan_id: null,
    source_plan_version: null,
    created_at: "2026-08-02T00:00:00Z",
    updated_at: "2026-08-02T00:00:00Z",
  },
  schedule_events: [{ event_type: "created" }, { event_type: "approved" }],
  derivation: {
    schedule_id: 10,
    household_id: "home-1",
    schedule_version: 2,
    schedule_status: "approved",
    schedule_hash: "b".repeat(64),
    derivation_method: "deterministic_dependency_aware_resource_scheduler_v2",
    evidence_complete: true,
    source_repair_proposal_id: null,
    source_repair_acceptance_id: null,
    source_schedule_id: null,
    warnings: [],
  },
  task_execution_eligibility: {
    schedule_id: 10,
    household_id: "home-1",
    schedule_version: 2,
    schedule_status: "approved",
    eligible: true,
    reason_code: "eligible",
    task_event_count: 1,
    accepted_proposal_id: null,
    acceptance_id: null,
    replacement_schedule_id: null,
    replacement_schedule_status: null,
    replacement_schedule_version: null,
  },
  task_execution: {
    schedule: {
      id: 10,
      household_id: "home-1",
      status: "approved",
      version: 2,
      schedule_hash: "b".repeat(64),
      calendar_version_id: 5,
      calendar_content_hash: "c".repeat(64),
      source_plan_id: null,
      source_plan_version: null,
      created_at: "2026-08-02T00:00:00Z",
      updated_at: "2026-08-02T00:00:00Z",
    },
    tasks: [{ task: { task_id: "dinner.prep" }, state: "completed" }],
    events: [{ event_type: "completed" }],
    planned_count: 0,
    in_progress_count: 0,
    completed_count: 1,
    skipped_count: 0,
    terminal_count: 1,
    remaining_count: 0,
  },
  related_repair_proposals: [],
  repair_acceptances: [],
  repair_proposal_events: {},
  evidence_hash: "a".repeat(64),
  mutation_performed: false,
  actual_execution_verified: false,
  food_safety_verified: false,
} satisfies PreparationScheduleSupportExport;

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
        <PreparationScheduleSupportExportPage />
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
  mocks.schedules.mockResolvedValue([
    { id: 10, status: "approved", version: 2 },
    { id: 22, status: "draft", version: 1 },
  ]);
  mocks.getExport.mockResolvedValue(exportFixture);
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    writable: true,
    value: vi.fn(() => "blob:support-export"),
  });
  Object.defineProperty(URL, "revokeObjectURL", {
    configurable: true,
    writable: true,
    value: vi.fn(),
  });
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
  if (originalCreateObjectURL) {
    Object.defineProperty(URL, "createObjectURL", originalCreateObjectURL);
  } else {
    Reflect.deleteProperty(URL, "createObjectURL");
  }
  if (originalRevokeObjectURL) {
    Object.defineProperty(URL, "revokeObjectURL", originalRevokeObjectURL);
  } else {
    Reflect.deleteProperty(URL, "revokeObjectURL");
  }
});

describe("Preparation schedule support export workspace", () => {
  it("does not generate evidence until the user explicitly requests it", async () => {
    renderPage();

    expect(
      await screen.findByRole("heading", {
        name: "Preparation schedule support export",
      }),
    ).toBeInTheDocument();
    expect(mocks.getExport).not.toHaveBeenCalled();
    expect(
      screen.getByRole("button", { name: "Generate read-only snapshot" }),
    ).toBeInTheDocument();
  });

  it("shows server identity, evidence counts, and non-claims", async () => {
    renderPage();
    await screen.findByRole("button", { name: "Generate read-only snapshot" });

    fireEvent.click(
      screen.getByRole("button", { name: "Generate read-only snapshot" }),
    );

    expect(await screen.findByText("Server evidence snapshot ready")).toBeInTheDocument();
    expect(screen.getByText("aaaaaaaaaaaaaaaa…aaaaaaaaaa")).toBeInTheDocument();
    expect(screen.getByText("postgresql · repeatable_read")).toBeInTheDocument();
    expect(screen.getByText("2 schedule events")).toBeInTheDocument();
    expect(screen.getByText("1 task events")).toBeInTheDocument();
    expect(screen.getByText("eligible")).toBeInTheDocument();
    expect(screen.getByText(/Mutation performed: false/)).toBeInTheDocument();
    expect(screen.getByText(/Actual execution verified: false/)).toBeInTheDocument();
    expect(screen.getByText(/Food safety verified: false/)).toBeInTheDocument();
    expect(mocks.getExport).toHaveBeenCalledWith("home-1", 10);
  });

  it("downloads the complete JSON under a hash-addressed filename", async () => {
    renderPage();
    fireEvent.click(
      await screen.findByRole("button", { name: "Generate read-only snapshot" }),
    );
    await screen.findByText("Server evidence snapshot ready");

    fireEvent.click(screen.getByRole("button", { name: "Download JSON evidence" }));

    expect(URL.createObjectURL).toHaveBeenCalledTimes(1);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:support-export");
    expect(
      screen.getByText(
        "Downloaded preparation-support-home-1-schedule-10-aaaaaaaaaaaa.json.",
      ),
    ).toBeInTheDocument();
  });

  it("clears stale evidence when schedule scope changes", async () => {
    renderPage();
    fireEvent.click(
      await screen.findByRole("button", { name: "Generate read-only snapshot" }),
    );
    await screen.findByText("Server evidence snapshot ready");

    fireEvent.change(screen.getByLabelText("Schedule"), {
      target: { value: "22" },
    });

    await waitFor(() => {
      expect(screen.queryByText("Server evidence snapshot ready")).not.toBeInTheDocument();
    });
    expect(mocks.getExport).toHaveBeenCalledTimes(1);
  });

  it("surfaces fail-closed server errors without creating a download", async () => {
    mocks.getExport.mockRejectedValueOnce(
      new Error("Support export evidence is internally inconsistent"),
    );
    renderPage();

    fireEvent.click(
      await screen.findByRole("button", { name: "Generate read-only snapshot" }),
    );

    expect(await screen.findByText("Support export unavailable")).toBeInTheDocument();
    expect(
      screen.getByText("Support export evidence is internally inconsistent"),
    ).toBeInTheDocument();
    expect(URL.createObjectURL).not.toHaveBeenCalled();
  });
});
