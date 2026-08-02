import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CalendarCheck2,
  CheckCircle2,
  History,
  ShieldCheck,
  XCircle,
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  householdPlanApi,
  type HouseholdPlanEventType,
  type PersistedHouseholdPlanView,
} from "@/lib/householdPlanApi";
import { householdApi, type HouseholdRole } from "@/lib/platformApi";
import { useToast } from "@/hooks/use-toast";

function messageOf(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "The household plan request could not be completed";
}

function formatDate(value?: string | null): string {
  if (!value) return "Not recorded";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function canEdit(role?: HouseholdRole | null): boolean {
  return role === "owner" || role === "editor";
}

function transitionKey(action: HouseholdPlanEventType): string {
  return `household-plan-${action}-${crypto.randomUUID()}`;
}

export default function HouseholdPlanReviewPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [selectedId, setSelectedId] = useState("");
  const [reasons, setReasons] = useState<Record<number, string>>({});
  const [expandedPlanId, setExpandedPlanId] = useState<number | null>(null);

  const householdsQ = useQuery({
    queryKey: ["households"],
    queryFn: householdApi.list,
  });
  const households = householdsQ.data ?? [];
  const householdId = selectedId || households[0]?.id || "";

  useEffect(() => {
    setReasons({});
    setExpandedPlanId(null);
  }, [householdId]);

  const detailQ = useQuery({
    queryKey: ["households", householdId, "detail"],
    queryFn: () => householdApi.get(householdId),
    enabled: Boolean(householdId),
  });
  const plansQ = useQuery({
    queryKey: ["household-plans", householdId],
    queryFn: () => householdPlanApi.list(householdId),
    enabled: Boolean(householdId),
  });
  const eventsQ = useQuery({
    queryKey: ["household-plans", householdId, expandedPlanId, "events"],
    queryFn: () =>
      householdPlanApi.events(householdId, expandedPlanId as number),
    enabled: Boolean(householdId && expandedPlanId),
  });

  const role = detailQ.data?.role;
  const plans = plansQ.data ?? [];
  const counts = useMemo(
    () => ({
      draft: plans.filter((value) => value.status === "draft").length,
      approved: plans.filter((value) => value.status === "approved").length,
      cancelled: plans.filter((value) => value.status === "cancelled").length,
    }),
    [plans],
  );

  const transition = useMutation({
    mutationFn: ({
      plan,
      action,
    }: {
      plan: PersistedHouseholdPlanView;
      action: HouseholdPlanEventType;
    }) => {
      const reason = reasons[plan.id]?.trim();
      if (!reason) {
        throw new Error("Record a human review reason before changing plan state");
      }
      const payload = {
        expected_version: plan.version,
        reason,
        idempotency_key: transitionKey(action),
        metadata: { source: "household_plan_review_ui" },
      };
      return action === "approved"
        ? householdPlanApi.approve(householdId, plan.id, payload)
        : householdPlanApi.cancel(householdId, plan.id, payload);
    },
    onSuccess: async (plan) => {
      setReasons((current) => ({ ...current, [plan.id]: "" }));
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["household-plans", householdId],
        }),
        queryClient.invalidateQueries({
          queryKey: ["household-plans", householdId, plan.id, "events"],
        }),
        queryClient.invalidateQueries({
          queryKey: ["preparation-operations", householdId, "schedules"],
        }),
        queryClient.invalidateQueries({
          queryKey: ["preparation-operations", householdId, "coverage"],
        }),
        queryClient.invalidateQueries({
          queryKey: ["households", householdId, "reservations"],
        }),
      ]);
      toast({
        title: `Plan ${plan.status}`,
        description: `Plan #${plan.id} is now optimistic version ${plan.version}.`,
      });
    },
    onError: (error) =>
      toast({
        title: "Plan transition failed",
        description: messageOf(error),
        variant: "destructive",
      }),
  });

  const pageError = householdsQ.error || detailQ.error || plansQ.error;

  return (
    <AppLayout>
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold">Household plan review</h1>
            <p className="text-sm text-muted-foreground">
              Review persisted meal plans, approve an exact optimistic version,
              cancel obsolete work, and inspect append-only transition evidence.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline">
              <Link to="/meals">Generate a new plan</Link>
            </Button>
            <Button asChild variant="outline">
              <Link to="/preparation/operations">Preparation operations</Link>
            </Button>
          </div>
        </div>

        <Alert>
          <ShieldCheck className="h-4 w-4" />
          <AlertTitle>Approval is explicit household confirmation</AlertTitle>
          <AlertDescription>
            Approval records the exact plan version accepted by the household.
            It does not clinically validate nutrition, guarantee ingredient
            availability, certify allergy safety, or approve preparation
            automatically. Cancelling a plan releases active reservations and
            invalidates dependent draft or approved preparation schedules.
          </AlertDescription>
        </Alert>

        {pageError && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Plan review unavailable</AlertTitle>
            <AlertDescription>{messageOf(pageError)}</AlertDescription>
          </Alert>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Household scope</CardTitle>
            <CardDescription>
              Plans and decisions remain isolated to one authorized household.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-[1fr_auto] md:items-end">
            <div className="space-y-1">
              <Label htmlFor="plan-review-household">Household</Label>
              <select
                id="plan-review-household"
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
            <Badge variant="outline" className="w-fit capitalize">
              {role ?? "no role"}
            </Badge>
          </CardContent>
        </Card>

        <div className="grid gap-3 sm:grid-cols-3">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Draft plans</CardDescription>
              <CardTitle>{counts.draft}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Approved plans</CardDescription>
              <CardTitle>{counts.approved}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Cancelled plans</CardDescription>
              <CardTitle>{counts.cancelled}</CardTitle>
            </CardHeader>
          </Card>
        </div>

        {plans.map((plan) => (
          <Card key={plan.id}>
            <CardHeader>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <CalendarCheck2 className="h-4 w-4" />
                    Household plan #{plan.id}
                  </CardTitle>
                  <CardDescription>
                    Created {formatDate(plan.created_at)} · schema {plan.schema_version}
                    {" · "}optimistic version {plan.version}
                  </CardDescription>
                </div>
                <Badge
                  variant={plan.status === "approved" ? "default" : "secondary"}
                  className="capitalize"
                >
                  {plan.status}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {plan.status === "approved" && (
                <Alert>
                  <CheckCircle2 className="h-4 w-4" />
                  <AlertTitle>Eligible exact source plan</AlertTitle>
                  <AlertDescription>
                    Preparation occurrences may reference plan #{plan.id}, version {plan.version}.
                    Any later cancellation increments the version and invalidates dependent work.
                  </AlertDescription>
                </Alert>
              )}
              {plan.status === "cancelled" && (
                <Alert variant="destructive">
                  <XCircle className="h-4 w-4" />
                  <AlertTitle>Plan cancelled</AlertTitle>
                  <AlertDescription>
                    {plan.cancellation_reason ?? "No cancellation reason was retained"}
                    {" · "}{formatDate(plan.cancelled_at)}
                  </AlertDescription>
                </Alert>
              )}

              <div className="grid gap-3 lg:grid-cols-2">
                {plan.plan.days.map((day) => (
                  <div key={day.day} className="rounded-md border p-3">
                    <p className="mb-2 font-medium">Day {day.day}</p>
                    <div className="space-y-2">
                      {Object.entries(day.meals).map(([slot, recipe]) => (
                        <div
                          key={`${day.day}-${slot}`}
                          className="flex items-start justify-between gap-3 text-sm"
                        >
                          <div>
                            <p className="font-medium">{recipe.name}</p>
                            <p className="capitalize text-muted-foreground">{slot}</p>
                          </div>
                          <Badge variant="outline">
                            {day.portions[slot] ?? 1} portions
                          </Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>

              {plan.plan.warnings.length > 0 && (
                <div className="rounded-md border p-3 text-sm">
                  <p className="mb-2 font-medium">Planner warnings</p>
                  <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
                    {plan.plan.warnings.map((warning) => (
                      <li key={warning}>{warning}</li>
                    ))}
                  </ul>
                </div>
              )}

              {(plan.status === "draft" || plan.status === "approved")
                && canEdit(role) && (
                  <div className="space-y-3 border-t pt-4">
                    <div className="space-y-1">
                      <Label htmlFor={`plan-review-reason-${plan.id}`}>
                        Human decision reason
                      </Label>
                      <Input
                        id={`plan-review-reason-${plan.id}`}
                        value={reasons[plan.id] ?? ""}
                        onChange={(event) =>
                          setReasons((current) => ({
                            ...current,
                            [plan.id]: event.target.value,
                          }))
                        }
                        placeholder="Record what was reviewed and why this state is appropriate"
                      />
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {plan.status === "draft" && role === "owner" && (
                        <Button
                          type="button"
                          disabled={
                            transition.isPending || !(reasons[plan.id]?.trim())
                          }
                          onClick={() =>
                            transition.mutate({ plan, action: "approved" })
                          }
                        >
                          Approve exact plan version
                        </Button>
                      )}
                      <Button
                        type="button"
                        variant="outline"
                        disabled={
                          transition.isPending || !(reasons[plan.id]?.trim())
                        }
                        onClick={() =>
                          transition.mutate({ plan, action: "cancelled" })
                        }
                      >
                        Cancel plan
                      </Button>
                    </div>
                  </div>
                )}

              <div className="border-t pt-4">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    setExpandedPlanId((current) =>
                      current === plan.id ? null : plan.id,
                    )
                  }
                >
                  <History className="mr-2 h-4 w-4" />
                  {expandedPlanId === plan.id
                    ? "Hide transition history"
                    : "Load transition history"}
                </Button>
                {expandedPlanId === plan.id && (
                  <div className="mt-3 space-y-2" aria-live="polite">
                    {eventsQ.isLoading && (
                      <p className="text-sm text-muted-foreground">
                        Loading append-only plan events…
                      </p>
                    )}
                    {(eventsQ.data ?? []).map((event) => (
                      <div key={event.id} className="rounded-md border p-3 text-sm">
                        <div className="flex flex-wrap justify-between gap-2">
                          <span className="font-medium capitalize">
                            {event.event_type}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {formatDate(event.created_at)}
                          </span>
                        </div>
                        <p>
                          {event.from_status} → {event.to_status} · {event.reason}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          Actor {event.actor_user_id} · fingerprint {event.request_fingerprint}
                        </p>
                      </div>
                    ))}
                    {!eventsQ.isLoading && (eventsQ.data?.length ?? 0) === 0 && (
                      <p className="text-sm text-muted-foreground">
                        No approval or cancellation transition has been recorded.
                      </p>
                    )}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        ))}

        {!plansQ.isLoading && plans.length === 0 && householdId && (
          <p className="text-sm text-muted-foreground">
            No persisted household plans. Generate one in Meal Planner, then return for review.
          </p>
        )}
      </div>
    </AppLayout>
  );
}
