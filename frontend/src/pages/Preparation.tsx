import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import AppLayout from "@/components/AppLayout";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import {
  preparationApi,
  type PreparationResourceInput,
  type PreparationScheduleRequest,
  type PreparationTaskInput,
} from "@/lib/preparationApi";
import {
  AlertTriangle,
  ArrowRight,
  Clock3,
  Gauge,
  Plus,
  Trash2,
} from "lucide-react";

interface ResourceDraft {
  resourceId: string;
  label: string;
  capacity: string;
  availableFrom: string;
  availableUntil: string;
}

interface TaskDraft {
  taskId: string;
  duration: string;
  earliest: string;
  latest: string;
  priority: string;
  demands: string;
  dependencies: string;
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "The schedule could not be created";
}

function integer(
  value: string,
  label: string,
  minimum: number,
  maximum: number,
): number {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < minimum || parsed > maximum) {
    throw new Error(`${label} must be an integer from ${minimum} to ${maximum}`);
  }
  return parsed;
}

function optionalInteger(
  value: string,
  label: string,
  minimum: number,
  maximum: number,
): number | null {
  return value.trim() ? integer(value, label, minimum, maximum) : null;
}

function parseDemands(value: string): Record<string, number> {
  const result: Record<string, number> = {};
  for (const entry of value.split(/[,\n]/).map((item) => item.trim()).filter(Boolean)) {
    const [rawId, rawDemand, ...extra] = entry.split(":");
    const resourceId = rawId?.trim();
    if (!resourceId || !rawDemand?.trim() || extra.length) {
      throw new Error(`Resource demand "${entry}" must use resource_id:capacity`);
    }
    if (resourceId in result) {
      throw new Error(`Resource demand ${resourceId} is duplicated`);
    }
    result[resourceId] = integer(
      rawDemand.trim(),
      `Demand for ${resourceId}`,
      1,
      1000,
    );
  }
  return result;
}

function parseDependencies(value: string): string[] {
  const dependencies = value
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
  if (dependencies.length !== new Set(dependencies).size) {
    throw new Error("Task dependencies cannot contain duplicates");
  }
  return dependencies;
}

function demandText(value: Record<string, number>): string {
  return Object.entries(value)
    .map(([identifier, demand]) => `${identifier}:${demand}`)
    .join(", ");
}

