import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

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
import { householdApi } from "@/lib/platformApi";
import {
  preparationApi,
  type CompileAndScheduleRequest,
  type PreparationOccurrenceInput,
  type PreparationResourceInput,
} from "@/lib/preparationApi";
import { preparationOperationsApi } from "@/lib/preparationOperationsApi";
import {
  buildPreparationOperationsHandoff,
  calendarPreparationResources,
  storePreparationOperationsHandoff,
} from "@/lib/preparationOperationsHandoff";
import {
  AlertTriangle,
  ArrowRight,
  CalendarRange,
  CheckCircle2,
  Clock3,
  FileWarning,
  Plus,
  ShieldCheck,
  Trash2,
} from "lucide-react";

interface OccurrenceDraft {
  occurrenceId: string;
  recipeId: string;
  finishMinute: string;
  servings: string;
  priority: string;
}

interface ResourceDraft {
  resourceId: string;
  label: string;
  capacity: string;
  availableFrom: string;
  availableUntil: string;
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "The pipeline could not be executed";
}

function integer(value: string, label: string, minimum: number, maximum: number): number {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < minimum || parsed > maximum) {
    throw new Error(`${label} must be an integer from ${minimum} to ${maximum}`);
  }
  return parsed;
}

function positive(value: string, label: string, maximum: number): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0 || parsed > maximum) {
    throw new Error(`${label} must be greater than zero and at most ${maximum}`);
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

function minuteLabel(value: number): string {
  const day = Math.floor(value / 1440) + 1;
  const withinDay = value % 1440;
  const hours = Math.floor(withinDay / 60);
  const minutes = withinDay % 60;
  return `Day ${day}, ${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
}

export default function PreparationPipelinePage() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const [occurrences, setOccurrences] = useState<OccurrenceDraft[]>([]);
  const [resources, setResources] = useState<ResourceDraft[]>([]);
  const [horizon, setHorizon] = useState("1440");
  const [granularity, setGranularity] = useState("5");
  const [allowPartial, setAllowPartial] = useState(false);
  const [durationPolicy, setDurationPolicy] = useState<
    "conservative_max" | "optimistic_min"
  >("conservative_max");
  const [selectedHouseholdId, setSelectedHouseholdId] = useState("");
  const [useActiveCalendar, setUseActiveCalendar] = useState(false);
  const [occurrenceSetVersion, setOccurrenceSetVersion] = useState("occurrences-v1");
  const [handoffNotes, setHandoffNotes] = useState("");
  const [lastCompileRequest, setLastCompileRequest] = useState<CompileAndScheduleRequest | null>(null);
  const [handoffPending, setHandoffPending] = useState(false);

  const profiles = useQuery({
    queryKey: ["preparation-profiles", "active-reviewed"],
    queryFn: () => preparationApi.profiles(true, true),
  });
  const householdsQ = useQuery({
    queryKey: ["households"],
    queryFn: householdApi.list,
  });
  const households = householdsQ.data ?? [];
  const householdId = selectedHouseholdId || households[0]?.id || "";
  const calendarsQ = useQuery({
    queryKey: ["preparation-operations", householdId, "active-calendar"],
    queryFn: () => preparationOperationsApi.calendars(householdId, true),
    enabled: Boolean(householdId),
  });
  const activeCalendar = useMemo(
    () => (calendarsQ.data ?? []).find((calendar) => calendar.active),
    [calendarsQ.data],
  );

  const buildPayload = (): CompileAndScheduleRequest => {
    const governed = useActiveCalendar;
    if (governed && !activeCalendar) {
      throw new Error("The selected household has no active reviewed resource calendar");
    }
    const horizonMinutes = governed
      ? activeCalendar!.horizon_minutes
      : integer(horizon, "Horizon", 1, 10080);
    const occurrencePayload: PreparationOccurrenceInput[] = occurrences.map(
      (value, index) => {
        const occurrenceId = value.occurrenceId.trim();
        const recipeId = value.recipeId.trim();
        if (!occurrenceId) throw new Error(`Occurrence ${index + 1} needs an identifier`);
        if (!recipeId) throw new Error(`Occurrence ${occurrenceId} needs a reviewed profile`);
        return {
          occurrence_id: occurrenceId,
          recipe_id: recipeId,
          required_finish_minute: integer(
            value.finishMinute,
            `Finish for ${occurrenceId}`,
            1,
            horizonMinutes,
          ),
          servings: positive(value.servings, `Servings for ${occurrenceId}`, 1000),
          priority: integer(value.priority, `Priority for ${occurrenceId}`, -1000, 1000),
        };
      },
    );
    const resourcePayload: PreparationResourceInput[] = governed
      ? calendarPreparationResources(activeCalendar!)
      : resources.map((value, index) => {
          const resourceId = value.resourceId.trim();
          if (!resourceId) throw new Error(`Resource ${index + 1} needs an identifier`);
          return {
            resource_id: resourceId,
            label: value.label.trim() || null,
            capacity: integer(value.capacity, `Capacity for ${resourceId}`, 1, 1000),
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
        });
    return {
      occurrences: occurrencePayload,
      duration_policy: durationPolicy,
      reviewed_only: true,
      allow_partial: allowPartial,
      horizon_minutes: horizonMinutes,
      granularity_minutes: integer(granularity, "Granularity", 1, 60),
      resources: resourcePayload,
    };
  };

  const pipeline = useMutation({
    mutationFn: () => {
      const payload = buildPayload();
      setLastCompileRequest(payload);
      return preparationApi.compileAndSchedule(payload);
    },
    onSuccess: (value) => {
      const title =
        value.execution_status === "scheduled"
          ? "Preparation pipeline scheduled"
          : value.execution_status === "blocked_unresolved"
            ? "Scheduling blocked by unresolved evidence"
            : "No preparation tasks could be compiled";
      toast({
        title,
        description: `${value.compilation.tasks.length} tasks compiled; ${value.compilation.unresolved.length} unresolved occurrences.`,
        variant: value.execution_status === "scheduled" ? "default" : "destructive",
      });
    },
    onError: (error) =>
      toast({
        title: "Preparation pipeline failed",
        description: messageOf(error),
        variant: "destructive",
      }),
  });

  const sendToOperations = async () => {
    if (!pipeline.data || !lastCompileRequest || !activeCalendar) return;
    setHandoffPending(true);
    try {
      const handoff = await buildPreparationOperationsHandoff({
        householdId,
        calendar: activeCalendar,
        compileRequest: lastCompileRequest,
        compileResponse: pipeline.data,
        occurrenceSetVersion,
        notes: handoffNotes,
      });
      storePreparationOperationsHandoff(handoff);
      navigate("/preparation/operations?handoff=1");
    } catch (error) {
      toast({
        title: "Operations handoff failed",
        description: messageOf(error),
        variant: "destructive",
      });
    } finally {
      setHandoffPending(false);
    }
  };

  const addOccurrence = () =>
    setOccurrences((current) => [
      ...current,
      { occurrenceId: "", recipeId: "", finishMinute: "", servings: "1", priority: "0" },
    ]);

  const addResource = () =>
    setResources((current) => [
      ...current,
      { resourceId: "", label: "", capacity: "1", availableFrom: "0", availableUntil: "" },
    ]);

  const canHandoff = Boolean(
    useActiveCalendar
      && activeCalendar
      && lastCompileRequest
      && pipeline.data?.execution_status === "scheduled"
      && pipeline.data.partial === false
      && pipeline.data.compilation.unresolved.length === 0
      && pipeline.data.schedule
      && pipeline.data.schedule.unscheduled.length === 0
      && !lastCompileRequest.allow_partial,
  );

  return (
    <AppLayout>
      <div className="mx-auto max-w-7xl space-y-6">
        <header>
          <h1 className="text-2xl font-bold">Reviewed preparation pipeline</h1>
          <p className="text-sm text-muted-foreground">
            Compile immutable reviewed recipe evidence and schedule it in one fail-closed request.
          </p>
        </header>

        <Alert>
          <ShieldCheck className="h-4 w-4" />
          <AlertTitle>Fail-closed by default</AlertTitle>
          <AlertDescription>
            Missing, inactive, unreviewed, or serving-range-incompatible occurrences block the schedule. Persisted operations additionally require an active reviewed household calendar, zero unresolved work, and partial scheduling disabled.
          </AlertDescription>
        </Alert>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base"><CalendarRange className="h-4 w-4" />Household operations scope</CardTitle>
            <CardDescription>Use the active reviewed calendar to create an exact bundle that can be reviewed and persisted separately.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
            <div className="space-y-1">
              <Label htmlFor="pipeline-household">Household</Label>
              <select id="pipeline-household" value={householdId} onChange={(event) => setSelectedHouseholdId(event.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm">
                <option value="">No household selected</option>
                {households.map((household) => <option key={household.id} value={household.id}>{household.name}</option>)}
              </select>
            </div>
            <label className="flex min-h-10 items-center gap-2 rounded-md border px-3 text-sm lg:mt-6">
              <input type="checkbox" checked={useActiveCalendar} disabled={!activeCalendar} onChange={(event) => { setUseActiveCalendar(event.target.checked); setLastCompileRequest(null); pipeline.reset(); }} />
              Use active reviewed calendar
            </label>
            <div className="space-y-1">
              <Label htmlFor="occurrence-set-version">Occurrence-set version</Label>
              <Input id="occurrence-set-version" value={occurrenceSetVersion} onChange={(event) => setOccurrenceSetVersion(event.target.value)} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="handoff-notes">Handoff notes</Label>
              <Input id="handoff-notes" value={handoffNotes} onChange={(event) => setHandoffNotes(event.target.value)} />
            </div>
            <div className="md:col-span-2 lg:col-span-4">
              {activeCalendar ? (
                <div className="rounded-md border p-3 text-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2"><span className="font-medium">Active {activeCalendar.calendar_version}</span><Badge variant="default">reviewed</Badge></div>
                  <p className="text-muted-foreground">#{activeCalendar.id} · {activeCalendar.horizon_minutes} minutes · {activeCalendar.resources.length} resources · {activeCalendar.timezone}</p>
                  <p className="break-all font-mono text-[11px] text-muted-foreground">sha256:{activeCalendar.content_hash}</p>
                </div>
              ) : householdId ? (
                <Alert variant="destructive"><AlertTriangle className="h-4 w-4" /><AlertTitle>No active reviewed calendar</AlertTitle><AlertDescription>Create and activate one in Preparation Operations before using governed handoff.</AlertDescription></Alert>
              ) : (
                <p className="text-sm text-muted-foreground">Select a household to inspect its active calendar.</p>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Active reviewed profiles</CardTitle><CardDescription>Versions and hashes identify the exact evidence used by compiled tasks.</CardDescription></CardHeader>
          <CardContent className="space-y-3">
            {profiles.isLoading && <p className="text-sm text-muted-foreground">Loading reviewed profiles…</p>}
            {profiles.error && <Alert variant="destructive"><AlertTriangle className="h-4 w-4" /><AlertTitle>Profiles unavailable</AlertTitle><AlertDescription>{messageOf(profiles.error)}</AlertDescription></Alert>}
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {(profiles.data ?? []).map((profile) => (
                <article key={profile.id} className="rounded-md border p-3 text-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2"><span className="font-medium">{profile.recipe_id}</span><Badge variant="outline">v{profile.profile_version}</Badge></div>
                  <p>{profile.task_templates.length} tasks · {profile.supported_servings_min.toLocaleString()}–{profile.supported_servings_max.toLocaleString()} servings</p>
                  <p className="text-xs text-muted-foreground">{profile.source_name} · source {profile.source_version}</p>
                  <p className="break-all font-mono text-[11px] text-muted-foreground">sha256:{profile.content_hash}</p>
                </article>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Pipeline controls</CardTitle></CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="space-y-1"><Label htmlFor="pipeline-horizon">Horizon minutes</Label><Input id="pipeline-horizon" type="number" min="1" max="10080" value={useActiveCalendar && activeCalendar ? String(activeCalendar.horizon_minutes) : horizon} disabled={useActiveCalendar} onChange={(event) => setHorizon(event.target.value)} /></div>
            <div className="space-y-1"><Label htmlFor="pipeline-granularity">Granularity minutes</Label><Input id="pipeline-granularity" type="number" min="1" max="60" value={granularity} onChange={(event) => setGranularity(event.target.value)} /></div>
            <div className="space-y-1"><Label htmlFor="pipeline-duration-policy">Duration policy</Label><select id="pipeline-duration-policy" className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={durationPolicy} onChange={(event) => setDurationPolicy(event.target.value as "conservative_max" | "optimistic_min")}><option value="conservative_max">Conservative maximum</option><option value="optimistic_min">Optimistic minimum (sensitivity only)</option></select></div>
            <label className="flex min-h-10 items-center gap-2 rounded-md border px-3 text-sm"><input type="checkbox" checked={allowPartial} onChange={(event) => setAllowPartial(event.target.checked)} />Allow partial scheduling</label>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-start justify-between gap-3"><div><CardTitle className="text-base">Recipe occurrences</CardTitle><CardDescription>Finish times are relative to the scheduling horizon.</CardDescription></div><Button type="button" variant="outline" onClick={addOccurrence}><Plus className="mr-2 h-4 w-4" /> Add occurrence</Button></CardHeader>
          <CardContent className="space-y-3">
            {occurrences.map((value, index) => (
              <div key={index} className="grid gap-3 rounded-md border p-3 md:grid-cols-6">
                <div className="space-y-1"><Label htmlFor={`pipeline-occurrence-${index}`}>Occurrence ID</Label><Input id={`pipeline-occurrence-${index}`} value={value.occurrenceId} onChange={(event) => setOccurrences((current) => current.map((item, position) => position === index ? { ...item, occurrenceId: event.target.value } : item))} placeholder="day1.dinner" /></div>
                <div className="space-y-1"><Label htmlFor={`pipeline-recipe-${index}`}>Reviewed profile</Label><select id={`pipeline-recipe-${index}`} className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={value.recipeId} onChange={(event) => setOccurrences((current) => current.map((item, position) => position === index ? { ...item, recipeId: event.target.value } : item))}><option value="">Select profile</option>{(profiles.data ?? []).map((profile) => <option key={profile.id} value={profile.recipe_id}>{profile.recipe_id} · v{profile.profile_version}</option>)}</select></div>
                <div className="space-y-1"><Label htmlFor={`pipeline-finish-${index}`}>Required finish</Label><Input id={`pipeline-finish-${index}`} type="number" min="1" value={value.finishMinute} onChange={(event) => setOccurrences((current) => current.map((item, position) => position === index ? { ...item, finishMinute: event.target.value } : item))} /></div>
                <div className="space-y-1"><Label htmlFor={`pipeline-servings-${index}`}>Servings</Label><Input id={`pipeline-servings-${index}`} type="number" min="0.01" step="0.01" value={value.servings} onChange={(event) => setOccurrences((current) => current.map((item, position) => position === index ? { ...item, servings: event.target.value } : item))} /></div>
                <div className="space-y-1"><Label htmlFor={`pipeline-priority-${index}`}>Priority</Label><Input id={`pipeline-priority-${index}`} type="number" value={value.priority} onChange={(event) => setOccurrences((current) => current.map((item, position) => position === index ? { ...item, priority: event.target.value } : item))} /></div>
                <div className="flex items-end"><Button type="button" variant="outline" aria-label={`Remove occurrence ${index + 1}`} onClick={() => setOccurrences((current) => current.filter((_, position) => position !== index))}><Trash2 className="h-4 w-4" /></Button></div>
              </div>
            ))}
            {occurrences.length === 0 && <p className="text-sm text-muted-foreground">Add every meal occurrence that must be prepared.</p>}
          </CardContent>
        </Card>

        {useActiveCalendar && activeCalendar ? (
          <Card>
            <CardHeader><CardTitle className="text-base">Calendar-bound resources</CardTitle><CardDescription>These immutable reviewed resources are used exactly; manual changes are disabled in governed mode.</CardDescription></CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {activeCalendar.resources.map((resource) => <div key={resource.id} className="rounded-md border p-3 text-sm"><div className="flex justify-between gap-2"><span className="font-medium">{resource.label}</span><Badge variant="outline">capacity {resource.capacity}</Badge></div><p className="text-xs text-muted-foreground">{resource.resource_id} · {resource.resource_kind}</p><p className="mt-1 text-xs">{resource.availability_windows.map((window) => `${window.start_minute}–${window.end_minute}`).join(", ")}</p></div>)}
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardHeader className="flex-row items-start justify-between gap-3"><div><CardTitle className="text-base">Manual sensitivity resources</CardTitle><CardDescription>Manual resources support exploration but cannot be handed to persisted operations.</CardDescription></div><Button type="button" variant="outline" onClick={addResource}><Plus className="mr-2 h-4 w-4" /> Add resource</Button></CardHeader>
            <CardContent className="space-y-3">
              {resources.map((value, index) => (
                <div key={index} className="grid gap-3 rounded-md border p-3 md:grid-cols-6">
                  <div className="space-y-1"><Label htmlFor={`pipeline-resource-${index}`}>Resource ID</Label><Input id={`pipeline-resource-${index}`} value={value.resourceId} onChange={(event) => setResources((current) => current.map((item, position) => position === index ? { ...item, resourceId: event.target.value } : item))} placeholder="oven" /></div>
                  <div className="space-y-1"><Label htmlFor={`pipeline-resource-label-${index}`}>Label</Label><Input id={`pipeline-resource-label-${index}`} value={value.label} onChange={(event) => setResources((current) => current.map((item, position) => position === index ? { ...item, label: event.target.value } : item))} /></div>
                  <div className="space-y-1"><Label htmlFor={`pipeline-capacity-${index}`}>Capacity</Label><Input id={`pipeline-capacity-${index}`} type="number" min="1" value={value.capacity} onChange={(event) => setResources((current) => current.map((item, position) => position === index ? { ...item, capacity: event.target.value } : item))} /></div>
                  <div className="space-y-1"><Label htmlFor={`pipeline-from-${index}`}>Available from</Label><Input id={`pipeline-from-${index}`} type="number" min="0" value={value.availableFrom} onChange={(event) => setResources((current) => current.map((item, position) => position === index ? { ...item, availableFrom: event.target.value } : item))} /></div>
                  <div className="space-y-1"><Label htmlFor={`pipeline-until-${index}`}>Available until</Label><Input id={`pipeline-until-${index}`} type="number" min="1" value={value.availableUntil} onChange={(event) => setResources((current) => current.map((item, position) => position === index ? { ...item, availableUntil: event.target.value } : item))} placeholder="horizon" /></div>
                  <div className="flex items-end"><Button type="button" variant="outline" aria-label={`Remove resource ${index + 1}`} onClick={() => setResources((current) => current.filter((_, position) => position !== index))}><Trash2 className="h-4 w-4" /></Button></div>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        <Button type="button" size="lg" onClick={() => pipeline.mutate()} disabled={occurrences.length === 0 || pipeline.isPending}><Clock3 className="mr-2 h-4 w-4" /> Compile and schedule safely</Button>

        {pipeline.error && <Alert variant="destructive"><AlertTriangle className="h-4 w-4" /><AlertTitle>Pipeline unavailable</AlertTitle><AlertDescription>{messageOf(pipeline.error)}</AlertDescription></Alert>}

        {pipeline.data && (
          <section className="space-y-4" aria-live="polite">
            <Alert variant={pipeline.data.execution_status === "scheduled" ? "default" : "destructive"}>
              {pipeline.data.execution_status === "scheduled" ? <CheckCircle2 className="h-4 w-4" /> : <FileWarning className="h-4 w-4" />}
              <AlertTitle>{pipeline.data.execution_status.replaceAll("_", " ")}</AlertTitle>
              <AlertDescription>{pipeline.data.compilation.tasks.length} tasks compiled; {pipeline.data.compilation.unresolved.length} unresolved. Partial: {pipeline.data.partial ? "yes" : "no"}.</AlertDescription>
            </Alert>
            {pipeline.data.compilation.warnings.map((warning) => <Alert key={warning}><AlertTriangle className="h-4 w-4" /><AlertTitle>Evidence warning</AlertTitle><AlertDescription>{warning}</AlertDescription></Alert>)}
            {pipeline.data.compilation.unresolved.map((value) => <Alert key={value.occurrence_id} variant="destructive"><FileWarning className="h-4 w-4" /><AlertTitle>{value.occurrence_id}: {value.reason_code.replaceAll("_", " ")}</AlertTitle><AlertDescription>{value.message}</AlertDescription></Alert>)}
            {pipeline.data.schedule && (
              <>
                <div className="grid gap-3 sm:grid-cols-3"><Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Scheduled</p><p className="text-2xl font-bold">{pipeline.data.schedule.scheduled.length}</p></CardContent></Card><Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Unscheduled</p><p className="text-2xl font-bold">{pipeline.data.schedule.unscheduled.length}</p></CardContent></Card><Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Makespan</p><p className="text-2xl font-bold">{pipeline.data.schedule.makespan_minutes} min</p></CardContent></Card></div>
                <Card><CardHeader><CardTitle className="text-base">Scheduled work</CardTitle></CardHeader><CardContent className="space-y-2">{pipeline.data.schedule.scheduled.map((task) => <article key={task.task_id} className="rounded-md border p-3 text-sm"><div className="flex flex-wrap items-center justify-between gap-2"><span className="font-medium">{task.task_id}</span><Badge variant="outline">priority {task.priority}</Badge></div><p>{minuteLabel(task.start_minute)} → {minuteLabel(task.finish_minute)}</p>{task.dependencies.length > 0 && <p className="text-xs text-muted-foreground">After: {task.dependencies.join(", ")}</p>}<p className="break-all font-mono text-[11px] text-muted-foreground">{String(task.metadata.profile_content_hash ?? "no evidence hash")}</p></article>)}</CardContent></Card>
              </>
            )}
            {useActiveCalendar && (
              <Card>
                <CardHeader><CardTitle className="text-base">Governed operations handoff</CardTitle><CardDescription>The exact bundle remains a draft until an editor persists it and an owner approves it in the separate operations workspace.</CardDescription></CardHeader>
                <CardContent className="space-y-3">
                  {!canHandoff && <Alert variant="destructive"><AlertTriangle className="h-4 w-4" /><AlertTitle>Handoff unavailable</AlertTitle><AlertDescription>Use the active calendar, disable partial scheduling, and resolve every occurrence and task.</AlertDescription></Alert>}
                  <Button type="button" disabled={!canHandoff || handoffPending} onClick={() => void sendToOperations()}><ArrowRight className="mr-2 h-4 w-4" /> Send replayable bundle to operations</Button>
                </CardContent>
              </Card>
            )}
          </section>
        )}
      </div>
    </AppLayout>
  );
}
