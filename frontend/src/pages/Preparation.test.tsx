import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PreparationPage from "@/pages/Preparation";

const mocks = vi.hoisted(() => ({
  schedule: vi.fn(),
  toast: vi.fn(),
}));

vi.mock("@/components/AppLayout", () => ({
  default: ({ children }: { children: ReactNode }) => <main>{children}</main>,
}));

vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({ toast: mocks.toast }),
}));

vi.mock("@/lib/preparationApi", () => ({
  preparationApi: { schedule: mocks.schedule },
}));

function renderPage() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={client}>
      <PreparationPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("Preparation workspace", () => {
  it("builds an explicit typed resource schedule request", async () => {
    mocks.schedule.mockResolvedValue({
      method: "deterministic_earliest_feasible_resource_scheduler_v1",
      deterministic: true,
      horizon_minutes: 120,
      granularity_minutes: 5,
      scheduled: [
        {
          task_id: "bake",
          start_minute: 0,
          finish_minute: 30,
          duration_minutes: 30,
          priority: 2,
          resource_demands: { oven: 1 },
          metadata: {},
        },
      ],
      unscheduled: [],
      resource_utilization: { oven: 0.25 },
      resource_peak_usage: { oven: 1 },
      makespan_minutes: 30,
      diagnostics: { scheduled_count: 1 },
    });

    renderPage();
    fireEvent.change(screen.getByLabelText("Horizon minutes"), {
      target: { value: "120" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add resource" }));
    fireEvent.change(screen.getByLabelText("Resource ID"), {
      target: { value: "oven" },
    });
    fireEvent.change(screen.getByLabelText("Available until"), {
      target: { value: "120" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Add task" }));
    fireEvent.change(screen.getByLabelText("Task ID"), {
      target: { value: "bake" },
    });
    fireEvent.change(screen.getByLabelText("Duration"), {
      target: { value: "30" },
    });
    fireEvent.change(screen.getByLabelText("Latest finish"), {
      target: { value: "60" },
    });
    fireEvent.change(screen.getByLabelText("Priority"), {
      target: { value: "2" },
    });
    fireEvent.change(screen.getByLabelText("Resource demands"), {
      target: { value: "oven:1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create schedule" }));

    expect(await screen.findByText("bake")).toBeInTheDocument();
    expect(mocks.schedule).toHaveBeenCalledWith({
      horizon_minutes: 120,
      granularity_minutes: 5,
      resources: [
        {
          resource_id: "oven",
          label: null,
          capacity: 1,
          available_from_minute: 0,
          available_until_minute: 120,
        },
      ],
      tasks: [
        {
          task_id: "bake",
          duration_minutes: 30,
          earliest_start_minute: 0,
          latest_finish_minute: 60,
          priority: 2,
          resource_demands: { oven: 1 },
          metadata: {},
        },
      ],
    });
    expect(screen.getByText("25.0%")).toBeInTheDocument();
  });

  it("renders explicit unscheduled reasons without inventing a fallback", async () => {
    mocks.schedule.mockResolvedValue({
      method: "deterministic_earliest_feasible_resource_scheduler_v1",
      deterministic: true,
      horizon_minutes: 60,
      granularity_minutes: 5,
      scheduled: [],
      unscheduled: [
        {
          task_id: "freeze",
          reason_code: "missing_resource",
          message: "One or more declared resources are not present",
          missing_resources: ["freezer"],
          capacity_violations: {},
          metadata: {},
        },
      ],
      resource_utilization: {},
      resource_peak_usage: {},
      makespan_minutes: 0,
      diagnostics: { unscheduled_count: 1 },
    });

    renderPage();
    fireEvent.change(screen.getByLabelText("Horizon minutes"), {
      target: { value: "60" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add task" }));
    fireEvent.change(screen.getByLabelText("Task ID"), {
      target: { value: "freeze" },
    });
    fireEvent.change(screen.getByLabelText("Resource demands"), {
      target: { value: "freezer:1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create schedule" }));

    expect(await screen.findByText(/freeze: missing resource/i)).toBeInTheDocument();
    expect(screen.getByText(/Missing: freezer/)).toBeInTheDocument();
    expect(screen.getByText("No task could be scheduled.")).toBeInTheDocument();
  });
});
