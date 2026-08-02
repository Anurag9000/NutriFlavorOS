import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeftRight,
  CheckCircle2,
  FileWarning,
  LockKeyhole,
  ShieldAlert,
  Wrench,
} from "lucide-react";
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
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { householdApi } from "@/lib/platformApi";
import {
  preparationOperationsApi,
  type PersistedPreparationScheduleView,
  type PreparationScheduleRequest,
  type ScheduledPreparationTask,
} from "@/lib/preparationOperationsApi";
import {
  preparationRepairApi,
  type PreparationRepairStrategy,
  type PreparationScheduleRepairResult,
} from "@/lib/preparationRepairApi";

function messageOf(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "The repair request could not be completed";
}

function shortHash(value?: string | null): string {
  if (!value) return "not recorded";
  return value.length <= 22
    ? value
    : `${value.slice(0, 12)}…${value.slice(-6)}`;
}

function parseRevisedRequest(raw: string): PreparationScheduleRequest {
  const value = JSON.parse(raw) as unknown;
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("Revised request must be a JSON object");
  }
  const candidate = value as Partial<PreparationScheduleRequest>;
  if (!Number.isInteger(candidate.horizon_minutes) || !candidate.horizon_minutes) {
    throw new Error("Revised request requires a positive integer horizon_minutes");
  }
  if (!Number.isInteger(candidate.granularity_minutes) || !candidate.granularity_minutes) {
    throw new Error("Revised request requires a positive integer granularity_minutes");
  }
  if (!Array.isArray(candidate.resources) || !Array.isArray(candidate.tasks)) {
    throw new Error("Revised request requires resources and tasks arrays");
  }
  return candidate as PreparationScheduleRequest;
}

function taskMap(tasks: ScheduledPreparationTask[]): Map<string, ScheduledPreparationTask> {
  return new Map(tasks.map((task) => [task.task_id, task]));
}

function outcomeFor(
  taskId: string,
  result: PreparationScheduleRepairResult,
): string {
  if (result.preserved_task_ids.includes(taskId)) return "preserved";
  if (result.moved_tasks.some((movement) => movement.task_id === taskId)) {
    return "moved";
  }
  if (result.added_task_ids.includes(taskId)) return "added";
  if (result.removed_task_ids.includes(taskId)) return "removed";
  if (result.unscheduled_task_ids.includes(taskId)) return "unscheduled";
  return "changed";
}

function selectedScheduleRequest(
  schedule?: PersistedPreparationScheduleView,
): PreparationScheduleRequest | null {
  return schedule?.schedule_request ?? null;
}

