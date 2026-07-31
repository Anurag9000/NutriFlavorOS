import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import HouseholdPage from "@/pages/Household";

const mocks = vi.hoisted(() => ({
  toast: vi.fn(),
  list: vi.fn(),
  get: vi.fn(),
  pantry: vi.fn(),
  leftovers: vi.fn(),
  reservations: vi.fn(),
  events: vi.fn(),
  invitations: vi.fn(),
  storagePolicies: vi.fn(),
  reconcileShopping: vi.fn(),
  batchPrep: vi.fn(),
  createInvitation: vi.fn(),
  revokeInvitation: vi.fn(),
  create: vi.fn(),
  acceptInvitation: vi.fn(),
  addMember: vi.fn(),
  updateMember: vi.fn(),
  addPantry: vi.fn(),
  consumePantry: vi.fn(),
  discardPantry: vi.fn(),
  adjustPantry: vi.fn(),
  addLeftover: vi.fn(),
  consumeLeftover: vi.fn(),
  generatePlan: vi.fn(),
  commitReservations: vi.fn(),
  releaseReservations: vi.fn(),
}));

vi.mock("@/components/AppLayout", () => ({
  default: ({ children }: { children: ReactNode }) => <main>{children}</main>,
}));

vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({ toast: mocks.toast }),
}));

vi.mock("@/lib/platformApi", () => ({
  evidenceApi: {
    storagePolicies: mocks.storagePolicies,
  },
  householdApi: {
    list: mocks.list,
    get: mocks.get,
    pantry: mocks.pantry,
    leftovers: mocks.leftovers,
    reservations: mocks.reservations,
    events: mocks.events,
    invitations: mocks.invitations,
    reconcileShopping: mocks.reconcileShopping,
    batchPrep: mocks.batchPrep,
    createInvitation: mocks.createInvitation,
    revokeInvitation: mocks.revokeInvitation,
    create: mocks.create,
    acceptInvitation: mocks.acceptInvitation,
    addMember: mocks.addMember,
    updateMember: mocks.updateMember,
    addPantry: mocks.addPantry,
    consumePantry: mocks.consumePantry,
    discardPantry: mocks.discardPantry,
    adjustPantry: mocks.adjustPantry,
    addLeftover: mocks.addLeftover,
    consumeLeftover: mocks.consumeLeftover,
    generatePlan: mocks.generatePlan,
    commitReservations: mocks.commitReservations,
    releaseReservations: mocks.releaseReservations,
  },
}));

const household = {
  id: "household-1",
  owner_user_id: "owner@example.test",
  name: "Home",
  timezone: "UTC",
  version: 1,
  created_at: "2026-07-31T00:00:00Z",
  updated_at: "2026-07-31T00:00:00Z",
  current_role: "owner",
};

function detail(role: "owner" | "editor" | "viewer") {
  return {
    household: { ...household, current_role: role },
    role,
    members: [],
    active_servings_multiplier: 0,
    planning_status: "ready",
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
    <QueryClientProvider client={client}>
      <HouseholdPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  mocks.list.mockResolvedValue([household]);
  mocks.get.mockResolvedValue(detail("owner"));
  mocks.pantry.mockResolvedValue([]);
  mocks.leftovers.mockResolvedValue([]);
  mocks.reservations.mockResolvedValue([]);
  mocks.events.mockResolvedValue([]);
  mocks.invitations.mockResolvedValue([]);
  mocks.storagePolicies.mockResolvedValue([]);
  mocks.reconcileShopping.mockResolvedValue([]);
  mocks.batchPrep.mockResolvedValue([]);
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: vi.fn().mockResolvedValue(undefined) },
  });
});

describe("Household workspace", () => {
  it("preserves, copies, and explicitly dismisses a one-time invitation token", async () => {
    mocks.createInvitation.mockResolvedValue({
      id: "invite-1",
      household_id: household.id,
      invited_email: "member@example.test",
      role: "viewer",
      expires_at: "2026-08-03T00:00:00Z",
      accepted_at: null,
      revoked_at: null,
      created_by_user_id: "owner@example.test",
      created_at: "2026-07-31T00:00:00Z",
      acceptance_token: "one-time-secret-token",
    });

    renderPage();
    fireEvent.click(await screen.findByRole("tab", { name: "Members" }));
    expect(await screen.findByText("Invite an account")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Invitee email"), {
      target: { value: "member@example.test" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create invite" }));

    const token = await screen.findByLabelText("One-time invitation token");
    expect(token).toHaveTextContent("one-time-secret-token");
    expect(mocks.createInvitation).toHaveBeenCalledWith(household.id, {
      email: "member@example.test",
      role: "viewer",
      expires_in_hours: 72,
    });

    fireEvent.click(screen.getByRole("button", { name: "Copy token" }));
    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
        "one-time-secret-token",
      );
    });

    fireEvent.click(screen.getByRole("button", { name: "I saved it" }));
    expect(screen.queryByLabelText("One-time invitation token")).not.toBeInTheDocument();
  });

  it("hides owner/editor mutation forms from a viewer", async () => {
    mocks.list.mockResolvedValue([{ ...household, current_role: "viewer" }]);
    mocks.get.mockResolvedValue(detail("viewer"));

    renderPage();
    expect((await screen.findAllByText("Home")).length).toBeGreaterThan(0);

    expect(screen.queryByText("Record a pantry lot")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Members" }));
    expect(screen.queryByText("Invite an account")).not.toBeInTheDocument();
    expect(screen.queryByText("Add an unlinked member")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Planning" }));
    expect(screen.getByRole("button", { name: "Generate and reserve" })).toBeDisabled();
  });
});
