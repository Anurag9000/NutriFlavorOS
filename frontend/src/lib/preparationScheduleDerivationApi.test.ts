import { beforeEach, describe, expect, it, vi } from "vitest";

import { preparationScheduleDerivationApi } from "@/lib/preparationScheduleDerivationApi";

const mocks = vi.hoisted(() => ({ apiRequest: vi.fn() }));

vi.mock("@/lib/http", () => ({ apiRequest: mocks.apiRequest }));

beforeEach(() => {
  vi.resetAllMocks();
  mocks.apiRequest.mockResolvedValue({});
});

describe("preparationScheduleDerivationApi", () => {
  it("reads viewer-authorized schedule derivation evidence", async () => {
    await preparationScheduleDerivationApi.get("home one", 22);

    expect(mocks.apiRequest).toHaveBeenCalledWith(
      "/households/home%20one/preparation-operations/schedules/22/derivation",
    );
  });

  it("reads household derivation coverage denominators", async () => {
    await preparationScheduleDerivationApi.coverage("home one");

    expect(mocks.apiRequest).toHaveBeenCalledWith(
      "/households/home%20one/preparation-operations/schedule-derivation-coverage",
    );
  });

  it("exposes read-only methods only", () => {
    expect(Object.keys(preparationScheduleDerivationApi)).toEqual([
      "get",
      "coverage",
    ]);
  });
});
