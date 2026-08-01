import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ResearchPage from "@/pages/Research";

const mocks = vi.hoisted(() => ({
  catalog: vi.fn(),
  collection: vi.fn(),
  conversions: vi.fn(),
  policies: vi.fn(),
  lifecycleEvents: vi.fn(),
}));

vi.mock("@/components/AppLayout", () => ({
  default: ({ children }: { children: ReactNode }) => <main>{children}</main>,
}));

vi.mock("@/lib/platformApi", () => ({
  researchApi: {
    catalog: mocks.catalog,
    collection: mocks.collection,
  },
  evidenceHistoryApi: {
    conversions: mocks.conversions,
    storagePolicies: mocks.policies,
    lifecycleEvents: mocks.lifecycleEvents,
  },
}));

const conversionHash = "a".repeat(64);
const policyHash = "b".repeat(64);
const lifecycleTargetHash = "c".repeat(64);
const lifecycleRequestHash = "d".repeat(64);

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <ResearchPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  mocks.catalog.mockResolvedValue({
    catalog: { version: "2026-08-01.3" },
    summary: {
      tasks: { total: 37, implemented: 5, research_only: 32 },
      datasets: { total: 30, implemented: 8, research_only: 22 },
      models: { total: 75, implemented: 8, baseline_available: 32, research_only: 35 },
      experiments: { total: 29, baseline_available: 8, research_only: 21 },
      features: { total: 39, implemented: 12, baseline_available: 8, research_only: 19 },
    },
    implemented_components: {
      exact_preparation_scheduler: {
        status: "baseline_available",
        runtime_available: true,
        runtime_enabled: false,
      },
    },
  });
  mocks.collection.mockResolvedValue({
    collection: "models",
    count: 1,
    items: [
      {
        id: "exact_preparation_scheduler",
        name: "Exact Preparation Scheduler",
        readiness: "baseline_available",
        risk: "moderate",
        default_enabled: false,
      },
    ],
  });
  mocks.conversions.mockResolvedValue([
    {
      id: 11,
      canonical_name: "cooked rice",
      from_unit: "cup",
      to_unit: "g",
      record_version: "reviewed-v2",
      multiplier_min: 120,
      multiplier_max: 125,
      source_name: "Reviewed source",
      source_url: "https://example.test/rice",
      source_version: "source-v2",
      evidence_status: "reviewed",
      reviewed_at: "2026-08-01T00:00:00Z",
      reviewed_by: "Evidence reviewer",
      notes: null,
      content_hash: conversionHash,
      supersedes_conversion_id: 7,
      active: true,
      created_at: "2026-08-01T00:00:00Z",
      updated_at: "2026-08-01T00:00:00Z",
    },
  ]);
  mocks.policies.mockResolvedValue([
    {
      id: 22,
      policy_key: "pizza_refrigerated",
      policy_version: "official-2026-07-31",
      food_category: "pizza",
      storage_state: "refrigerated",
      duration_min_hours: 72,
      duration_max_hours: 96,
      maximum_temperature_c: 4,
      source_name: "Official source",
      source_url: "https://example.test/policy",
      source_version: "reviewed-2026-07-31",
      evidence_status: "reviewed",
      reviewed_at: "2026-07-31T00:00:00Z",
      reviewed_by: "Policy reviewer",
      safety_scope: "general_home_storage",
      notes: null,
      content_hash: policyHash,
      supersedes_policy_id: 19,
      active: true,
      created_at: "2026-08-01T00:00:00Z",
      updated_at: "2026-08-01T00:00:00Z",
    },
  ]);
  mocks.lifecycleEvents.mockResolvedValue([
    {
      id: 31,
      target_kind: "storage_policy",
      target_id: 19,
      action: "rejected",
      actor: "Evidence operator",
      reason: "Source scope no longer supports future automatic use",
      metadata: { ticket: "EVIDENCE-31" },
      idempotency_key: "lifecycle-policy-19",
      request_fingerprint: lifecycleRequestHash,
      target_record_version: "official-2026-06-01",
      target_content_hash: lifecycleTargetHash,
      target_was_active: true,
      created_at: "2026-08-01T01:00:00Z",
    },
  ]);
});

describe("Research registry", () => {
  it("uses catalog total fields without double-counting readiness subtotals", async () => {
    renderPage();
    expect(await screen.findByText("Exact Preparation Scheduler")).toBeInTheDocument();
    expect(screen.getByText("37")).toBeInTheDocument();
    expect(screen.getByText("30")).toBeInTheDocument();
    expect(screen.getByText("75")).toBeInTheDocument();
    expect(screen.getByText("29")).toBeInTheDocument();
    expect(screen.getByText("39")).toBeInTheDocument();
    expect(screen.queryByText("74")).not.toBeInTheDocument();
  });

  it("shows immutable versions and append-only lifecycle provenance", async () => {
    renderPage();
    await screen.findByText("Exact Preparation Scheduler");
    fireEvent.click(screen.getByRole("tab", { name: "Immutable food evidence" }));

    expect(await screen.findByText("cooked rice")).toBeInTheDocument();
    expect(screen.getByText(/Record reviewed-v2/)).toBeInTheDocument();
    expect(screen.getByText(/Evidence reviewer/)).toBeInTheDocument();
    expect(screen.getByTitle(conversionHash)).toBeInTheDocument();
    expect(screen.getByText(/Supersedes record #7/)).toBeInTheDocument();

    expect(screen.getByText("pizza")).toBeInTheDocument();
    expect(screen.getByText(/official-2026-07-31/)).toBeInTheDocument();
    expect(screen.getByText(/Policy reviewer/)).toBeInTheDocument();
    expect(screen.getByTitle(policyHash)).toBeInTheDocument();
    expect(screen.getByText(/Supersedes policy record #19/)).toBeInTheDocument();

    expect(screen.getByText(/storage policy #19/i)).toBeInTheDocument();
    expect(screen.getByText("rejected")).toBeInTheDocument();
    expect(screen.getByText(/Evidence operator/)).toBeInTheDocument();
    expect(screen.getByText(/Source scope no longer supports/)).toBeInTheDocument();
    expect(screen.getByText(/official-2026-06-01/)).toBeInTheDocument();
    expect(screen.getByTitle(lifecycleTargetHash)).toBeInTheDocument();
    expect(screen.getByTitle(lifecycleRequestHash)).toBeInTheDocument();
    expect(screen.getByLabelText("Lifecycle metadata for event 31")).toHaveTextContent("EVIDENCE-31");

    expect(mocks.conversions).toHaveBeenCalledWith({ activeOnly: false });
    expect(mocks.policies).toHaveBeenCalledWith({ activeOnly: false });
    expect(mocks.lifecycleEvents).toHaveBeenCalledWith({ limit: 500 });
  });
});