function minuteLabel(value: number): string {
  const day = Math.floor(value / 1440) + 1;
  const withinDay = value % 1440;
  const hours = Math.floor(withinDay / 60);
  const minutes = withinDay % 60;
  return `Day ${day}, ${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
}

export default function PreparationPage() {
  const { toast } = useToast();
  const [horizon, setHorizon] = useState("1440");
  const [granularity, setGranularity] = useState("5");
  const [resources, setResources] = useState<ResourceDraft[]>([]);
  const [tasks, setTasks] = useState<TaskDraft[]>([]);

  const schedule = useMutation({
    mutationFn: () => {
      const horizonMinutes = integer(horizon, "Horizon", 1, 10080);
      const resourcePayload: PreparationResourceInput[] = resources.map(
        (value, index) => {
          const resourceId = value.resourceId.trim();
          if (!resourceId) {
            throw new Error(`Resource ${index + 1} needs an identifier`);
          }
          return {
            resource_id: resourceId,
            label: value.label.trim() || null,
            capacity: integer(
              value.capacity,
              `Capacity for ${resourceId}`,
              1,
              1000,
            ),
            available_from_minute: integer(
              value.availableFrom,
              `Start for ${resourceId}`,
              0,
              horizonMinutes,
            ),
            available_until_minute: optionalInteger(
              value.availableUntil,
              `End for ${resourceId}`,
              1,
              horizonMinutes,
            ),
          };
        },
      );
      const taskPayload: PreparationTaskInput[] = tasks.map((value, index) => {
        const taskId = value.taskId.trim();
        if (!taskId) {
          throw new Error(`Task ${index + 1} needs an identifier`);
        }
        return {
          task_id: taskId,
          duration_minutes: integer(
            value.duration,
            `Duration for ${taskId}`,
            1,
            1440,
          ),
          earliest_start_minute: integer(
            value.earliest,
            `Earliest start for ${taskId}`,
            0,
            horizonMinutes,
          ),
          latest_finish_minute: optionalInteger(
            value.latest,
            `Latest finish for ${taskId}`,
            1,
            horizonMinutes,
          ),
          priority: integer(
            value.priority,
            `Priority for ${taskId}`,
            -1000,
            1000,
          ),
          resource_demands: parseDemands(value.demands),
          dependencies: parseDependencies(value.dependencies),
          metadata: { source: "manual_user_declaration" },
        };
      });
      const payload: PreparationScheduleRequest = {
        horizon_minutes: horizonMinutes,
        granularity_minutes: integer(
          granularity,
          "Granularity",
          1,
          60,
        ),
        resources: resourcePayload,
        tasks: taskPayload,
      };
      return preparationApi.schedule(payload);
    },
    onSuccess: (value) =>
      toast({
        title: "Manual preparation schedule created",
        description: `${value.scheduled.length} scheduled; ${value.unscheduled.length} unscheduled.`,
      }),
    onError: (error) =>
      toast({
        title: "Scheduling failed",
        description: messageOf(error),
        variant: "destructive",
      }),
  });

  return (
    <AppLayout>
      <div className="mx-auto max-w-7xl space-y-6">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold">Manual preparation editor</h1>
            <p className="text-sm text-muted-foreground">
              Schedule explicitly declared tasks and resources without inferred recipe metadata.
            </p>
          </div>
          <Button asChild variant="outline">
            <Link to="/preparation/pipeline">
              Use reviewed evidence pipeline
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
        </header>

        <Alert>
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Human-declared values</AlertTitle>
          <AlertDescription>
            This editor does not verify recipe provenance. Use the reviewed pipeline for immutable evidence versions and fail-closed occurrence compilation.
          </AlertDescription>
        </Alert>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Scheduling horizon</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="prep-horizon">Horizon minutes</Label>
              <Input
                id="prep-horizon"
                type="number"
                min="1"
                max="10080"
                value={horizon}
                onChange={(event) => setHorizon(event.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="prep-granularity">Start-time granularity</Label>
              <Input
                id="prep-granularity"
                type="number"
                min="1"
                max="60"
                value={granularity}
                onChange={(event) => setGranularity(event.target.value)}
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-start justify-between gap-3">
            <div>
              <CardTitle className="text-base">Resources</CardTitle>
              <CardDescription>
                Appliances, counters, or person-specific active-work capacity.
              </CardDescription>
            </div>
            <Button
              type="button"
              variant="outline"
              onClick={() =>
                setResources((current) => [
                  ...current,
                  {
                    resourceId: "",
                    label: "",
                    capacity: "1",
                    availableFrom: "0",
                    availableUntil: "",
                  },
                ])
              }
            >
              <Plus className="mr-2 h-4 w-4" /> Add resource
            </Button>
          </CardHeader>
          <CardContent className="space-y-3">
            {resources.map((value, index) => (
              <div
                key={index}
                className="grid gap-3 rounded-md border p-3 md:grid-cols-6"
              >
                <div className="space-y-1">
                  <Label htmlFor={`resource-id-${index}`}>Resource ID</Label>
                  <Input
                    id={`resource-id-${index}`}
                    value={value.resourceId}
                    onChange={(event) =>
                      setResources((current) =>
                        current.map((item, position) =>
                          position === index
                            ? { ...item, resourceId: event.target.value }
                            : item,
                        ),
                      )
                    }
                    placeholder="oven"
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor={`resource-label-${index}`}>Label</Label>
                  <Input
                    id={`resource-label-${index}`}
                    value={value.label}
                    onChange={(event) =>
                      setResources((current) =>
                        current.map((item, position) =>
                          position === index
                            ? { ...item, label: event.target.value }
                            : item,
                        ),
                      )
                    }
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor={`resource-capacity-${index}`}>Capacity</Label>
                  <Input
                    id={`resource-capacity-${index}`}
                    type="number"
                    min="1"
                    value={value.capacity}
                    onChange={(event) =>
                      setResources((current) =>
                        current.map((item, position) =>
                          position === index
                            ? { ...item, capacity: event.target.value }
                            : item,
                        ),
                      )
                    }
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor={`resource-from-${index}`}>Available from</Label>
                  <Input
                    id={`resource-from-${index}`}
                    type="number"
                    min="0"
                    value={value.availableFrom}
                    onChange={(event) =>
                      setResources((current) =>
                        current.map((item, position) =>
                          position === index
                            ? { ...item, availableFrom: event.target.value }
                            : item,
                        ),
                      )
                    }
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor={`resource-until-${index}`}>Available until</Label>
                  <Input
                    id={`resource-until-${index}`}
                    type="number"
                    min="1"
                    value={value.availableUntil}
                    onChange={(event) =>
                      setResources((current) =>
                        current.map((item, position) =>
                          position === index
                            ? { ...item, availableUntil: event.target.value }
                            : item,
                        ),
                      )
                    }
                    placeholder="horizon"
                  />
                </div>
                <div className="flex items-end">
                  <Button
                    type="button"
                    variant="outline"
                    aria-label={`Remove resource ${index + 1}`}
                    onClick={() =>
                      setResources((current) =>
                        current.filter((_, position) => position !== index),
                      )
                    }
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-start justify-between gap-3">
            <div>
              <CardTitle className="text-base">Tasks</CardTitle>
              <CardDescription>
                Dependencies are comma-separated IDs; demands use resource_id:capacity.
              </CardDescription>
            </div>
            <Button
              type="button"
              variant="outline"
              onClick={() =>
                setTasks((current) => [
                  ...current,
                  {
                    taskId: "",
                    duration: "30",
                    earliest: "0",
                    latest: "",
                    priority: "0",
                    demands: "",
                    dependencies: "",
                  },
                ])
              }
            >
              <Plus className="mr-2 h-4 w-4" /> Add task
            </Button>
          </CardHeader>
          <CardContent className="space-y-3">
            {tasks.map((value, index) => (
              <div
                key={index}
                className="grid gap-3 rounded-md border p-3 lg:grid-cols-8"
              >
                <div className="space-y-1">
                  <Label htmlFor={`task-id-${index}`}>Task ID</Label>
                  <Input
                    id={`task-id-${index}`}
                    value={value.taskId}
                    onChange={(event) =>
                      setTasks((current) =>
                        current.map((item, position) =>
                          position === index
                            ? { ...item, taskId: event.target.value }
                            : item,
                        ),
                      )
                    }
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor={`task-duration-${index}`}>Duration</Label>
                  <Input
                    id={`task-duration-${index}`}
                    type="number"
                    min="1"
                    value={value.duration}
                    onChange={(event) =>
                      setTasks((current) =>
                        current.map((item, position) =>
                          position === index
                            ? { ...item, duration: event.target.value }
                            : item,
                        ),
                      )
                    }
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor={`task-earliest-${index}`}>Earliest start</Label>
                  <Input
                    id={`task-earliest-${index}`}
                    type="number"
                    min="0"
                    value={value.earliest}
                    onChange={(event) =>
                      setTasks((current) =>
                        current.map((item, position) =>
                          position === index
                            ? { ...item, earliest: event.target.value }
                            : item,
                        ),
                      )
                    }
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor={`task-latest-${index}`}>Latest finish</Label>
                  <Input
                    id={`task-latest-${index}`}
                    type="number"
                    min="1"
                    value={value.latest}
                    onChange={(event) =>
                      setTasks((current) =>
                        current.map((item, position) =>
                          position === index
                            ? { ...item, latest: event.target.value }
                            : item,
                        ),
                      )
                    }
                    placeholder="horizon"
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor={`task-priority-${index}`}>Priority</Label>
                  <Input
                    id={`task-priority-${index}`}
                    type="number"
                    value={value.priority}
                    onChange={(event) =>
                      setTasks((current) =>
                        current.map((item, position) =>
                          position === index
                            ? { ...item, priority: event.target.value }
                            : item,
                        ),
                      )
                    }
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor={`task-demands-${index}`}>Resource demands</Label>
                  <Input
                    id={`task-demands-${index}`}
                    value={value.demands}
                    onChange={(event) =>
                      setTasks((current) =>
                        current.map((item, position) =>
                          position === index
                            ? { ...item, demands: event.target.value }
                            : item,
                        ),
                      )
                    }
                    placeholder="oven:1"
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor={`task-dependencies-${index}`}>Dependencies</Label>
                  <Input
                    id={`task-dependencies-${index}`}
                    value={value.dependencies}
                    onChange={(event) =>
                      setTasks((current) =>
                        current.map((item, position) =>
                          position === index
                            ? { ...item, dependencies: event.target.value }
                            : item,
                        ),
                      )
                    }
                    placeholder="mix, preheat"
                  />
                </div>
                <div className="flex items-end">
                  <Button
                    type="button"
                    variant="outline"
                    aria-label={`Remove task ${index + 1}`}
                    onClick={() =>
                      setTasks((current) =>
                        current.filter((_, position) => position !== index),
                      )
                    }
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
            {tasks.length === 0 && (
              <p className="text-sm text-muted-foreground">
                Add at least one explicitly specified task.
              </p>
            )}
            <Button
              type="button"
              onClick={() => schedule.mutate()}
              disabled={tasks.length === 0 || schedule.isPending}
            >
              <Clock3 className="mr-2 h-4 w-4" /> Create manual schedule
            </Button>
          </CardContent>
        </Card>

        {schedule.error && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Schedule unavailable</AlertTitle>
            <AlertDescription>{messageOf(schedule.error)}</AlertDescription>
          </Alert>
        )}

        {schedule.data && (
          <section className="space-y-4" aria-live="polite">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Scheduled</p><p className="text-2xl font-bold">{schedule.data.scheduled.length}</p></CardContent></Card>
              <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Unscheduled</p><p className="text-2xl font-bold">{schedule.data.unscheduled.length}</p></CardContent></Card>
              <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Makespan</p><p className="text-2xl font-bold">{schedule.data.makespan_minutes} min</p></CardContent></Card>
              <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Critical path floor</p><p className="text-2xl font-bold">{String(schedule.data.diagnostics.critical_path_lower_bound_minutes ?? "—")} min</p></CardContent></Card>
            </div>

            <Card>
              <CardHeader><CardTitle className="text-base">Scheduled tasks</CardTitle></CardHeader>
              <CardContent className="space-y-2">
                {schedule.data.scheduled.map((task) => (
                  <article key={task.task_id} className="rounded-md border p-3 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2"><span className="font-medium">{task.task_id}</span><Badge variant="outline">priority {task.priority}</Badge></div>
                    <p>{minuteLabel(task.start_minute)} → {minuteLabel(task.finish_minute)} ({task.duration_minutes} min)</p>
                    <p className="text-xs text-muted-foreground">{Object.keys(task.resource_demands).length ? demandText(task.resource_demands) : "No resource demand declared"}</p>
                    {task.dependencies.length > 0 && <p className="text-xs text-muted-foreground">After: {task.dependencies.join(", ")}</p>}
                  </article>
                ))}
              </CardContent>
            </Card>

            {schedule.data.unscheduled.length > 0 && (
              <Card>
                <CardHeader><CardTitle className="text-base">Unscheduled tasks</CardTitle></CardHeader>
                <CardContent className="space-y-2">
                  {schedule.data.unscheduled.map((task) => (
                    <Alert key={task.task_id} variant="destructive">
                      <AlertTriangle className="h-4 w-4" />
                      <AlertTitle>{task.task_id}: {task.reason_code.replaceAll("_", " ")}</AlertTitle>
                      <AlertDescription>
                        {task.message}
                        {task.missing_resources.length ? ` Missing: ${task.missing_resources.join(", ")}.` : ""}
                        {task.blocked_by.length ? ` Blocked by: ${task.blocked_by.join(", ")}.` : ""}
                      </AlertDescription>
                    </Alert>
                  ))}
                </CardContent>
              </Card>
            )}

            <Card>
              <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Gauge className="h-4 w-4" /> Resource utilization</CardTitle></CardHeader>
              <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {Object.entries(schedule.data.resource_utilization).map(([resourceId, utilization]) => (
                  <div key={resourceId} className="rounded-md border p-3 text-sm">
                    <div className="flex items-center justify-between gap-2"><span className="font-medium">{resourceId}</span><Badge variant="outline">peak {schedule.data.resource_peak_usage[resourceId] ?? 0}</Badge></div>
                    <p className="text-lg font-semibold">{(utilization * 100).toFixed(1)}%</p>
                  </div>
                ))}
              </CardContent>
            </Card>
          </section>
        )}
      </div>
    </AppLayout>
  );
}
