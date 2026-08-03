import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  preparationScheduleSupportExportApi,
  serializeSupportExport,
  supportExportFilename,
  type PreparationScheduleSupportExport,
} from "@/lib/preparationScheduleSupportExportApi";

const mocks = vi.hoisted(() => ({
  apiRequest: vi.fn(),
}));

vi.mock("@/lib/http", () => ({
  apiRequest: mocks.apiRequest,
}));

const fixture = {
  document_version: "preparation-schedule-support-export-v1",
  household_id: "home one/unsafe",
  schedule_id: 17,
  evidence_hash: "a".repeat(64),
  snapshot_read_only: true,
  mutation_performed: false,
} as unknown as PreparationScheduleSupportExport;

beforeEach(() => {
  vi.resetAllMocks();
  mocks.apiRequest.mockResolvedValue(fixture);
});

describe("preparationScheduleSupportExportApi", () => {
  it("reads the viewer-authorized support export endpoint", async () => {
    await preparationScheduleSupportExportApi.get("home one", 17);

    expect(mocks.apiRequest).toHaveBeenCalledWith(
      "/households/home%20one/preparation-operations/schedules/17/support-export",
    );
  });

  it("exposes no mutation method", () => {
    expect(Object.keys(preparationScheduleSupportExportApi)).toEqual(["get"]);
  });

  it("creates a filesystem-safe hash-addressed filename", () => {
    expect(supportExportFilename(fixture)).toBe(
      "preparation-support-home-one-unsafe-schedule-17-aaaaaaaaaaaa.json",
    );
  });

  it("serializes the complete object with a trailing newline", () => {
    const serialized = serializeSupportExport(fixture);

    expect(serialized.endsWith("\n")).toBe(true);
    expect(JSON.parse(serialized)).toEqual(fixture);
    expect(serialized).toContain('"mutation_performed": false');
  });
});
