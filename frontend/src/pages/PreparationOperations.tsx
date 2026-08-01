import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import AppLayout from "@/components/AppLayout";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import { householdApi, type HouseholdRole } from "@/lib/platformApi";
import {
  preparationOperationsApi,
  type HouseholdResourceInput,
  type PersistedScheduleCreateRequest,
  type PreparationScheduleEventType,
  type PersistedPreparationScheduleView,
  type ResourceCalendarVersionCreate,
} from "@/lib/preparationOperationsApi";
import { AlertCircle, CalendarRange, CheckCircle2, Clock3, History, ShieldCheck } from "lucide-react";

const DEFAULT_RESOURCES = JSON.stringify(
  [
    {
      resource_id: "person",
      label: "Available cook",
      capacity: 1,
      resource_kind: "person",
      availability_windows: [
        { start_minute: 0, end_minute: 60 },
        { start_minute: 90, end_minute: 240 },
      ],
      metadata: { source: "household_review" },
    },
    {
      resource_id: "burner",
      label: "Stove burner",
      capacity: 2,
      resource_kind: "equipment",
      availability_windows: [{ start_minute: 0, end_minute: 240 }],
      metadata: { source: "household_review" },
    },
  ],
  null,
  2,
);

const EMPTY_SCHEDULE_BUNDLE = JSON.stringify(
  {
    calendar_version_id: 0,
    source_plan_id: null,
    source_plan_version: null,
    occurrence_set_version: "occurrences-v1",
    occurrence_set_hash: "replace-with-64-character-lowercase-sha256",
    profile_versions: {},
    schedule_request: {
      horizon_minutes: 240,
      granularity_minutes: 5,
      resources: [],
      tasks: [],
    },
    schedule_response: {
      method: "deterministic_dependency_aware_resource_scheduler_v3_multi_window",
      deterministic: true,
      horizon_minutes: 240,
      granularity_minutes: 5,
      scheduled: [],
      unscheduled: [],
      resource_utilization: {},
      resource_peak_usage: {},
      makespan_minutes: 0,
      diagnostics: {},
    },
    notes: "Reviewed preparation pipeline export",
  },
  null,
  2,
);

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "The request could not be completed";
}

function formatDate(value?: string | null): string {
  if (!value) return "Not recorded";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function shortHash(value?: string | null): string {
  if (!value) return "not recorded";
  return value.length <= 20 ? value : `${value.slice(0, 12)}…${value.slice(-6)}`;
}

function idempotencyKey(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}

function canEdit(role?: HouseholdRole | null): boolean {
  return role === "editor" || role === "owner";
}

function parseResources(raw: string): HouseholdResourceInput[] {
  const value = JSON.parse(raw) as unknown;
  if (!Array.isArray(value) || value.length === 0) {
    throw new Error("Resources JSON must be a non-empty array");
  }
  return value as HouseholdResourceInput[];
}

function parseScheduleBundle(raw: string): Omit<PersistedScheduleCreateRequest, "idempotency_key"> {
  const value = JSON.parse(raw) as unknown;
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("Schedule bundle must be a JSON object");
  }
  return value as Omit<PersistedScheduleCreateRequest, "idempotency_key">;
}

function TransitionButtons({
  schedule,
  role,
  pending,
  onTransition,
}: {
  schedule: PersistedPreparationScheduleView;
  role?: HouseholdRole | null;
  pending: boolean;
  onTransition: (eventType: Exclude<PreparationScheduleEventType, "created">) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {schedule.status === "draft" && role === "owner" && (
        <Button type="button" size="sm" disabled={pending || schedule.replay_status !== "replayable"} onClick={() => onTransition("approved")}>
          Approve
        </Button>
      )}
      {schedule.status === "approved" && canEdit(role) && (
        <Button type="button" size="sm" disabled={pending} onClick={() => onTransition("completed")}>
          Complete
        </Button>
      )}
      {(schedule.status === "draft" || schedule.status === "approved") && canEdit(role) && (
        <Button type="button" size="sm" variant="outline" disabled={pending} onClick={() => onTransition("cancelled")}>
          Cancel
        </Button>
      )}
      {(schedule.status === "draft" || schedule.status === "approved") && role === "owner" && (
        <Button type="button" size="sm" variant="outline" disabled={pending} onClick={() => onTransition("invalidated")}>
          Invalidate
        </Button>
      )}
    </div>
  );
}

