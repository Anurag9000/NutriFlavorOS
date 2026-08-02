import { beforeEach, describe, expect, it, vi } from "vitest";

import { preparationTaskExecutionEligibilityApi } from "@/lib/preparationTaskExecutionEligibilityApi";

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

describe("preparationTaskExecutionEligibilityApi", () => {
  it("reads the authenticated schedule eligibility evidence", async () => {
    await preparationTaskExecutionEligibilityApi.get("home one", 17);

    expect(mocks.apiRequest).toHaveBeenCalledWith(
      "/households/home%20one/preparation-operations/schedules/17/task-execution-eligibility",
    );
  });

  it("exposes no mutation method", () => {
    expect(Object.keys(preparationTaskExecutionEligibilityApi)).toEqual(["get"]);
  });
});
