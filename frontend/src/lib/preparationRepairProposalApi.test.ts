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
  it("creates only a non-accepted, non-persisted proposal request", async () => {
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

  it("encodes repeated status filters deterministically", async () => {
    await preparationRepairProposalApi.list("home-1", [
      "proposed",
      "rejected",
    ]);

    expect(mocks.apiRequest).toHaveBeenCalledWith(
      "/households/home-1/preparation-operations/repair-proposals?status=proposed&status=rejected",
    );
  });

  it("reads proposal identity and append-only events", async () => {
    await preparationRepairProposalApi.get("home-1", 11);
    await preparationRepairProposalApi.events("home-1", 11);

    expect(mocks.apiRequest).toHaveBeenNthCalledWith(
      1,
      "/households/home-1/preparation-operations/repair-proposals/11",
    );
    expect(mocks.apiRequest).toHaveBeenNthCalledWith(
      2,
      "/households/home-1/preparation-operations/repair-proposals/11/events",
    );
  });

  it("rejects through the only implemented review mutation", async () => {
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

  it("does not expose accept, approve, persist, complete, or execute methods", () => {
    const methods = Object.keys(preparationRepairProposalApi);
    expect(methods).toEqual(["create", "list", "get", "events", "reject"]);
    expect(methods).not.toContain("accept");
    expect(methods).not.toContain("approve");
    expect(methods).not.toContain("persist");
    expect(methods).not.toContain("complete");
    expect(methods).not.toContain("execute");
  });
});