export default function PreparationOperationsPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [selectedId, setSelectedId] = useState("");
  const [calendarVersion, setCalendarVersion] = useState("household-calendar-v1");
  const [horizonMinutes, setHorizonMinutes] = useState("240");
  const [timezone, setTimezone] = useState(() => Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC");
  const [reviewedAt, setReviewedAt] = useState(() => {
    const date = new Date();
    date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
    return date.toISOString().slice(0, 16);
  });
  const [reviewedBy, setReviewedBy] = useState("");
  const [calendarNotes, setCalendarNotes] = useState("");
  const [resourcesJson, setResourcesJson] = useState(DEFAULT_RESOURCES);
  const [scheduleJson, setScheduleJson] = useState(EMPTY_SCHEDULE_BUNDLE);
  const [transitionReasons, setTransitionReasons] = useState<Record<number, string>>({});
  const [expandedScheduleId, setExpandedScheduleId] = useState<number | null>(null);

  const householdsQ = useQuery({ queryKey: ["households"], queryFn: householdApi.list });
  const households = householdsQ.data ?? [];
  const householdId = selectedId || households[0]?.id || "";

  useEffect(() => {
    setExpandedScheduleId(null);
  }, [householdId]);

  const detailQ = useQuery({
    queryKey: ["households", householdId, "detail"],
    queryFn: () => householdApi.get(householdId),
    enabled: Boolean(householdId),
  });
  const calendarsQ = useQuery({
    queryKey: ["preparation-operations", householdId, "calendars"],
    queryFn: () => preparationOperationsApi.calendars(householdId),
    enabled: Boolean(householdId),
  });
  const schedulesQ = useQuery({
    queryKey: ["preparation-operations", householdId, "schedules"],
    queryFn: () => preparationOperationsApi.schedules(householdId),
    enabled: Boolean(householdId),
  });
  const eventsQ = useQuery({
    queryKey: ["preparation-operations", householdId, "schedule-events", expandedScheduleId],
    queryFn: () => preparationOperationsApi.events(householdId, expandedScheduleId as number),
    enabled: Boolean(householdId && expandedScheduleId),
  });

  const role = detailQ.data?.role;
  const activeCalendar = useMemo(
    () => (calendarsQ.data ?? []).find((calendar) => calendar.active),
    [calendarsQ.data],
  );

  const invalidate = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["preparation-operations", householdId, "calendars"] }),
      queryClient.invalidateQueries({ queryKey: ["preparation-operations", householdId, "schedules"] }),
      queryClient.invalidateQueries({ queryKey: ["preparation-operations", householdId, "schedule-events"] }),
    ]);
  };

  const createCalendar = useMutation({
    mutationFn: () => {
      const horizon = Number(horizonMinutes);
      if (!Number.isInteger(horizon) || horizon < 1 || horizon > 10080) {
        throw new Error("Horizon must be an integer from 1 to 10080 minutes");
      }
      const payload: ResourceCalendarVersionCreate = {
        calendar_version: calendarVersion.trim(),
        horizon_minutes: horizon,
        timezone: timezone.trim(),
        resources: parseResources(resourcesJson),
        evidence_status: "reviewed",
        reviewed_at: new Date(reviewedAt).toISOString(),
        reviewed_by: reviewedBy.trim(),
        notes: calendarNotes.trim() || null,
        activate: true,
        idempotency_key: idempotencyKey("calendar-create"),
      };
      return preparationOperationsApi.createCalendar(householdId, payload);
    },
    onSuccess: async (calendar) => {
      await invalidate();
      toast({ title: "Reviewed calendar activated", description: `${calendar.calendar_version} · ${calendar.resources.length} resources` });
    },
    onError: (error) => toast({ title: "Calendar registration failed", description: messageOf(error), variant: "destructive" }),
  });

  const createSchedule = useMutation({
    mutationFn: () => {
      const parsed = parseScheduleBundle(scheduleJson);
      return preparationOperationsApi.createSchedule(householdId, {
        ...parsed,
        idempotency_key: idempotencyKey("schedule-create"),
      });
    },
    onSuccess: async (schedule) => {
      await invalidate();
      toast({ title: "Draft schedule persisted", description: `Schedule #${schedule.id} is replayable and awaiting human approval.` });
    },
    onError: (error) => toast({ title: "Schedule persistence failed", description: messageOf(error), variant: "destructive" }),
  });

  const transition = useMutation({
    mutationFn: ({ schedule, eventType }: { schedule: PersistedPreparationScheduleView; eventType: Exclude<PreparationScheduleEventType, "created"> }) => {
      const reason = transitionReasons[schedule.id]?.trim() || `Household ${eventType} confirmation`;
      const payload = {
        expected_version: schedule.version,
        reason,
        idempotency_key: idempotencyKey(`schedule-${eventType}`),
        metadata: { source: "preparation_operations_ui" },
      };
      const handlers = {
        approved: preparationOperationsApi.approve,
        completed: preparationOperationsApi.complete,
        cancelled: preparationOperationsApi.cancel,
        invalidated: preparationOperationsApi.invalidate,
      };
      return handlers[eventType](householdId, schedule.id, payload);
    },
    onSuccess: async (schedule) => {
      await invalidate();
      toast({ title: `Schedule ${schedule.status}`, description: `Schedule #${schedule.id} is now version ${schedule.version}.` });
    },
    onError: (error) => toast({ title: "Schedule transition failed", description: messageOf(error), variant: "destructive" }),
  });

  const pageError = householdsQ.error || detailQ.error || calendarsQ.error || schedulesQ.error;

  return (
    <AppLayout>
      <div className="mx-auto max-w-7xl space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Preparation operations</h1>
          <p className="text-sm text-muted-foreground">
            Reviewed household resource calendars, deterministic replayable schedules, explicit approval, and append-only lifecycle history.
          </p>
        </div>

        {pageError && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Preparation operations unavailable</AlertTitle>
            <AlertDescription>{messageOf(pageError)}</AlertDescription>
          </Alert>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Household scope</CardTitle>
            <CardDescription>Every calendar, schedule, transition, and event remains isolated to one authorized household.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-[1fr_auto_auto] md:items-end">
            <div className="space-y-1">
              <Label htmlFor="operations-household">Household</Label>
              <select id="operations-household" value={householdId} onChange={(event) => setSelectedId(event.target.value)} className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                {households.map((household) => <option key={household.id} value={household.id}>{household.name}</option>)}
              </select>
            </div>
            <Badge variant="outline" className="w-fit capitalize">{role ?? "no role"}</Badge>
            <Badge variant={activeCalendar ? "default" : "secondary"} className="w-fit">
              {activeCalendar ? `Active ${activeCalendar.calendar_version}` : "No active reviewed calendar"}
            </Badge>
          </CardContent>
        </Card>

        <Alert>
          <ShieldCheck className="h-4 w-4" />
          <AlertTitle>Human-governed boundary</AlertTitle>
          <AlertDescription>
            Calendars are explicit household declarations, schedules are server-replayed plans, and approval is human confirmation. NutriFlavorOS does not control appliances, infer presence, verify execution, or guarantee food safety.
          </AlertDescription>
        </Alert>

        {householdId && (
          <Tabs defaultValue="schedules" className="space-y-4">
            <TabsList className="flex h-auto flex-wrap justify-start">
              <TabsTrigger value="schedules">Schedules</TabsTrigger>
              <TabsTrigger value="calendars">Resource calendars</TabsTrigger>
              <TabsTrigger value="ingest">Persist reviewed output</TabsTrigger>
            </TabsList>

            <TabsContent value="schedules" className="space-y-4">
              {(schedulesQ.data ?? []).map((schedule) => (
                <Card key={schedule.id}>
                  <CardHeader>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <CardTitle className="flex items-center gap-2 text-base"><Clock3 className="h-4 w-4" />Schedule #{schedule.id}</CardTitle>
                        <CardDescription>Created {formatDate(schedule.created_at)} · optimistic version {schedule.version}</CardDescription>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        <Badge variant={schedule.status === "approved" || schedule.status === "completed" ? "default" : "secondary"}>{schedule.status}</Badge>
                        <Badge variant={schedule.replay_status === "replayable" ? "default" : "destructive"}>{schedule.replay_status ?? "legacy_request_missing"}</Badge>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {schedule.replay_status !== "replayable" && (
                      <Alert variant="destructive">
                        <AlertCircle className="h-4 w-4" />
                        <AlertTitle>Approval blocked</AlertTitle>
                        <AlertDescription>This legacy row lacks the complete replay input. Recreate it with the exact original request before approval.</AlertDescription>
                      </Alert>
                    )}
                    <div className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
                      <div><p className="text-xs text-muted-foreground">Calendar</p><p>#{schedule.calendar_version_id}</p><code title={schedule.calendar_content_hash}>{shortHash(schedule.calendar_content_hash)}</code></div>
                      <div><p className="text-xs text-muted-foreground">Schedule hash</p><code title={schedule.schedule_hash}>{shortHash(schedule.schedule_hash)}</code></div>
                      <div><p className="text-xs text-muted-foreground">Request hash</p><code title={schedule.schedule_request_hash ?? undefined}>{shortHash(schedule.schedule_request_hash)}</code></div>
                      <div><p className="text-xs text-muted-foreground">Makespan</p><p>{schedule.schedule.makespan_minutes} minutes · {schedule.schedule.scheduled.length} tasks</p></div>
                    </div>
                    <div className="space-y-2">
                      {(schedule.schedule.scheduled ?? []).map((task) => (
                        <div key={task.task_id} className="grid gap-1 rounded-md border p-3 text-sm sm:grid-cols-[1fr_auto]">
                          <span>{task.task_id}</span>
                          <span className="text-muted-foreground">minute {task.start_minute}–{task.finish_minute}</span>
                        </div>
                      ))}
                    </div>
                    {(schedule.status === "draft" || schedule.status === "approved") && canEdit(role) && (
                      <div className="space-y-2 border-t pt-3">
                        <Label htmlFor={`transition-reason-${schedule.id}`}>Lifecycle reason</Label>
                        <Input id={`transition-reason-${schedule.id}`} value={transitionReasons[schedule.id] ?? ""} onChange={(event) => setTransitionReasons((current) => ({ ...current, [schedule.id]: event.target.value }))} placeholder="Record the human decision or operational outcome" />
                        <TransitionButtons schedule={schedule} role={role} pending={transition.isPending} onTransition={(eventType) => transition.mutate({ schedule, eventType })} />
                      </div>
                    )}
                    <div className="border-t pt-3">
                      <Button type="button" size="sm" variant="outline" onClick={() => setExpandedScheduleId((current) => current === schedule.id ? null : schedule.id)}>
                        <History className="mr-2 h-4 w-4" />{expandedScheduleId === schedule.id ? "Hide events" : "Load event history"}
                      </Button>
                      {expandedScheduleId === schedule.id && (
                        <div className="mt-3 space-y-2" aria-live="polite">
                          {eventsQ.isLoading && <p className="text-sm text-muted-foreground">Loading append-only events…</p>}
                          {(eventsQ.data ?? []).map((event) => (
                            <div key={event.id} className="rounded-md border p-3 text-sm">
                              <div className="flex flex-wrap justify-between gap-2"><span className="font-medium capitalize">{event.event_type}</span><span className="text-xs text-muted-foreground">{formatDate(event.created_at)}</span></div>
                              <p>{event.from_status ?? "none"} → {event.to_status} · {event.reason}</p>
                              <p className="text-xs text-muted-foreground">Actor {event.actor_user_id} · fingerprint <code title={event.request_fingerprint}>{shortHash(event.request_fingerprint)}</code></p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
              {!schedulesQ.isLoading && (schedulesQ.data?.length ?? 0) === 0 && <p className="text-sm text-muted-foreground">No persisted preparation schedules.</p>}
            </TabsContent>

            <TabsContent value="calendars" className="space-y-4">
              {role === "owner" && (
                <Card>
                  <CardHeader><CardTitle className="text-base">Register and activate a reviewed calendar</CardTitle><CardDescription>Activating a successor invalidates draft and approved schedules linked to the prior calendar.</CardDescription></CardHeader>
                  <CardContent>
                    <form className="space-y-3" onSubmit={(event) => { event.preventDefault(); createCalendar.mutate(); }}>
                      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
                        <div className="space-y-1"><Label htmlFor="calendar-version">Version</Label><Input id="calendar-version" value={calendarVersion} onChange={(event) => setCalendarVersion(event.target.value)} required /></div>
                        <div className="space-y-1"><Label htmlFor="calendar-horizon">Horizon minutes</Label><Input id="calendar-horizon" type="number" min="1" max="10080" value={horizonMinutes} onChange={(event) => setHorizonMinutes(event.target.value)} required /></div>
                        <div className="space-y-1"><Label htmlFor="calendar-timezone">Timezone</Label><Input id="calendar-timezone" value={timezone} onChange={(event) => setTimezone(event.target.value)} required /></div>
                        <div className="space-y-1"><Label htmlFor="calendar-reviewed-at">Reviewed at</Label><Input id="calendar-reviewed-at" type="datetime-local" value={reviewedAt} onChange={(event) => setReviewedAt(event.target.value)} required /></div>
                      </div>
                      <div className="grid gap-3 md:grid-cols-2">
                        <div className="space-y-1"><Label htmlFor="calendar-reviewed-by">Reviewed by</Label><Input id="calendar-reviewed-by" value={reviewedBy} onChange={(event) => setReviewedBy(event.target.value)} required /></div>
                        <div className="space-y-1"><Label htmlFor="calendar-notes">Review notes</Label><Input id="calendar-notes" value={calendarNotes} onChange={(event) => setCalendarNotes(event.target.value)} /></div>
                      </div>
                      <div className="space-y-1"><Label htmlFor="calendar-resources">Resources and explicit windows JSON</Label><Textarea id="calendar-resources" className="min-h-72 font-mono text-xs" value={resourcesJson} onChange={(event) => setResourcesJson(event.target.value)} required /></div>
                      <Button type="submit" disabled={createCalendar.isPending}>Register active reviewed calendar</Button>
                    </form>
                  </CardContent>
                </Card>
              )}
              <div className="grid gap-4 lg:grid-cols-2">
                {(calendarsQ.data ?? []).map((calendar) => (
                  <Card key={calendar.id}>
                    <CardHeader>
                      <div className="flex flex-wrap items-start justify-between gap-2"><div><CardTitle className="flex items-center gap-2 text-base"><CalendarRange className="h-4 w-4" />{calendar.calendar_version}</CardTitle><CardDescription>Record #{calendar.id} · {calendar.timezone} · {calendar.horizon_minutes} minutes</CardDescription></div><div className="flex gap-1"><Badge variant="outline">{calendar.evidence_status}</Badge><Badge variant={calendar.active ? "default" : "secondary"}>{calendar.active ? "active" : "historical"}</Badge></div></div>
                    </CardHeader>
                    <CardContent className="space-y-3 text-sm">
                      <p>Reviewed by {calendar.reviewed_by ?? "not recorded"} · {formatDate(calendar.reviewed_at)}</p>
                      <p>SHA-256 <code title={calendar.content_hash}>{shortHash(calendar.content_hash)}</code></p>
                      {calendar.supersedes_calendar_id && <p className="text-muted-foreground">Supersedes calendar #{calendar.supersedes_calendar_id}</p>}
                      {calendar.resources.map((resource) => (
                        <div key={resource.id} className="rounded-md border p-3"><div className="flex justify-between gap-2"><span className="font-medium">{resource.label}</span><Badge variant="outline">capacity {resource.capacity}</Badge></div><p className="text-xs text-muted-foreground">{resource.resource_id} · {resource.resource_kind}</p><p className="mt-1 text-xs">{resource.availability_windows.map((window) => `${window.start_minute}–${window.end_minute}`).join(", ")}</p></div>
                      ))}
                    </CardContent>
                  </Card>
                ))}
              </div>
            </TabsContent>

            <TabsContent value="ingest">
              <Card>
                <CardHeader><CardTitle className="flex items-center gap-2 text-base"><CheckCircle2 className="h-4 w-4" />Persist reviewed deterministic output</CardTitle><CardDescription>Editors paste the complete request and response exported by the reviewed preparation pipeline. The server rejects any resource mismatch, stale plan, unresolved task, or replay difference.</CardDescription></CardHeader>
                <CardContent>
                  <form className="space-y-3" onSubmit={(event) => { event.preventDefault(); createSchedule.mutate(); }}>
                    <div className="space-y-1"><Label htmlFor="schedule-bundle">Schedule creation bundle JSON</Label><Textarea id="schedule-bundle" className="min-h-[32rem] font-mono text-xs" value={scheduleJson} onChange={(event) => setScheduleJson(event.target.value)} required /></div>
                    <Button type="submit" disabled={!canEdit(role) || createSchedule.isPending}>Persist replayable draft</Button>
                  </form>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        )}
      </div>
    </AppLayout>
  );
}
