import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import AppLayout from "@/components/AppLayout";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import {
  preparationApi,
  type PreparationResourceInput,
  type PreparationScheduleRequest,
  type PreparationTaskInput,
} from "@/lib/preparationApi";
import { AlertTriangle, Clock3, Gauge, Plus, Trash2 } from "lucide-react";

interface ResourceDraft {
  id: string;
  label: string;
  capacity: string;
  availableFrom: string;
  availableUntil: string;
}

interface TaskDraft {
  id: string;
  duration: string;
  earliest: string;
  latest: string;
  priority: string;
  demands: string;
}

const EMPTY_RESOURCE: ResourceDraft = {
  id: "",
  label: "",
  capacity: "1",
  availableFrom: "0",
  availableUntil: "",
};

const EMPTY_TASK: TaskDraft = {
  id: "",
  duration: "30",
  earliest: "0",
  latest: "",
  priority: "0",
  demands: "",
};

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "The schedule could not be created";
}

function integer(value: string, label: string, minimum: number, maximum: number): number {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < minimum || parsed > maximum) {
    throw new Error(`${label} must be an integer from ${minimum} to ${maximum}`);
  }
  return parsed;
}

function optionalInteger(value: string, label: string, minimum: number, maximum: number): number | null {
  return value.trim() ? integer(value, label, minimum, maximum) : null;
}

