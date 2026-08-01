import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LeftoverPolicyProvenance from "@/components/household/LeftoverPolicyProvenance";

const mocks = vi.hoisted(() => ({
  leftoverStoragePolicy: vi.fn(),
}));

vi.mock("@/lib/platformApi", () => ({
  householdApi: {
    leftoverStoragePolicy: mocks.leftoverStoragePolicy,
  },
}));

const baseLeftover = {
  id: 51,
  household_id: "household-1",
  recipe_id: "rice-recipe",
  source_plan_id: null,
  portions_available: 2,
  cooked_at: "2026-07-31T18:00:00Z",
  expires_at: "2026-08-04T18:00:00Z",
  frozen: false,
  storage_policy_key: "rice_refrigerated",
  notes: null,
  version: 1,
  created_at: "2026-07-31T18:00:00Z",
  updated_at: "2026-07-31T18:00:00Z",
};

function renderComponent(leftover = baseLeftover) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <LeftoverPolicyProvenance
        householdId="household-1"
        leftover={leftover}
      />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("LeftoverPolicyProvenance", () => {
  it("does not query when no immutable policy was selected", () => {
    renderComponent({ ...baseLeftover, storage_policy_key: null });
    expect(
      screen.getByText(/No immutable storage-policy version was selected/),
    ).toBeInTheDocument();
    expect(mocks.leftoverStoragePolicy).not.toHaveBeenCalled();
  });

  it("fails visibly for a legacy key without an exact version link", async () => {
    mocks.leftoverStoragePolicy.mockRejectedValue(new Error("Resource not found"));
    renderComponent();
    expect(
      await screen.findByText("Exact policy provenance unavailable"),
    ).toBeInTheDocument();
    expect(screen.getByText(/legacy leftover/)).toHaveTextContent(
      "rice_refrigerated",
    );
  });
});
