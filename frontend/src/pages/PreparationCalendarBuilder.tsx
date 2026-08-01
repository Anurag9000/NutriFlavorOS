import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  ClipboardCheck,
  CopyPlus,
  FileJson2,
  Plus,
  ShieldCheck,
  Trash2,
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
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import { householdApi } from "@/lib/platformApi";
import {
  preparationOperationsApi,
  type HouseholdResourceInput,
  type ResourceCalendarVersionCreate,
  type ResourceCalendarVersionView,
} from "@/lib/preparationOperationsApi";

const RESOURCE_ID_PATTERN = /^[A-Za-z0-9_.:-]+$/;

const templates = {
  person: {
    label: "Available cook",
    resource_kind: "person",
    capacity: 1,
  },
  burner: {
    label: "Stove burner",
    resource_kind: "equipment",
    capacity: 1,
  },
  oven: {
    label: "Oven",
    resource_kind: "equipment",
    capacity: 1,
  },
  counter: {
    label: "Counter workspace",
    resource_kind: "workspace",
    capacity: 1,
  },
  refrigerator: {
    label: "Refrigerator space",
    resource_kind: "storage",
    capacity: 1,
  },
  custom: {
    label: "Custom resource",
    resource_kind: "custom",
    capacity: 1,
  },
} as const;

type TemplateName = keyof typeof templates;

type WindowDraft = {
  local_id: string;
  start_minute: string;
  end_minute: string;
};

type ResourceDraft = {
  local_id: string;
  resource_id: string;
  label: string;
  capacity: string;
  resource_kind: string;
  windows: WindowDraft[];
};

type CalendarDraftDocument = {
  document_version: "preparation-resource-calendar-draft-v1";
  calendar_version: string;
  horizon_minutes: number;
  timezone: string;
  notes: string | null;
  resources: HouseholdResourceInput[];
};

type ReviewChecks = {
  people: boolean;
  equipment: boolean;
  timezone: boolean;
  invalidation: boolean;
};

function localId(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}

function defaultResource(
  template: TemplateName,
  horizonMinutes = 240,
  index = 0,
): ResourceDraft {
  const definition = templates[template];
  const suffix = index > 0 ? `-${index + 1}` : "";
  return {
    local_id: localId(`resource-${template}`),
    resource_id: template === "custom" ? "" : `${template}${suffix}`,
    label: definition.label,
    capacity: String(definition.capacity),
    resource_kind: definition.resource_kind,
    windows: [
      {
        local_id: localId(`window-${template}`),
        start_minute: "0",
        end_minute: String(horizonMinutes),
      },
    ],
  };
}

function messageOf(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "The reviewed calendar could not be registered";
}

function canonicalResource(resource: HouseholdResourceInput): HouseholdResourceInput {
  return {
    resource_id: resource.resource_id,
    label: resource.label,
    capacity: resource.capacity,
    resource_kind: resource.resource_kind,
    availability_windows: [...resource.availability_windows].sort(
      (left, right) =>
        left.start_minute - right.start_minute
        || left.end_minute - right.end_minute,
    ),
    metadata: Object.fromEntries(
      Object.entries(resource.metadata ?? {}).sort(([left], [right]) =>
        left.localeCompare(right),
      ),
    ),
  };
}

function resourceSignature(resource: HouseholdResourceInput): string {
  return JSON.stringify(canonicalResource(resource));
}

function toResourceDraft(resource: HouseholdResourceInput): ResourceDraft {
  return {
    local_id: localId(`resource-${resource.resource_id}`),
    resource_id: resource.resource_id,
    label: resource.label,
    capacity: String(resource.capacity),
    resource_kind: resource.resource_kind,
    windows: resource.availability_windows.map((window) => ({
      local_id: localId(`window-${resource.resource_id}`),
      start_minute: String(window.start_minute),
      end_minute: String(window.end_minute),
    })),
  };
}

