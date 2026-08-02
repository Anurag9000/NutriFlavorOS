import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  FileJson2,
  ShieldCheck,
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
import {
  householdPlanApi,
  type ApprovedPlanOccurrenceCandidate,
  type DurationPolicy,
} from "@/lib/householdPlanApi";
import { householdApi, type HouseholdRole } from "@/lib/platformApi";
import { useToast } from "@/hooks/use-toast";

interface OccurrenceDraft {
  include: boolean;
  servings: string;
  requiredFinishMinute: string;
  priority: string;
}

function messageOf(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "Approved-plan occurrences could not be prepared";
}

function canEdit(role?: HouseholdRole | null): boolean {
  return role === "owner" || role === "editor";
}

function initialDraft(candidate: ApprovedPlanOccurrenceCandidate): OccurrenceDraft {
  return {
    include: candidate.preparation_profile_status === "reviewed_compatible",
    servings: String(candidate.planned_servings),
    requiredFinishMinute: "",
    priority: "0",
  };
}

function profileLabel(candidate: ApprovedPlanOccurrenceCandidate): string {
  if (candidate.preparation_profile_status === "reviewed_compatible") {
    return `Reviewed profile ${candidate.preparation_profile_version}`;
  }
  if (
    candidate.preparation_profile_status
    === "reviewed_incompatible_servings"
  ) {
    return "Reviewed profile incompatible with planned servings";
  }
  return "No active reviewed preparation profile";
}

