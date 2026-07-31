import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
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
    <MemoryRouter>
      <QueryClientProvider client={client}>
        <PreparationPage />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("Manual preparation editor", () => {
  it("builds an explicit dependency-aware schedule request", async () => {
    mocks.schedule.mockResolvedValue({
      method: "deterministic_dependency_aware_resource_scheduler_v2",
      deterministic: true,
      horizon_minutes: 120,
      granularity_minutes: 5,
      scheduled: [
        {
          task_id: "bake",
          start_minute: 30,
          finish_minute: 60,
          duration_minutes: 30,
          priority: 2,
          resource_demands: { oven: 1 },
          dependencies: ["mix"],
          metadata: { source: "manual_user_declaration" },
        },
      ],
      unscheduled: [],
      resource_utilization: { oven: 0.25 },
      resource_peak_usage: { oven: 1 },
      makespan_minutes: 60,
      diagnostics: {
        scheduled_count: 1,
        critical_path_lower_bound_minutes: 60,
      },
    });

    renderPage();
    expect(
      screen.getByRole("link", { name: /Use reviewed evidence pipeline/ }),
    ).toHaveAttribute("href", "/preparation/pipeline");
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
    fireEvent.change(screen.getByLabelText("Dependencies"), {
      target: { value: "mix" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Create manual schedule" }),
    );

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
          dependencies: ["mix"],
          metadata: { source: "manual_user_declaration" },
        },
      ],
    });
    expect(screen.getByText("25.0%")).toBeInTheDocument();
    expect(screen.getByText("After: mix")).toBeInTheDocument();
  });

  it("renders blocked dependencies and missing resources explicitly", async () => {
    mocks.schedule.mockResolvedValue({
      method: "deterministic_dependency_aware_resource_scheduler_v2",
      deterministic: true,
      horizon_minutes: 60,
      granularity_minutes: 5,
      scheduled: [],
      unscheduled: [
        {
          task_id: "pack",
          reason_code: "blocked_by_dependency",
          message: "A prerequisite task was not scheduled",
          missing_resources: [],
          blocked_by: ["freeze"],
          capacity_violations: {},
          metadata: { source: "manual_user_declaration" },
        },
      ],
      resource_utilization: {},
      resource_peak_usage: {},
      makespan_minutes: 0,
      diagnostics: {
        unscheduled_count: 1,
        critical_path_lower_bound_minutes: 30,
      },
    });

    renderPage();
    fireEvent.change(screen.getByLabelText("Horizon minutes"), {
      target: { value: "60" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add task" }));
    fireEvent.change(screen.getByLabelText("Task ID"), {
      target: { value: "pack" },
    });
    fireEvent.change(screen.getByLabelText("Dependencies"), {
      target: { value: "freeze" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Create manual schedule" }),
    );

    expect(
      await screen.findByText(/pack: blocked by dependency/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/Blocked by: freeze/)).toBeInTheDocument();
  });
});