function normalizeResources(
  drafts: ResourceDraft[],
  horizonMinutes: number,
): HouseholdResourceInput[] {
  if (drafts.length === 0) {
    throw new Error("Add at least one reviewed household resource");
  }
  const seen = new Set<string>();
  const normalized = drafts.map((resource, resourceIndex) => {
    const resourceId = resource.resource_id.trim();
    const label = resource.label.trim();
    const resourceKind = resource.resource_kind.trim();
    const capacity = Number(resource.capacity);
    if (!resourceId || !RESOURCE_ID_PATTERN.test(resourceId)) {
      throw new Error(
        `Resource ${resourceIndex + 1} needs an ID using letters, numbers, _, ., :, or -`,
      );
    }
    if (seen.has(resourceId)) {
      throw new Error(`Resource ID ${resourceId} is duplicated`);
    }
    seen.add(resourceId);
    if (!label) {
      throw new Error(`Resource ${resourceId} needs a label`);
    }
    if (!resourceKind) {
      throw new Error(`Resource ${resourceId} needs a kind`);
    }
    if (!Number.isInteger(capacity) || capacity < 1 || capacity > 1000) {
      throw new Error(`Resource ${resourceId} capacity must be an integer from 1 to 1000`);
    }
    if (resource.windows.length === 0) {
      throw new Error(`Resource ${resourceId} needs at least one availability window`);
    }
    const windows = resource.windows
      .map((window, windowIndex) => {
        const start = Number(window.start_minute);
        const end = Number(window.end_minute);
        if (!Number.isInteger(start) || !Number.isInteger(end)) {
          throw new Error(
            `Window ${windowIndex + 1} for ${resourceId} must use integer minutes`,
          );
        }
        if (start < 0 || end <= start || end > horizonMinutes) {
          throw new Error(
            `Window ${windowIndex + 1} for ${resourceId} must satisfy 0 ≤ start < end ≤ ${horizonMinutes}`,
          );
        }
        return { start_minute: start, end_minute: end };
      })
      .sort(
        (left, right) =>
          left.start_minute - right.start_minute
          || left.end_minute - right.end_minute,
      );
    for (let index = 1; index < windows.length; index += 1) {
      if (windows[index].start_minute < windows[index - 1].end_minute) {
        throw new Error(`Availability windows for ${resourceId} cannot overlap`);
      }
    }
    return canonicalResource({
      resource_id: resourceId,
      label,
      capacity,
      resource_kind: resourceKind,
      availability_windows: windows,
      metadata: { source: "structured_calendar_builder" },
    });
  });
  return normalized.sort((left, right) =>
    left.resource_id.localeCompare(right.resource_id),
  );
}

function parseDraftDocument(raw: string): CalendarDraftDocument {
  const parsed = JSON.parse(raw) as Partial<CalendarDraftDocument>;
  if (
    parsed.document_version !== "preparation-resource-calendar-draft-v1"
    || typeof parsed.calendar_version !== "string"
    || typeof parsed.horizon_minutes !== "number"
    || typeof parsed.timezone !== "string"
    || !Array.isArray(parsed.resources)
  ) {
    throw new Error("JSON is not a preparation-resource-calendar-draft-v1 document");
  }
  return parsed as CalendarDraftDocument;
}

function formattedReviewTime(reviewedAt: string, timezone: string): string {
  try {
    const value = new Date(reviewedAt);
    if (Number.isNaN(value.getTime())) return "Invalid review time";
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: timezone,
    }).format(value);
  } catch {
    return "Invalid timezone or review time";
  }
}

function diffResources(
  activeCalendar: ResourceCalendarVersionView | undefined,
  draftResources: HouseholdResourceInput[],
) {
  if (!activeCalendar) {
    return {
      added: draftResources.map((value) => value.resource_id),
      removed: [] as string[],
      changed: [] as string[],
    };
  }
  const active = new Map(
    activeCalendar.resources.map((value) => [
      value.resource_id,
      resourceSignature({
        resource_id: value.resource_id,
        label: value.label,
        capacity: value.capacity,
        resource_kind: value.resource_kind,
        availability_windows: value.availability_windows,
        metadata: value.metadata,
      }),
    ]),
  );
  const draft = new Map(
    draftResources.map((value) => [value.resource_id, resourceSignature(value)]),
  );
  return {
    added: [...draft.keys()].filter((key) => !active.has(key)).sort(),
    removed: [...active.keys()].filter((key) => !draft.has(key)).sort(),
    changed: [...draft.keys()]
      .filter((key) => active.has(key) && active.get(key) !== draft.get(key))
      .sort(),
  };
}

export default function PreparationCalendarBuilderPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [selectedId, setSelectedId] = useState("");
  const [calendarVersion, setCalendarVersion] = useState("household-calendar-v1");
  const [horizonMinutes, setHorizonMinutes] = useState("240");
  const [timezone, setTimezone] = useState(
    () => Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
  );
  const [reviewedAt, setReviewedAt] = useState(() => {
    const date = new Date();
    date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
    return date.toISOString().slice(0, 16);
  });
  const [reviewedBy, setReviewedBy] = useState("");
  const [notes, setNotes] = useState("");
  const [resources, setResources] = useState<ResourceDraft[]>(() => [
    defaultResource("person", 240),
    defaultResource("burner", 240),
  ]);
  const [jsonDocument, setJsonDocument] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [checks, setChecks] = useState<ReviewChecks>({
    people: false,
    equipment: false,
    timezone: false,
    invalidation: false,
  });

  const householdsQ = useQuery({
    queryKey: ["households"],
    queryFn: householdApi.list,
  });
  const households = householdsQ.data ?? [];
  const householdId = selectedId || households[0]?.id || "";
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
  const activeCalendar = useMemo(
    () => (calendarsQ.data ?? []).find((value) => value.active),
    [calendarsQ.data],
  );
  const role = detailQ.data?.role;

  useEffect(() => {
    if (detailQ.data?.household.timezone) {
      setTimezone(detailQ.data.household.timezone);
    }
  }, [detailQ.data?.household.timezone]);

  const normalizedPreview = useMemo(() => {
    const horizon = Number(horizonMinutes);
    if (!Number.isInteger(horizon) || horizon < 1 || horizon > 10080) {
      return null;
    }
    try {
      return normalizeResources(resources, horizon);
    } catch {
      return null;
    }
  }, [horizonMinutes, resources]);

  const draftDocument = useMemo<CalendarDraftDocument | null>(() => {
    const horizon = Number(horizonMinutes);
    if (!normalizedPreview || !Number.isInteger(horizon)) return null;
    return {
      document_version: "preparation-resource-calendar-draft-v1",
      calendar_version: calendarVersion.trim(),
      horizon_minutes: horizon,
      timezone: timezone.trim(),
      notes: notes.trim() || null,
      resources: normalizedPreview,
    };
  }, [calendarVersion, horizonMinutes, normalizedPreview, notes, timezone]);

  const predecessorDiff = useMemo(
    () => diffResources(activeCalendar, normalizedPreview ?? []),
    [activeCalendar, normalizedPreview],
  );
  const reviewComplete = Object.values(checks).every(Boolean);

  const addResource = (template: TemplateName) => {
    const count = resources.filter((value) =>
      value.resource_id.startsWith(template),
    ).length;
    setResources((current) => [
      ...current,
      defaultResource(template, Number(horizonMinutes) || 240, count),
    ]);
  };

  const updateResource = (
    localResourceId: string,
    patch: Partial<ResourceDraft>,
  ) => {
    setResources((current) =>
      current.map((resource) =>
        resource.local_id === localResourceId
          ? { ...resource, ...patch }
          : resource,
      ),
    );
  };

  const updateWindow = (
    localResourceId: string,
    localWindowId: string,
    patch: Partial<WindowDraft>,
  ) => {
    setResources((current) =>
      current.map((resource) =>
        resource.local_id === localResourceId
          ? {
              ...resource,
              windows: resource.windows.map((window) =>
                window.local_id === localWindowId
                  ? { ...window, ...patch }
                  : window,
              ),
            }
          : resource,
      ),
    );
  };

  const createCalendar = useMutation({
    mutationFn: async () => {
      setFormError(null);
      if (role !== "owner") {
        throw new Error("Only the household owner can activate a reviewed calendar");
      }
      if (!reviewComplete) {
        throw new Error("Complete every review confirmation before activation");
      }
      const horizon = Number(horizonMinutes);
      if (!Number.isInteger(horizon) || horizon < 1 || horizon > 10080) {
        throw new Error("Horizon must be an integer from 1 to 10080 minutes");
      }
      if (!calendarVersion.trim()) throw new Error("Calendar version cannot be blank");
      if (!timezone.trim()) throw new Error("Timezone cannot be blank");
      if (!reviewedBy.trim()) throw new Error("Reviewer cannot be blank");
      const reviewDate = new Date(reviewedAt);
      if (Number.isNaN(reviewDate.getTime())) {
        throw new Error("Review time is invalid");
      }
      const payload: ResourceCalendarVersionCreate = {
        calendar_version: calendarVersion.trim(),
        horizon_minutes: horizon,
        timezone: timezone.trim(),
        resources: normalizeResources(resources, horizon),
        evidence_status: "reviewed",
        reviewed_at: reviewDate.toISOString(),
        reviewed_by: reviewedBy.trim(),
        notes: notes.trim() || null,
        activate: true,
        idempotency_key: `calendar-builder-${crypto.randomUUID()}`,
      };
      return preparationOperationsApi.createCalendar(householdId, payload);
    },
    onSuccess: async (calendar) => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["preparation-operations", householdId, "calendars"],
        }),
        queryClient.invalidateQueries({
          queryKey: ["preparation-operations", householdId, "coverage"],
        }),
        queryClient.invalidateQueries({
          queryKey: ["preparation-operations", householdId, "schedules"],
        }),
      ]);
      setChecks({ people: false, equipment: false, timezone: false, invalidation: false });
      toast({
        title: "Reviewed calendar activated",
        description: `${calendar.calendar_version} · ${calendar.resources.length} resources`,
      });
    },
    onError: (error) => {
      const message = messageOf(error);
      setFormError(message);
      toast({
        title: "Calendar activation failed",
        description: message,
        variant: "destructive",
      });
    },
  });

  const loadJson = () => {
    try {
      const document = parseDraftDocument(jsonDocument);
      const normalized = normalizeResources(
        document.resources.map(toResourceDraft),
        document.horizon_minutes,
      );
      setCalendarVersion(document.calendar_version);
      setHorizonMinutes(String(document.horizon_minutes));
      setTimezone(document.timezone);
      setNotes(document.notes ?? "");
      setResources(normalized.map(toResourceDraft));
      setFormError(null);
      toast({
        title: "Calendar draft loaded",
        description: `${normalized.length} structured resources imported`,
      });
    } catch (error) {
      const message = messageOf(error);
      setFormError(message);
      toast({
        title: "Calendar JSON rejected",
        description: message,
        variant: "destructive",
      });
    }
  };

  const pageError = householdsQ.error || detailQ.error || calendarsQ.error;

  return (
    <AppLayout>
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold">Reviewed resource calendar builder</h1>
            <p className="text-sm text-muted-foreground">
              Build explicit household availability windows, compare them with
              the active version, review the consequences, and activate one
              immutable calendar version.
            </p>
          </div>
          <Button asChild variant="outline">
            <Link to="/preparation/operations">Open operations workspace</Link>
          </Button>
        </div>

        <Alert>
          <ShieldCheck className="h-4 w-4" />
          <AlertTitle>Explicit declarations only</AlertTitle>
          <AlertDescription>
            NutriFlavorOS does not infer presence, appliance availability, or
            safe operating conditions. Activating a successor invalidates draft
            and approved schedules linked to the previous calendar; it does not
            create or approve replacements.
          </AlertDescription>
        </Alert>

        {(pageError || formError) && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Calendar builder needs attention</AlertTitle>
            <AlertDescription>{formError ?? messageOf(pageError)}</AlertDescription>
          </Alert>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Household and review identity</CardTitle>
            <CardDescription>
              Only the household owner can activate a reviewed version.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <div className="space-y-1 md:col-span-2">
              <Label htmlFor="calendar-builder-household">Household</Label>
              <select
                id="calendar-builder-household"
                value={householdId}
                onChange={(event) => setSelectedId(event.target.value)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                {households.map((household) => (
                  <option key={household.id} value={household.id}>
                    {household.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="calendar-builder-version">Calendar version</Label>
              <Input
                id="calendar-builder-version"
                value={calendarVersion}
                onChange={(event) => setCalendarVersion(event.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="calendar-builder-horizon">Horizon minutes</Label>
              <Input
                id="calendar-builder-horizon"
                type="number"
                min="1"
                max="10080"
                value={horizonMinutes}
                onChange={(event) => setHorizonMinutes(event.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="calendar-builder-timezone">Timezone</Label>
              <Input
                id="calendar-builder-timezone"
                value={timezone}
                onChange={(event) => setTimezone(event.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="calendar-builder-reviewed-at">Reviewed at</Label>
              <Input
                id="calendar-builder-reviewed-at"
                type="datetime-local"
                value={reviewedAt}
                onChange={(event) => setReviewedAt(event.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Displayed in {timezone || "the selected timezone"}: {formattedReviewTime(reviewedAt, timezone)}
              </p>
            </div>
            <div className="space-y-1">
              <Label htmlFor="calendar-builder-reviewed-by">Reviewed by</Label>
              <Input
                id="calendar-builder-reviewed-by"
                value={reviewedBy}
                onChange={(event) => setReviewedBy(event.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="calendar-builder-notes">Review notes</Label>
              <Input
                id="calendar-builder-notes"
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <CalendarClock className="h-4 w-4" />
              Structured resources and windows
            </CardTitle>
            <CardDescription>
              A preparation task must fit wholly inside one continuous window
              for every resource it demands.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2" aria-label="Resource templates">
              {(Object.keys(templates) as TemplateName[]).map((template) => (
                <Button
                  key={template}
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => addResource(template)}
                >
                  <CopyPlus className="mr-2 h-4 w-4" />
                  Add {template}
                </Button>
              ))}
            </div>

            {resources.map((resource, resourceIndex) => (
              <fieldset key={resource.local_id} className="space-y-4 rounded-lg border p-4">
                <legend className="px-2 text-sm font-medium">
                  Resource {resourceIndex + 1}
                </legend>
                <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-5">
                  <div className="space-y-1">
                    <Label htmlFor={`${resource.local_id}-id`}>Resource ID</Label>
                    <Input
                      id={`${resource.local_id}-id`}
                      value={resource.resource_id}
                      onChange={(event) =>
                        updateResource(resource.local_id, {
                          resource_id: event.target.value,
                        })
                      }
                    />
                  </div>
                  <div className="space-y-1 lg:col-span-2">
                    <Label htmlFor={`${resource.local_id}-label`}>Label</Label>
                    <Input
                      id={`${resource.local_id}-label`}
                      value={resource.label}
                      onChange={(event) =>
                        updateResource(resource.local_id, { label: event.target.value })
                      }
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor={`${resource.local_id}-kind`}>Kind</Label>
                    <Input
                      id={`${resource.local_id}-kind`}
                      value={resource.resource_kind}
                      onChange={(event) =>
                        updateResource(resource.local_id, {
                          resource_kind: event.target.value,
                        })
                      }
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor={`${resource.local_id}-capacity`}>Capacity</Label>
                    <Input
                      id={`${resource.local_id}-capacity`}
                      type="number"
                      min="1"
                      max="1000"
                      value={resource.capacity}
                      onChange={(event) =>
                        updateResource(resource.local_id, { capacity: event.target.value })
                      }
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-medium">Availability windows</p>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        updateResource(resource.local_id, {
                          windows: [
                            ...resource.windows,
                            {
                              local_id: localId(`window-${resource.resource_id || "custom"}`),
                              start_minute: "0",
                              end_minute: horizonMinutes,
                            },
                          ],
                        })
                      }
                    >
                      <Plus className="mr-2 h-4 w-4" />
                      Add window
                    </Button>
                  </div>
                  {resource.windows.map((window, windowIndex) => (
                    <div
                      key={window.local_id}
                      className="grid gap-3 rounded-md bg-muted/40 p-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end"
                    >
                      <div className="space-y-1">
                        <Label htmlFor={`${window.local_id}-start`}>
                          Window {windowIndex + 1} start minute
                        </Label>
                        <Input
                          id={`${window.local_id}-start`}
                          type="number"
                          min="0"
                          max={horizonMinutes}
                          value={window.start_minute}
                          onChange={(event) =>
                            updateWindow(resource.local_id, window.local_id, {
                              start_minute: event.target.value,
                            })
                          }
                        />
                      </div>
                      <div className="space-y-1">
                        <Label htmlFor={`${window.local_id}-end`}>
                          Window {windowIndex + 1} end minute
                        </Label>
                        <Input
                          id={`${window.local_id}-end`}
                          type="number"
                          min="1"
                          max={horizonMinutes}
                          value={window.end_minute}
                          onChange={(event) =>
                            updateWindow(resource.local_id, window.local_id, {
                              end_minute: event.target.value,
                            })
                          }
                        />
                      </div>
                      <Button
                        type="button"
                        size="icon"
                        variant="ghost"
                        aria-label={`Remove window ${windowIndex + 1} from ${resource.label || resource.resource_id}`}
                        onClick={() =>
                          updateResource(resource.local_id, {
                            windows: resource.windows.filter(
                              (value) => value.local_id !== window.local_id,
                            ),
                          })
                        }
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>

                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  onClick={() =>
                    setResources((current) =>
                      current.filter((value) => value.local_id !== resource.local_id),
                    )
                  }
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  Remove resource
                </Button>
              </fieldset>
            ))}
          </CardContent>
        </Card>

        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Predecessor diff</CardTitle>
              <CardDescription>
                Compared with {activeCalendar ? activeCalendar.calendar_version : "no active calendar"}.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">Added: {predecessorDiff.added.length}</Badge>
                <Badge variant="outline">Changed: {predecessorDiff.changed.length}</Badge>
                <Badge variant="outline">Removed: {predecessorDiff.removed.length}</Badge>
              </div>
              {(["added", "changed", "removed"] as const).map((kind) => (
                predecessorDiff[kind].length > 0 && (
                  <p key={kind}>
                    <span className="font-medium capitalize">{kind}:</span>{" "}
                    {predecessorDiff[kind].join(", ")}
                  </p>
                )
              ))}
              {!activeCalendar && (
                <p className="text-muted-foreground">
                  This will be the household's first active reviewed calendar.
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <FileJson2 className="h-4 w-4" />
                Canonical JSON import/export
              </CardTitle>
              <CardDescription>
                Export the structured draft for review or load a compatible
                draft. Import never activates a calendar.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={!draftDocument}
                  onClick={() =>
                    setJsonDocument(JSON.stringify(draftDocument, null, 2))
                  }
                >
                  Refresh JSON from builder
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={!jsonDocument.trim()}
                  onClick={loadJson}
                >
                  Load JSON into builder
                </Button>
              </div>
              <Label htmlFor="calendar-builder-json">Calendar draft JSON</Label>
              <Textarea
                id="calendar-builder-json"
                className="min-h-72 font-mono text-xs"
                value={jsonDocument}
                onChange={(event) => setJsonDocument(event.target.value)}
                placeholder="Refresh from the builder or paste a preparation-resource-calendar-draft-v1 document"
              />
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <ClipboardCheck className="h-4 w-4" />
              Human review and activation
            </CardTitle>
            <CardDescription>
              Every confirmation is required. Importing or editing data never
              checks these boxes automatically.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {([
              ["people", "I confirmed declared person availability with the household."],
              ["equipment", "I confirmed equipment/workspace availability and capacity."],
              ["timezone", `I confirmed the horizon and timezone (${timezone || "blank"}).`],
              ["invalidation", "I understand activation invalidates dependent draft and approved schedules on the predecessor."],
            ] as const).map(([key, label]) => (
              <div key={key} className="flex items-start gap-3">
                <Checkbox
                  id={`calendar-builder-check-${key}`}
                  checked={checks[key]}
                  onCheckedChange={(value) =>
                    setChecks((current) => ({ ...current, [key]: value === true }))
                  }
                />
                <Label htmlFor={`calendar-builder-check-${key}`} className="leading-5">
                  {label}
                </Label>
              </div>
            ))}

            <div className="rounded-md border bg-muted/30 p-3 text-sm">
              <p className="font-medium">Review timestamp preview</p>
              <p className="text-muted-foreground">
                {formattedReviewTime(reviewedAt, timezone)} · reviewer {reviewedBy || "not entered"}
              </p>
            </div>

            <Button
              type="button"
              disabled={
                role !== "owner"
                || !reviewComplete
                || createCalendar.isPending
                || !draftDocument
              }
              onClick={() => createCalendar.mutate()}
            >
              <CheckCircle2 className="mr-2 h-4 w-4" />
              Activate reviewed calendar version
            </Button>
            {role !== "owner" && (
              <p className="text-sm text-muted-foreground">
                Your household role is {role ?? "unavailable"}; owner access is required.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </AppLayout>
  );
}