function parseDemands(value: string): Record<string, number> {
  const result: Record<string, number> = {};
  const entries = value
    .split(/[,\n]/)
    .map((entry) => entry.trim())
    .filter(Boolean);
  for (const entry of entries) {
    const [rawId, rawDemand, ...extra] = entry.split(":");
    const resourceId = rawId?.trim();
    if (!resourceId || !rawDemand?.trim() || extra.length) {
      throw new Error(`Resource demand "${entry}" must use resource_id:capacity`);
    }
    if (resourceId in result) throw new Error(`Resource demand ${resourceId} is duplicated`);
    result[resourceId] = integer(rawDemand.trim(), `Demand for ${resourceId}`, 1, 1000);
  }
  return result;
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
      const granularityMinutes = integer(granularity, "Granularity", 1, 60);
      const resourcePayload: PreparationResourceInput[] = resources.map((resource, index) => {
        const resourceId = resource.id.trim();
        if (!resourceId) throw new Error(`Resource ${index + 1} needs an identifier`);
        return {
          resource_id: resourceId,
          label: resource.label.trim() || null,
          capacity: integer(resource.capacity, `Capacity for ${resourceId}`, 1, 1000),
          available_from_minute: integer(resource.availableFrom, `Start for ${resourceId}`, 0, 10080),
          available_until_minute: optionalInteger(resource.availableUntil, `End for ${resourceId}`, 1, 10080),
        };
      });
      const taskPayload: PreparationTaskInput[] = tasks.map((task, index) => {
        const taskId = task.id.trim();
        if (!taskId) throw new Error(`Task ${index + 1} needs an identifier`);
        return {
          task_id: taskId,
          duration_minutes: integer(task.duration, `Duration for ${taskId}`, 1, 1440),
          earliest_start_minute: integer(task.earliest, `Earliest start for ${taskId}`, 0, 10080),
          latest_finish_minute: optionalInteger(task.latest, `Latest finish for ${taskId}`, 1, 10080),
          priority: integer(task.priority, `Priority for ${taskId}`, -1000, 1000),
          resource_demands: parseDemands(task.demands),
          metadata: {},
        };
      });
      const payload: PreparationScheduleRequest = {
        horizon_minutes: horizonMinutes,
        granularity_minutes: granularityMinutes,
        resources: resourcePayload,
        tasks: taskPayload,
      };
      return preparationApi.schedule(payload);
    },
    onSuccess: (value) => toast({
      title: "Preparation schedule created",
      description: `${value.scheduled.length} scheduled; ${value.unscheduled.length} unscheduled.`,
    }),
    onError: (error) => toast({
      title: "Scheduling failed",
      description: messageOf(error),
      variant: "destructive",
    }),
  });

  const updateResource = (index: number, patch: Partial<ResourceDraft>) => {
    setResources((current) => current.map((value, position) => position === index ? { ...value, ...patch } : value));
  };
  const updateTask = (index: number, patch: Partial<TaskDraft>) => {
    setTasks((current) => current.map((value, position) => position === index ? { ...value, ...patch } : value));
  };

  return (
    <AppLayout>
      <div className="mx-auto max-w-6xl space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Preparation resources</h1>
          <p className="text-sm text-muted-foreground">
            Deterministic scheduling for explicitly declared durations, appliance capacities, and availability windows.
          </p>
        </div>

        <Alert>
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>No inferred cooking metadata</AlertTitle>
          <AlertDescription>
            Enter durations and resource demands from reviewed recipe data or human planning. The scheduler does not infer appliances, timings, food-safety windows, or unattended-cooking suitability.
          </AlertDescription>
        </Alert>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Scheduling horizon</CardTitle>
            <CardDescription>Minutes are measured from the start of the planning horizon.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1"><Label htmlFor="prep-horizon">Horizon minutes</Label><Input id="prep-horizon" type="number" min="1" max="10080" value={horizon} onChange={(event) => setHorizon(event.target.value)} /></div>
            <div className="space-y-1"><Label htmlFor="prep-granularity">Start-time granularity</Label><Input id="prep-granularity" type="number" min="1" max="60" value={granularity} onChange={(event) => setGranularity(event.target.value)} /></div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-start justify-between gap-3">
            <div><CardTitle className="text-base">Resources</CardTitle><CardDescription>Examples include oven, burner, blender, prep-counter, or a person-specific work capacity.</CardDescription></div>
            <Button type="button" variant="outline" onClick={() => setResources((current) => [...current, { ...EMPTY_RESOURCE }])}><Plus className="mr-2 h-4 w-4" />Add resource</Button>
          </CardHeader>
          <CardContent className="space-y-3">
            {resources.map((resource, index) => (
              <div key={index} className="grid gap-3 rounded-md border p-3 md:grid-cols-6">
                <div className="space-y-1"><Label htmlFor={`resource-id-${index}`}>Resource ID</Label><Input id={`resource-id-${index}`} value={resource.id} onChange={(event) => updateResource(index, { id: event.target.value })} placeholder="oven" /></div>
                <div className="space-y-1"><Label htmlFor={`resource-label-${index}`}>Label</Label><Input id={`resource-label-${index}`} value={resource.label} onChange={(event) => updateResource(index, { label: event.target.value })} /></div>
                <div className="space-y-1"><Label htmlFor={`resource-capacity-${index}`}>Capacity</Label><Input id={`resource-capacity-${index}`} type="number" min="1" value={resource.capacity} onChange={(event) => updateResource(index, { capacity: event.target.value })} /></div>
                <div className="space-y-1"><Label htmlFor={`resource-from-${index}`}>Available from</Label><Input id={`resource-from-${index}`} type="number" min="0" value={resource.availableFrom} onChange={(event) => updateResource(index, { availableFrom: event.target.value })} /></div>
                <div className="space-y-1"><Label htmlFor={`resource-until-${index}`}>Available until</Label><Input id={`resource-until-${index}`} type="number" min="1" value={resource.availableUntil} onChange={(event) => updateResource(index, { availableUntil: event.target.value })} placeholder="horizon" /></div>
                <div className="flex items-end"><Button type="button" variant="outline" aria-label={`Remove resource ${index + 1}`} onClick={() => setResources((current) => current.filter((_, position) => position !== index))}><Trash2 className="h-4 w-4" /></Button></div>
              </div>
            ))}
            {resources.length === 0 && <p className="text-sm text-muted-foreground">No resources declared. Tasks without resource demands can still be scheduled.</p>}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-start justify-between gap-3">
            <div><CardTitle className="text-base">Preparation tasks</CardTitle><CardDescription>Resource demands use comma-separated resource_id:capacity pairs.</CardDescription></div>
            <Button type="button" variant="outline" onClick={() => setTasks((current) => [...current, { ...EMPTY_TASK }])}><Plus className="mr-2 h-4 w-4" />Add task</Button>
          </CardHeader>
          <CardContent className="space-y-3">
            {tasks.map((task, index) => (
              <div key={index} className="grid gap-3 rounded-md border p-3 md:grid-cols-7">
                <div className="space-y-1"><Label htmlFor={`task-id-${index}`}>Task ID</Label><Input id={`task-id-${index}`} value={task.id} onChange={(event) => updateTask(index, { id: event.target.value })} /></div>
                <div className="space-y-1"><Label htmlFor={`task-duration-${index}`}>Duration</Label><Input id={`task-duration-${index}`} type="number" min="1" value={task.duration} onChange={(event) => updateTask(index, { duration: event.target.value })} /></div>
                <div className="space-y-1"><Label htmlFor={`task-earliest-${index}`}>Earliest start</Label><Input id={`task-earliest-${index}`} type="number" min="0" value={task.earliest} onChange={(event) => updateTask(index, { earliest: event.target.value })} /></div>
                <div className="space-y-1"><Label htmlFor={`task-latest-${index}`}>Latest finish</Label><Input id={`task-latest-${index}`} type="number" min="1" value={task.latest} onChange={(event) => updateTask(index, { latest: event.target.value })} placeholder="horizon" /></div>
                <div className="space-y-1"><Label htmlFor={`task-priority-${index}`}>Priority</Label><Input id={`task-priority-${index}`} type="number" value={task.priority} onChange={(event) => updateTask(index, { priority: event.target.value })} /></div>
                <div className="space-y-1"><Label htmlFor={`task-demands-${index}`}>Resource demands</Label><Input id={`task-demands-${index}`} value={task.demands} onChange={(event) => updateTask(index, { demands: event.target.value })} placeholder="oven:1, counter:1" /></div>
                <div className="flex items-end"><Button type="button" variant="outline" aria-label={`Remove task ${index + 1}`} onClick={() => setTasks((current) => current.filter((_, position) => position !== index))}><Trash2 className="h-4 w-4" /></Button></div>
              </div>
            ))}
            {tasks.length === 0 && <p className="text-sm text-muted-foreground">Add at least one explicitly specified task.</p>}
            <Button type="button" onClick={() => schedule.mutate()} disabled={tasks.length === 0 || schedule.isPending}><Clock3 className="mr-2 h-4 w-4" />Create schedule</Button>
          </CardContent>
        </Card>

        {schedule.error && <Alert variant="destructive"><AlertTriangle className="h-4 w-4" /><AlertTitle>Schedule unavailable</AlertTitle><AlertDescription>{messageOf(schedule.error)}</AlertDescription></Alert>}

        {schedule.data && (
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Scheduled</p><p className="text-2xl font-bold">{schedule.data.scheduled.length}</p></CardContent></Card>
              <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Unscheduled</p><p className="text-2xl font-bold">{schedule.data.unscheduled.length}</p></CardContent></Card>
              <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Makespan</p><p className="text-2xl font-bold">{schedule.data.makespan_minutes} min</p></CardContent></Card>
              <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Method</p><p className="text-sm font-medium break-words">{schedule.data.method}</p></CardContent></Card>
            </div>

            <Card>
              <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Clock3 className="h-4 w-4" />Scheduled tasks</CardTitle></CardHeader>
              <CardContent className="space-y-2">
                {schedule.data.scheduled.map((task) => <div key={task.task_id} className="rounded-md border p-3 text-sm"><div className="flex flex-wrap items-center justify-between gap-2"><span className="font-medium">{task.task_id}</span><Badge variant="outline">priority {task.priority}</Badge></div><p>{minuteLabel(task.start_minute)} → {minuteLabel(task.finish_minute)} ({task.duration_minutes} min)</p><p className="text-xs text-muted-foreground">{Object.keys(task.resource_demands).length ? Object.entries(task.resource_demands).map(([id, demand]) => `${id}:${demand}`).join(", ") : "No resource demand declared"}</p></div>)}
                {schedule.data.scheduled.length === 0 && <p className="text-sm text-muted-foreground">No task could be scheduled.</p>}
              </CardContent>
            </Card>

            {schedule.data.unscheduled.length > 0 && <Card><CardHeader><CardTitle className="text-base">Unscheduled tasks</CardTitle></CardHeader><CardContent className="space-y-2">{schedule.data.unscheduled.map((task) => <Alert key={task.task_id} variant="destructive"><AlertTriangle className="h-4 w-4" /><AlertTitle>{task.task_id}: {task.reason_code.replaceAll("_", " ")}</AlertTitle><AlertDescription>{task.message}{task.missing_resources.length ? ` Missing: ${task.missing_resources.join(", ")}.` : ""}</AlertDescription></Alert>)}</CardContent></Card>}

            <Card>
              <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Gauge className="h-4 w-4" />Resource utilization</CardTitle></CardHeader>
              <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {Object.entries(schedule.data.resource_utilization).map(([resourceId, utilization]) => <div key={resourceId} className="rounded-md border p-3 text-sm"><div className="flex items-center justify-between gap-2"><span className="font-medium">{resourceId}</span><Badge variant="outline">peak {schedule.data.resource_peak_usage[resourceId] ?? 0}</Badge></div><p className="text-lg font-semibold">{(utilization * 100).toFixed(1)}%</p></div>)}
                {Object.keys(schedule.data.resource_utilization).length === 0 && <p className="text-sm text-muted-foreground">No resource utilization exists because no capacities were declared.</p>}
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
