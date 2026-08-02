import { beforeEach, describe, expect, it, vi } from "vitest";

import { preparationRepairProposalApi } from "@/lib/preparationRepairProposalApi";

const mocks = vi.hoisted(() => ({
  apiRequest: vi.fn(),
}));

vi.mock("@/lib/http", () => ({
  apiRequest: mocks.apiRequest,
}));

beforeEach(() => {
  vi.resetAllMocks();
  mocks.apiRequest.mockResolvedValue({});
});

describe("preparationRepairProposalApi", () => {
  it("creates only an advisory proposal request", async () => {
    const payload = {
      source_schedule_id: 7,
      expected_source_version: 2,
      target_calendar_version_id: 3,
      revised_request: {
        horizon_minutes: 120,
        granularity_minutes: 5,
        resources: [],
        tasks: [],
      },
      immutable_task_ids: [],
      strategy: "greedy_min_change" as const,
      notes: "Review this candidate",
      acknowledge_non_acceptance: true as const,
      acknowledge_non_persistence: true as const,
      idempotency_key: "repair-proposal-client-0001",
    };

    await preparationRepairProposalApi.create("home-1", payload);

    expect(mocks.apiRequest).toHaveBeenCalledWith(
      "/households/home-1/preparation-operations/repair-proposals",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  });

  it("encodes repeated status filters including accepted", async () => {
    await preparationRepairProposalApi.list("home-1", [
      "proposed",
      "accepted",
      "rejected",
    ]);

    expect(mocks.apiRequest).toHaveBeenCalledWith(
      "/households/home-1/preparation-operations/repair-proposals?status=proposed&status=accepted&status=rejected",
    );
  });

  it("reads proposal, immutable acceptance, and append-only events", async () => {
    await preparationRepairProposalApi.get("home-1", 11);
    await preparationRepairProposalApi.acceptance("home-1", 11);
    await preparationRepairProposalApi.events("home-1", 11);

    expect(mocks.apiRequest).toHaveBeenNthCalledWith(
      1,
      "/households/home-1/preparation-operations/repair-proposals/11",
    );
    expect(mocks.apiRequest).toHaveBeenNthCalledWith(
      2,
      "/households/home-1/preparation-operations/repair-proposals/11/acceptance",
    );
    expect(mocks.apiRequest).toHaveBeenNthCalledWith(
      3,
      "/households/home-1/preparation-operations/repair-proposals/11/events",
    );
  });

  it("accepts only through an exact new-draft request", async () => {
    const payload = {
      expected_proposal_version: 1,
      expected_source_schedule_version: 2,
      expected_source_schedule_hash: "a".repeat(64),
      expected_source_schedule_request_hash: "b".repeat(64),
      expected_target_calendar_content_hash: "c".repeat(64),
      expected_repair_request_hash: "d".repeat(64),
      expected_repair_result_hash: "e".repeat(64),
      expected_revised_request_hash: "f".repeat(64),
      expected_repaired_response_hash: "1".repeat(64),
      acknowledged_task_ids: ["dinner.prep"],
      reason: "Create a separately approvable repaired draft",
      acknowledge_creates_new_draft_only: true as const,
      idempotency_key: "repair-proposal-accept-client-0001",
      metadata: { reviewed_change_count: 1 },
    };

    await preparationRepairProposalApi.accept("home-1", 11, payload);

    expect(mocks.apiRequest).toHaveBeenCalledWith(
      "/households/home-1/preparation-operations/repair-proposals/11/accept",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  });

  it("retains versioned rejection as a separate review mutation", async () => {
    const payload = {
      expected_version: 1,
      reason: "The movement is not acceptable",
      idempotency_key: "repair-proposal-reject-client-0001",
      metadata: { reviewed_change_count: 2 },
    };

    await preparationRepairProposalApi.reject("home-1", 11, payload);

    expect(mocks.apiRequest).toHaveBeenCalledWith(
      "/households/home-1/preparation-operations/repair-proposals/11/reject",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  });

  it("exposes acceptance but no approval, execution, or completion method", () => {
    const methods = Object.keys(preparationRepairProposalApi);
    expect(methods).toEqual([
      "create",
      "list",
      "get",
      "acceptance",
      "events",
      "accept",
      "reject",
    ]);
    expect(methods).not.toContain("approve");
    expect(methods).not.toContain("persist");
    expect(methods).not.toContain("complete");
    expect(methods).not.toContain("execute");
  });
});