export default function ApprovedPlanOccurrencesPage() {
  const { toast } = useToast();
  const [selectedHouseholdId, setSelectedHouseholdId] = useState("");
  const [selectedPlanId, setSelectedPlanId] = useState("");
  const [occurrenceSetVersion, setOccurrenceSetVersion] = useState("");
  const [durationPolicy, setDurationPolicy] = useState<DurationPolicy>(
    "conservative_max",
  );
  const [drafts, setDrafts] = useState<Record<string, OccurrenceDraft>>({});
  const [confirmedJson, setConfirmedJson] = useState("");

  const householdsQ = useQuery({
    queryKey: ["households"],
    queryFn: householdApi.list,
  });
  const households = householdsQ.data ?? [];
  const householdId = selectedHouseholdId || households[0]?.id || "";
  const detailQ = useQuery({
    queryKey: ["households", householdId, "detail"],
    queryFn: () => householdApi.get(householdId),
    enabled: Boolean(householdId),
  });
  const plansQ = useQuery({
    queryKey: ["household-plans", householdId, "approved"],
    queryFn: () => householdPlanApi.list(householdId, ["approved"]),
    enabled: Boolean(householdId),
  });
  const approvedPlans = plansQ.data ?? [];
  const plan = useMemo(() => {
    const requested = Number(selectedPlanId);
    return approvedPlans.find((value) => value.id === requested)
      ?? approvedPlans[0]
      ?? null;
  }, [approvedPlans, selectedPlanId]);

  useEffect(() => {
    setSelectedPlanId("");
    setDrafts({});
    setConfirmedJson("");
    setOccurrenceSetVersion("");
  }, [householdId]);

  useEffect(() => {
    setDrafts({});
    setConfirmedJson("");
    if (plan) {
      setOccurrenceSetVersion(
        `plan-${plan.id}-v${plan.version}-occurrences-v1`,
      );
    } else {
      setOccurrenceSetVersion("");
    }
  }, [plan?.id, plan?.version]);

  const candidatesQ = useQuery({
    queryKey: [
      "household-plans",
      householdId,
      plan?.id,
      plan?.version,
      "occurrence-candidates",
    ],
    queryFn: () =>
      householdPlanApi.occurrenceCandidates(
        householdId,
        plan!.id,
        plan!.version,
      ),
    enabled: Boolean(householdId && plan),
  });

  useEffect(() => {
    if (!candidatesQ.data) return;
    setDrafts(
      Object.fromEntries(
        candidatesQ.data.candidates.map((candidate) => [
          candidate.occurrence_id,
          initialDraft(candidate),
        ]),
      ),
    );
  }, [candidatesQ.data]);

  const role = detailQ.data?.role;
  const candidates = candidatesQ.data?.candidates ?? [];
  const includedCount = candidates.filter(
    (value) => drafts[value.occurrence_id]?.include,
  ).length;
  const confirmationReady = useMemo(() => {
    if (!plan || candidates.length === 0 || includedCount === 0) return false;
    if (!occurrenceSetVersion.trim()) return false;
    return candidates.every((candidate) => {
      const draft = drafts[candidate.occurrence_id];
      if (!draft) return false;
      if (!draft.include) return true;
      const servings = Number(draft.servings);
      const finish = Number(draft.requiredFinishMinute);
      const priority = Number(draft.priority);
      return (
        Number.isFinite(servings)
        && servings > 0
        && servings <= 1000
        && Number.isInteger(finish)
        && finish >= 1
        && finish <= 10080
        && Number.isInteger(priority)
        && priority >= -1000
        && priority <= 1000
      );
    });
  }, [
    candidates,
    drafts,
    includedCount,
    occurrenceSetVersion,
    plan,
  ]);

  const confirm = useMutation({
    mutationFn: () => {
      if (!plan) throw new Error("Select an approved household plan");
      if (!confirmationReady) {
        throw new Error(
          "Every included occurrence needs valid servings, finish minute, and priority",
        );
      }
      return householdPlanApi.confirmOccurrences(householdId, plan.id, {
        expected_plan_version: plan.version,
        occurrence_set_version: occurrenceSetVersion.trim(),
        duration_policy: durationPolicy,
        confirmations: candidates.map((candidate) => {
          const draft = drafts[candidate.occurrence_id];
          return {
            occurrence_id: candidate.occurrence_id,
            include: draft.include,
            servings: draft.include ? Number(draft.servings) : null,
            required_finish_minute: draft.include
              ? Number(draft.requiredFinishMinute)
              : null,
            priority: Number(draft.priority || 0),
          };
        }),
      });
    },
    onSuccess: (value) => {
      setConfirmedJson(JSON.stringify(value, null, 2));
      toast({
        title: "Occurrence document confirmed",
        description: `${value.confirmed_count} included · ${value.excluded_count} explicitly excluded. Nothing was persisted.`,
      });
    },
    onError: (error) =>
      toast({
        title: "Occurrence confirmation failed",
        description: messageOf(error),
        variant: "destructive",
      }),
  });

  const pageError =
    householdsQ.error || detailQ.error || plansQ.error || candidatesQ.error;

  return (
    <AppLayout>
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold">
              Approved-plan preparation occurrences
            </h1>
            <p className="text-sm text-muted-foreground">
              Derive meal identities from an exact approved plan, then explicitly
              confirm inclusion, servings, deadlines, priority, and duration policy.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline">
              <Link to="/household/plans">Plan review</Link>
            </Button>
            <Button asChild variant="outline">
              <Link to="/preparation/pipeline">Reviewed prep pipeline</Link>
            </Button>
          </div>
        </div>

        <Alert>
          <ShieldCheck className="h-4 w-4" />
          <AlertTitle>No deadline inference or automatic persistence</AlertTitle>
          <AlertDescription>
            Meal-slot names are not converted into times. Required finish minutes
            must be entered explicitly. Confirmation returns a canonical document
            and reviewed profile map; it does not persist, schedule, or approve work.
          </AlertDescription>
        </Alert>

        {pageError && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Occurrence workflow unavailable</AlertTitle>
            <AlertDescription>{messageOf(pageError)}</AlertDescription>
          </Alert>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Approved source plan</CardTitle>
            <CardDescription>
              Only currently approved exact plan versions are listed.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="occurrence-household">Household</Label>
              <select
                id="occurrence-household"
                value={householdId}
                onChange={(event) =>
                  setSelectedHouseholdId(event.target.value)
                }
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
              <Label htmlFor="occurrence-plan">Approved plan</Label>
              <select
                id="occurrence-plan"
                value={plan?.id ?? ""}
                onChange={(event) => setSelectedPlanId(event.target.value)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                {approvedPlans.map((value) => (
                  <option key={value.id} value={value.id}>
                    Plan #{value.id} · version {value.version} · approved {value.approved_at ?? "time unavailable"}
                  </option>
                ))}
              </select>
            </div>
            <div className="md:col-span-2 flex flex-wrap gap-2">
              <Badge variant="outline" className="capitalize">
                {role ?? "no role"}
              </Badge>
              {plan && (
                <Badge>
                  Source plan #{plan.id} · exact version {plan.version}
                </Badge>
              )}
            </div>
          </CardContent>
        </Card>

        {!plansQ.isLoading && approvedPlans.length === 0 && householdId && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>No approved household plan</AlertTitle>
            <AlertDescription>
              Generate and explicitly approve a household plan before deriving
              preparation occurrences.
            </AlertDescription>
          </Alert>
        )}

        {candidatesQ.data && (
          <>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <ClipboardCheck className="h-4 w-4" />
                  Confirm every planned meal
                </CardTitle>
                <CardDescription>
                  Compatible meals are included by default. Missing or incompatible
                  profiles are explicitly excluded by default and may not be included
                  until reviewed evidence supports the confirmed serving count.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline">
                    {candidatesQ.data.reviewed_compatible_count} compatible
                  </Badge>
                  <Badge
                    variant={
                      candidatesQ.data.unresolved_profile_count > 0
                        ? "destructive"
                        : "outline"
                    }
                  >
                    {candidatesQ.data.unresolved_profile_count} unresolved profile
                  </Badge>
                  <Badge variant="outline">{includedCount} included</Badge>
                </div>

                {candidates.map((candidate) => {
                  const draft = drafts[candidate.occurrence_id]
                    ?? initialDraft(candidate);
                  return (
                    <fieldset
                      key={candidate.occurrence_id}
                      className="space-y-4 rounded-lg border p-4"
                    >
                      <legend className="px-2 text-sm font-medium">
                        Day {candidate.day} · {candidate.meal_slot}
                      </legend>
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="font-medium">{candidate.recipe_name}</p>
                          <p className="text-xs text-muted-foreground">
                            Recipe {candidate.recipe_id} · occurrence {candidate.occurrence_id}
                          </p>
                          <p className="mt-1 text-sm text-muted-foreground">
                            Source recipe yield {candidate.source_recipe_servings} servings · planned {candidate.planned_servings} servings · batch scale {candidate.recipe_batch_scale.toFixed(3)}×
                          </p>
                        </div>
                        <Badge
                          variant={
                            candidate.preparation_profile_status
                              === "reviewed_compatible"
                              ? "default"
                              : "destructive"
                          }
                        >
                          {profileLabel(candidate)}
                        </Badge>
                      </div>

                      {candidate.supported_servings_min !== null && (
                        <p className="text-xs text-muted-foreground">
                          Reviewed serving range {candidate.supported_servings_min}–{candidate.supported_servings_max}; profile hash {candidate.preparation_profile_content_hash}
                        </p>
                      )}

                      <div className="flex items-center gap-3">
                        <Checkbox
                          id={`${candidate.occurrence_id}-include`}
                          checked={draft.include}
                          onCheckedChange={(value) =>
                            setDrafts((current) => ({
                              ...current,
                              [candidate.occurrence_id]: {
                                ...draft,
                                include: value === true,
                              },
                            }))
                          }
                        />
                        <Label htmlFor={`${candidate.occurrence_id}-include`}>
                          Include this occurrence
                        </Label>
                      </div>

                      <div className="grid gap-3 md:grid-cols-3">
                        <div className="space-y-1">
                          <Label htmlFor={`${candidate.occurrence_id}-servings`}>
                            Confirmed servings
                          </Label>
                          <Input
                            id={`${candidate.occurrence_id}-servings`}
                            type="number"
                            min="0.01"
                            max="1000"
                            step="0.01"
                            disabled={!draft.include}
                            value={draft.servings}
                            onChange={(event) =>
                              setDrafts((current) => ({
                                ...current,
                                [candidate.occurrence_id]: {
                                  ...draft,
                                  servings: event.target.value,
                                },
                              }))
                            }
                          />
                        </div>
                        <div className="space-y-1">
                          <Label htmlFor={`${candidate.occurrence_id}-finish`}>
                            Required finish minute
                          </Label>
                          <Input
                            id={`${candidate.occurrence_id}-finish`}
                            type="number"
                            min="1"
                            max="10080"
                            step="1"
                            disabled={!draft.include}
                            value={draft.requiredFinishMinute}
                            onChange={(event) =>
                              setDrafts((current) => ({
                                ...current,
                                [candidate.occurrence_id]: {
                                  ...draft,
                                  requiredFinishMinute: event.target.value,
                                },
                              }))
                            }
                            placeholder="Explicit horizon minute"
                          />
                        </div>
                        <div className="space-y-1">
                          <Label htmlFor={`${candidate.occurrence_id}-priority`}>
                            Priority
                          </Label>
                          <Input
                            id={`${candidate.occurrence_id}-priority`}
                            type="number"
                            min="-1000"
                            max="1000"
                            step="1"
                            value={draft.priority}
                            onChange={(event) =>
                              setDrafts((current) => ({
                                ...current,
                                [candidate.occurrence_id]: {
                                  ...draft,
                                  priority: event.target.value,
                                },
                              }))
                            }
                          />
                        </div>
                      </div>
                    </fieldset>
                  );
                })}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Occurrence document settings</CardTitle>
                <CardDescription>
                  Version and duration policy are retained in the canonical document.
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-3 md:grid-cols-2">
                <div className="space-y-1">
                  <Label htmlFor="occurrence-set-version">
                    Occurrence-set version
                  </Label>
                  <Input
                    id="occurrence-set-version"
                    value={occurrenceSetVersion}
                    onChange={(event) =>
                      setOccurrenceSetVersion(event.target.value)
                    }
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="duration-policy">Duration policy</Label>
                  <select
                    id="duration-policy"
                    value={durationPolicy}
                    onChange={(event) =>
                      setDurationPolicy(event.target.value as DurationPolicy)
                    }
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  >
                    <option value="conservative_max">Conservative maximum</option>
                    <option value="optimistic_min">Optimistic minimum</option>
                  </select>
                </div>
                <div className="md:col-span-2">
                  <Button
                    type="button"
                    disabled={
                      !canEdit(role)
                      || !confirmationReady
                      || confirm.isPending
                    }
                    onClick={() => confirm.mutate()}
                  >
                    <CheckCircle2 className="mr-2 h-4 w-4" />
                    Confirm canonical occurrence document
                  </Button>
                  {!canEdit(role) && (
                    <p className="mt-2 text-sm text-muted-foreground">
                      Editor or owner access is required to confirm occurrences.
                    </p>
                  )}
                </div>
              </CardContent>
            </Card>
          </>
        )}

        {confirmedJson && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <FileJson2 className="h-4 w-4" />
                Confirmed non-persisted output
              </CardTitle>
              <CardDescription>
                Inspect this exact occurrence document and profile map before
                passing them to the reviewed preparation pipeline.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <Label htmlFor="confirmed-occurrence-json">
                Confirmed occurrence bundle JSON
              </Label>
              <Textarea
                id="confirmed-occurrence-json"
                className="min-h-[28rem] font-mono text-xs"
                value={confirmedJson}
                readOnly
              />
            </CardContent>
          </Card>
        )}
      </div>
    </AppLayout>
  );
}