export default function PreparationRepairReviewPage() {
  const [householdId, setHouseholdId] = useState("");
  const [scheduleId, setScheduleId] = useState("");
  const [revisedRequestRaw, setRevisedRequestRaw] = useState("");
  const [immutableTaskIds, setImmutableTaskIds] = useState<string[]>([]);
  const [strategy, setStrategy] = useState<PreparationRepairStrategy>(
    "greedy_min_change",
  );
  const [allowPartial, setAllowPartial] = useState(false);
  const [result, setResult] = useState<PreparationScheduleRepairResult | null>(
    null,
  );
  const [reviewedChanges, setReviewedChanges] = useState(false);
  const [understandsBoundary, setUnderstandsBoundary] = useState(false);

  const householdsQ = useQuery({
    queryKey: ["households"],
    queryFn: householdApi.list,
  });
  const households = householdsQ.data ?? [];
  const activeHouseholdId = householdId || households[0]?.id || "";

  const schedulesQ = useQuery({
    queryKey: ["preparation-operations", activeHouseholdId, "repair-schedules"],
    queryFn: () =>
      preparationOperationsApi.schedules(activeHouseholdId, [
        "draft",
        "approved",
      ]),
    enabled: Boolean(activeHouseholdId),
  });
  const schedules = useMemo(
    () =>
      (schedulesQ.data ?? []).filter(
        (schedule) =>
          schedule.replay_status === "replayable" &&
          schedule.schedule_request !== null &&
          schedule.schedule.unscheduled.length === 0,
      ),
    [schedulesQ.data],
  );
  const activeScheduleId = Number(scheduleId) || schedules[0]?.id || 0;
  const selectedSchedule = schedules.find(
    (schedule) => schedule.id === activeScheduleId,
  );
  const previousRequest = selectedScheduleRequest(selectedSchedule);

  useEffect(() => {
    setScheduleId("");
    setResult(null);
    setImmutableTaskIds([]);
    setReviewedChanges(false);
    setUnderstandsBoundary(false);
  }, [activeHouseholdId]);

  useEffect(() => {
    if (!previousRequest) {
      setRevisedRequestRaw("");
      setResult(null);
      setImmutableTaskIds([]);
      return;
    }
    setRevisedRequestRaw(JSON.stringify(previousRequest, null, 2));
    setResult(null);
    setImmutableTaskIds([]);
    setReviewedChanges(false);
    setUnderstandsBoundary(false);
  }, [activeScheduleId, previousRequest]);

  const repairMutation = useMutation({
    mutationFn: async () => {
      if (!selectedSchedule || !previousRequest) {
        throw new Error("Select a replayable draft or approved schedule");
      }
      const revisedRequest = parseRevisedRequest(revisedRequestRaw);
      return preparationRepairApi.repair({
        previous_request: previousRequest,
        previous_response: selectedSchedule.schedule,
        revised_request: revisedRequest,
        immutable_task_ids: immutableTaskIds,
        strategy,
        allow_partial: allowPartial,
      });
    },
    onSuccess: (value) => {
      setResult(value);
      setReviewedChanges(false);
      setUnderstandsBoundary(false);
    },
    onError: () => setResult(null),
  });

  const previousTasks = selectedSchedule?.schedule.scheduled ?? [];
  const previousById = useMemo(() => taskMap(previousTasks), [previousTasks]);
  const repairedById = useMemo(
    () => taskMap(result?.response.scheduled ?? []),
    [result],
  );
  const comparisonTaskIds = useMemo(
    () =>
      Array.from(
        new Set([
          ...previousById.keys(),
          ...repairedById.keys(),
          ...(result?.unscheduled_task_ids ?? []),
        ]),
      ).sort((left, right) => {
        const leftTask = repairedById.get(left) ?? previousById.get(left);
        const rightTask = repairedById.get(right) ?? previousById.get(right);
        return (
          (leftTask?.start_minute ?? Number.MAX_SAFE_INTEGER) -
            (rightTask?.start_minute ?? Number.MAX_SAFE_INTEGER) ||
          left.localeCompare(right)
        );
      }),
    [previousById, repairedById, result],
  );

  const pageError =
    householdsQ.error ?? schedulesQ.error ?? repairMutation.error ?? null;
  const hasReviewableChanges = Boolean(
    result &&
      (result.moved_tasks.length ||
        result.added_task_ids.length ||
        result.removed_task_ids.length ||
        result.unscheduled_task_ids.length),
  );

  const toggleImmutable = (taskId: string) => {
    setImmutableTaskIds((current) =>
      current.includes(taskId)
        ? current.filter((value) => value !== taskId)
        : [...current, taskId].sort(),
    );
    setResult(null);
  };

  return (
    <AppLayout>
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-primary">Preparation operations</p>
            <h1 className="text-3xl font-semibold tracking-tight">
              Advisory schedule repair
            </h1>
            <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
              Compare a complete persisted schedule with a deterministic
              minimal-change candidate. Computing a candidate never accepts,
              replaces, approves, persists, or executes it.
            </p>
          </div>
          <Button asChild variant="outline">
            <Link to="/preparation/operations">
              <ArrowLeftRight className="mr-2 h-4 w-4" />
              Operations workspace
            </Link>
          </Button>
        </div>

        <Alert>
          <ShieldAlert className="h-4 w-4" />
          <AlertTitle>Human review boundary</AlertTitle>
          <AlertDescription>
            This workspace calls a computation-only endpoint. It cannot persist
            a repaired draft, approve a schedule, create task events, infer
            execution, or make a food-safety decision.
          </AlertDescription>
        </Alert>

        {pageError && (
          <Alert variant="destructive" role="alert">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Repair workspace unavailable</AlertTitle>
            <AlertDescription>{messageOf(pageError)}</AlertDescription>
          </Alert>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Source schedule</CardTitle>
            <CardDescription>
              Only replayable, complete draft or approved schedules are offered.
              Completed work is not yet modeled as an immutable execution-aware
              repair input.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="repair-household">Household</Label>
              <select
                id="repair-household"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={activeHouseholdId}
                onChange={(event) => setHouseholdId(event.target.value)}
              >
                {households.map((household) => (
                  <option key={household.id} value={household.id}>
                    {household.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="repair-schedule">Schedule</Label>
              <select
                id="repair-schedule"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={activeScheduleId || ""}
                onChange={(event) => setScheduleId(event.target.value)}
              >
                {schedules.map((schedule) => (
                  <option key={schedule.id} value={schedule.id}>
                    #{schedule.id} · {schedule.status} · version {schedule.version}
                  </option>
                ))}
              </select>
            </div>
            {selectedSchedule && (
              <div className="md:col-span-2 flex flex-wrap gap-2">
                <Badge className="capitalize">{selectedSchedule.status}</Badge>
                <Badge variant="outline">version {selectedSchedule.version}</Badge>
                <Badge variant="outline">
                  {selectedSchedule.schedule.scheduled.length} tasks
                </Badge>
                <Badge variant="outline">
                  schedule {shortHash(selectedSchedule.schedule_hash)}
                </Badge>
                <Badge variant="outline">
                  request {shortHash(selectedSchedule.schedule_request_hash)}
                </Badge>
              </div>
            )}
          </CardContent>
        </Card>

        {!schedulesQ.isLoading && schedules.length === 0 && activeHouseholdId && (
          <Alert>
            <FileWarning className="h-4 w-4" />
            <AlertTitle>No repairable schedule</AlertTitle>
            <AlertDescription>
              Persist a complete replayable draft or approved preparation
              schedule before computing a repair candidate.
            </AlertDescription>
          </Alert>
        )}

        {selectedSchedule && previousRequest && (
          <form
            className="space-y-6"
            onSubmit={(event) => {
              event.preventDefault();
              repairMutation.mutate();
            }}
          >
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Revised scheduling problem</CardTitle>
                <CardDescription>
                  The exact previous request is preloaded. Edit only explicit
                  tasks, dependencies, deadlines, resources, capacities, or
                  availability windows. Server validation remains authoritative.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-1">
                  <Label htmlFor="repair-request">Strict revised request JSON</Label>
                  <Textarea
                    id="repair-request"
                    className="min-h-[22rem] font-mono text-xs"
                    value={revisedRequestRaw}
                    aria-describedby="repair-request-help"
                    onChange={(event) => {
                      setRevisedRequestRaw(event.target.value);
                      setResult(null);
                    }}
                  />
                  <p id="repair-request-help" className="text-xs text-muted-foreground">
                    Unknown fields and malformed scheduling contracts fail closed.
                  </p>
                </div>

                <fieldset className="space-y-3 rounded-md border p-4">
                  <legend className="px-1 text-sm font-medium">
                    Immutable tasks
                  </legend>
                  <p className="text-xs text-muted-foreground">
                    Immutable tasks retain their exact prior placement and
                    operational signature. Every predecessor in their dependency
                    closure must also be pinned.
                  </p>
                  <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                    {previousTasks.map((task) => (
                      <label
                        key={task.task_id}
                        className="flex items-start gap-2 rounded-md border p-3 text-sm"
                      >
                        <input
                          type="checkbox"
                          className="mt-1 h-4 w-4"
                          checked={immutableTaskIds.includes(task.task_id)}
                          onChange={() => toggleImmutable(task.task_id)}
                        />
                        <span>
                          <span className="block font-medium">{task.task_id}</span>
                          <span className="text-xs text-muted-foreground">
                            minute {task.start_minute}–{task.finish_minute}
                          </span>
                        </span>
                      </label>
                    ))}
                  </div>
                </fieldset>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-1">
                    <Label htmlFor="repair-strategy">Repair strategy</Label>
                    <select
                      id="repair-strategy"
                      className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                      value={strategy}
                      onChange={(event) => {
                        setStrategy(
                          event.target.value as PreparationRepairStrategy,
                        );
                        setResult(null);
                      }}
                    >
                      <option value="greedy_min_change">
                        Greedy preservation-first
                      </option>
                      <option value="bounded_exact_min_change">
                        Bounded exact comparator
                      </option>
                    </select>
                  </div>
                  <label className="flex items-start gap-3 rounded-md border p-4 text-sm">
                    <input
                      type="checkbox"
                      className="mt-1 h-4 w-4"
                      checked={allowPartial}
                      onChange={(event) => {
                        setAllowPartial(event.target.checked);
                        setResult(null);
                      }}
                    />
                    <span>
                      <span className="block font-medium">Allow partial output</span>
                      <span className="text-xs text-muted-foreground">
                        Unresolved tasks remain explicit and the result is not a
                        complete executable schedule.
                      </span>
                    </span>
                  </label>
                </div>

                <Button type="submit" disabled={repairMutation.isPending}>
                  <Wrench className="mr-2 h-4 w-4" />
                  {repairMutation.isPending
                    ? "Computing repair…"
                    : "Compute advisory repair"}
                </Button>
              </CardContent>
            </Card>
          </form>
        )}

        {result && (
          <section className="space-y-6" aria-labelledby="repair-result-heading">
            <Alert variant={result.complete ? "default" : "destructive"}>
              {result.complete ? (
                <CheckCircle2 className="h-4 w-4" />
              ) : (
                <AlertTriangle className="h-4 w-4" />
              )}
              <AlertTitle id="repair-result-heading">
                {result.complete
                  ? "Complete advisory candidate"
                  : "Partial advisory candidate"}
              </AlertTitle>
              <AlertDescription>
                Human acceptance required: {String(result.requires_human_acceptance)}.
                Accepted: {String(result.accepted)}. Persistence performed: {String(result.persistence_performed)}.
              </AlertDescription>
            </Alert>

            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5" aria-live="polite">
              {[
                ["Preserved", result.preserved_task_ids.length],
                ["Moved", result.moved_tasks.length],
                ["Added", result.added_task_ids.length],
                ["Removed", result.removed_task_ids.length],
                ["Unscheduled", result.unscheduled_task_ids.length],
              ].map(([label, value]) => (
                <Card key={label}>
                  <CardContent className="p-4">
                    <p className="text-xs text-muted-foreground">{label}</p>
                    <p className="text-2xl font-semibold">{value}</p>
                  </CardContent>
                </Card>
              ))}
            </div>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Objective and provenance</CardTitle>
                <CardDescription>
                  Deterministic diagnostics are evidence about this computation,
                  not proof of global optimality or execution.
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
                <div className="rounded-md border p-3">
                  <p className="text-xs text-muted-foreground">Changed tasks</p>
                  <p className="font-semibold">{result.objective.changed_task_count}</p>
                </div>
                <div className="rounded-md border p-3">
                  <p className="text-xs text-muted-foreground">Total displacement</p>
                  <p className="font-semibold">
                    {result.objective.total_displacement_minutes} minutes
                  </p>
                </div>
                <div className="rounded-md border p-3">
                  <p className="text-xs text-muted-foreground">Makespan</p>
                  <p className="font-semibold">
                    {result.objective.makespan_minutes} minutes
                  </p>
                </div>
                <div className="rounded-md border p-3">
                  <p className="text-xs text-muted-foreground">Strategy</p>
                  <p className="font-semibold capitalize">
                    {result.diagnostics.strategy.replaceAll("_", " ")}
                  </p>
                </div>
                <div className="rounded-md border p-3 md:col-span-2">
                  <p className="text-xs text-muted-foreground">Previous hash</p>
                  <code className="break-all text-xs">{result.previous_schedule_hash}</code>
                </div>
                <div className="rounded-md border p-3 md:col-span-2">
                  <p className="text-xs text-muted-foreground">Repaired hash</p>
                  <code className="break-all text-xs">{result.repaired_response_hash}</code>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Task-by-task change ledger</CardTitle>
                <CardDescription>
                  Previous and candidate placements remain visible together.
                </CardDescription>
              </CardHeader>
              <CardContent className="overflow-x-auto">
                <table className="w-full min-w-[760px] border-collapse text-left text-sm">
                  <caption className="sr-only">
                    Previous and repaired preparation task placements
                  </caption>
                  <thead>
                    <tr className="border-b">
                      <th scope="col" className="p-2">Task</th>
                      <th scope="col" className="p-2">Outcome</th>
                      <th scope="col" className="p-2">Previous</th>
                      <th scope="col" className="p-2">Candidate</th>
                      <th scope="col" className="p-2">Displacement</th>
                      <th scope="col" className="p-2">Resources</th>
                    </tr>
                  </thead>
                  <tbody>
                    {comparisonTaskIds.map((taskId) => {
                      const previous = previousById.get(taskId);
                      const repaired = repairedById.get(taskId);
                      const movement = result.moved_tasks.find(
                        (value) => value.task_id === taskId,
                      );
                      const outcome = outcomeFor(taskId, result);
                      return (
                        <tr key={taskId} className="border-b align-top">
                          <th scope="row" className="p-2 font-medium">
                            {taskId}
                            {result.immutable_task_ids.includes(taskId) && (
                              <LockKeyhole
                                className="ml-2 inline h-3.5 w-3.5"
                                aria-label="Immutable"
                              />
                            )}
                          </th>
                          <td className="p-2">
                            <Badge variant={outcome === "unscheduled" ? "destructive" : "outline"} className="capitalize">
                              {outcome}
                            </Badge>
                          </td>
                          <td className="p-2">
                            {previous
                              ? `${previous.start_minute}–${previous.finish_minute}`
                              : "not present"}
                          </td>
                          <td className="p-2">
                            {repaired
                              ? `${repaired.start_minute}–${repaired.finish_minute}`
                              : outcome === "unscheduled"
                                ? "unresolved"
                                : "not present"}
                          </td>
                          <td className="p-2">
                            {movement
                              ? `${movement.displacement_minutes >= 0 ? "+" : ""}${movement.displacement_minutes} min`
                              : "0 min"}
                          </td>
                          <td className="p-2 font-mono text-xs">
                            {JSON.stringify(
                              repaired?.resource_demands ??
                                previous?.resource_demands ??
                                {},
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </CardContent>
            </Card>

            {(result.warnings.length > 0 || result.diagnostics.limitations.length > 0) && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Warnings and limitations</CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="list-disc space-y-1 pl-5 text-sm">
                    {[...result.warnings, ...result.diagnostics.limitations].map(
                      (value, index) => <li key={`${index}-${value}`}>{value}</li>,
                    )}
                  </ul>
                </CardContent>
              </Card>
            )}

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Review acknowledgement</CardTitle>
                <CardDescription>
                  These local acknowledgements do not accept or persist the
                  candidate. They make the review boundary explicit while the
                  server-side accepted-draft lifecycle remains unavailable.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <label className="flex items-start gap-3 rounded-md border p-3 text-sm">
                  <input
                    type="checkbox"
                    className="mt-1 h-4 w-4"
                    checked={reviewedChanges}
                    onChange={(event) => setReviewedChanges(event.target.checked)}
                  />
                  <span>
                    I reviewed every moved, added, removed, and unresolved task
                    shown in the change ledger.
                  </span>
                </label>
                <label className="flex items-start gap-3 rounded-md border p-3 text-sm">
                  <input
                    type="checkbox"
                    className="mt-1 h-4 w-4"
                    checked={understandsBoundary}
                    onChange={(event) => setUnderstandsBoundary(event.target.checked)}
                  />
                  <span>
                    I understand this candidate remains unaccepted, unpersisted,
                    unapproved, and unexecuted.
                  </span>
                </label>
                <Button
                  type="button"
                  variant="outline"
                  disabled={
                    (hasReviewableChanges && !reviewedChanges) ||
                    !understandsBoundary
                  }
                  onClick={() => {
                    const blob = new Blob(
                      [JSON.stringify(result, null, 2)],
                      { type: "application/json" },
                    );
                    const url = URL.createObjectURL(blob);
                    const anchor = document.createElement("a");
                    anchor.href = url;
                    anchor.download = `preparation-repair-${result.repaired_response_hash ?? "candidate"}.json`;
                    anchor.click();
                    URL.revokeObjectURL(url);
                  }}
                >
                  Export reviewed candidate JSON
                </Button>
                <p className="text-xs text-muted-foreground">
                  Export is a local file action only. It does not update server
                  state or prove acceptance.
                </p>
              </CardContent>
            </Card>
          </section>
        )}
      </div>
    </AppLayout>
  );
}
