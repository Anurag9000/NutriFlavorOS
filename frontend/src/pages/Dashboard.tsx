import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/AppLayout";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { useAuth } from "@/contexts/AuthContext";
import { useGetMealPlan, useUserProfile } from "@/hooks/useApi";
import { householdApi } from "@/lib/platformApi";
import type { PlanResponse, Recipe } from "@/lib/api";
import { AlertCircle, CalendarDays, Home, PackageOpen, Target, UtensilsCrossed } from "lucide-react";
import { Link } from "react-router-dom";

function numberValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function sumPlan(plan?: PlanResponse) {
  if (!plan?.days?.length) {
    return { meals: 0, calories: 0, protein: 0, carbs: 0, fat: 0, cost: null as number | null };
  }
  let meals = 0;
  let calories = 0;
  let protein = 0;
  let carbs = 0;
  let fat = 0;
  let recipeCost = 0;
  let costObservations = 0;
  for (const day of plan.days) {
    for (const recipe of Object.values(day.meals ?? {}) as Recipe[]) {
      meals += 1;
      calories += recipe.calories || 0;
      protein += recipe.macros?.protein || 0;
      carbs += recipe.macros?.carbs || 0;
      fat += recipe.macros?.fat || 0;
      if (typeof recipe.estimated_cost === "number") {
        recipeCost += recipe.estimated_cost;
        costObservations += 1;
      }
    }
  }
  const reportedCost = numberValue(plan.overall_stats?.total_plan_cost);
  return {
    meals,
    calories,
    protein,
    carbs,
    fat,
    cost: reportedCost ?? (costObservations === meals && meals > 0 ? recipeCost : null),
  };
}

function formatNumber(value: number, maximumFractionDigits = 0): string {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits }).format(value);
}

function targetProgress(current: number, target?: number): number {
  if (!target || target <= 0) return 0;
  return Math.min(100, Math.round((current / target) * 100));
}

export default function Dashboard() {
  const { user } = useAuth();
  const userId = user?.id ?? "";
  const planQ = useGetMealPlan(userId);
  const profileQ = useUserProfile(user?.profileComplete ? userId : "");
  const householdsQ = useQuery({ queryKey: ["households"], queryFn: householdApi.list, enabled: Boolean(userId) });

  const plan = planQ.data;
  const totals = sumPlan(plan);
  const dayCount = plan?.days?.length ?? 0;
  const daily = {
    calories: dayCount ? totals.calories / dayCount : 0,
    protein: dayCount ? totals.protein / dayCount : 0,
    carbs: dayCount ? totals.carbs / dayCount : 0,
    fat: dayCount ? totals.fat / dayCount : 0,
  };
  const today = plan?.days?.[0];
  const warnings = plan?.warnings ?? [];
  const optimization = plan?.optimization;

  return (
    <AppLayout>
      <div className="mx-auto max-w-6xl space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-sm text-muted-foreground">Persisted plan and household state for {user?.name ?? "your account"}.</p>
        </div>

        {!user?.profileComplete && (
          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Complete your nutrition profile</AlertTitle>
            <AlertDescription className="space-y-3">
              <p>Planning is blocked until the required profile fields are supplied. NutriFlavorOS will not invent age, weight, height, sex, activity, or goal values.</p>
              {user?.missingProfileFields.length ? <p>Missing: {user.missingProfileFields.join(", ")}</p> : null}
              <Button asChild size="sm"><Link to="/settings?completeProfile=1">Complete profile</Link></Button>
            </AlertDescription>
          </Alert>
        )}

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Card><CardContent className="p-5"><div className="flex items-center gap-2 text-sm text-muted-foreground"><CalendarDays className="h-4 w-4" />Plan horizon</div><p className="mt-2 text-2xl font-bold">{dayCount} day{dayCount === 1 ? "" : "s"}</p><p className="text-xs text-muted-foreground">{totals.meals} persisted meal slots</p></CardContent></Card>
          <Card><CardContent className="p-5"><div className="flex items-center gap-2 text-sm text-muted-foreground"><Target className="h-4 w-4" />Average planned energy</div><p className="mt-2 text-2xl font-bold">{dayCount ? formatNumber(daily.calories) : "—"}</p><p className="text-xs text-muted-foreground">kcal per planned day</p></CardContent></Card>
          <Card><CardContent className="p-5"><div className="flex items-center gap-2 text-sm text-muted-foreground"><Home className="h-4 w-4" />Households</div><p className="mt-2 text-2xl font-bold">{householdsQ.data?.length ?? 0}</p><p className="text-xs text-muted-foreground">accessible household workspaces</p></CardContent></Card>
          <Card><CardContent className="p-5"><div className="flex items-center gap-2 text-sm text-muted-foreground"><PackageOpen className="h-4 w-4" />Plan cost evidence</div><p className="mt-2 text-2xl font-bold">{totals.cost === null ? "—" : formatNumber(totals.cost, 2)}</p><p className="text-xs text-muted-foreground">shown only when all required cost data exists</p></CardContent></Card>
        </div>

        {planQ.isError && (
          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>No compatible persisted plan</AlertTitle>
            <AlertDescription className="space-y-3">
              <p>{planQ.error instanceof Error ? planQ.error.message : "A plan has not been generated yet."}</p>
              {user?.profileComplete && <Button asChild size="sm"><Link to="/meals">Open meal planner</Link></Button>}
            </AlertDescription>
          </Alert>
        )}

        {plan && (
          <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
            <Card>
              <CardHeader><CardTitle className="flex items-center gap-2 text-base"><UtensilsCrossed className="h-4 w-4" />First planned day</CardTitle><CardDescription>Selections are planned quantities, not logged consumption.</CardDescription></CardHeader>
              <CardContent className="grid gap-3 sm:grid-cols-2">
                {Object.entries(today?.meals ?? {}).map(([slot, recipe]) => {
                  const portion = today?.portions?.[slot] ?? 1;
                  return (
                    <div key={slot} className="rounded-md border p-3">
                      <div className="flex items-start justify-between gap-2"><div><p className="text-xs uppercase tracking-wide text-muted-foreground">{slot.replaceAll("_", " ")}</p><p className="font-medium">{recipe.name}</p></div><Badge variant="outline">{portion}×</Badge></div>
                      <p className="mt-2 text-xs text-muted-foreground">{formatNumber(recipe.calories * portion)} kcal · P {formatNumber((recipe.macros?.protein ?? 0) * portion, 1)} g · C {formatNumber((recipe.macros?.carbs ?? 0) * portion, 1)} g · F {formatNumber((recipe.macros?.fat ?? 0) * portion, 1)} g</p>
                    </div>
                  );
                })}
              </CardContent>
            </Card>

            <div className="space-y-4">
              <Card>
                <CardHeader><CardTitle className="text-base">Average daily targets</CardTitle><CardDescription>Targets come from your persisted profile.</CardDescription></CardHeader>
                <CardContent className="space-y-4">
                  {[
                    ["Calories", daily.calories, profileQ.data?.target_calories, "kcal"],
                    ["Protein", daily.protein, profileQ.data?.target_protein_g, "g"],
                    ["Carbohydrate", daily.carbs, profileQ.data?.target_carbs_g, "g"],
                    ["Fat", daily.fat, profileQ.data?.target_fat_g, "g"],
                  ].map(([name, current, target, unit]) => (
                    <div key={String(name)}>
                      <div className="mb-1 flex justify-between gap-2 text-sm"><span>{name}</span><span className="text-muted-foreground">{formatNumber(Number(current), 1)}{unit} / {target ? `${formatNumber(Number(target))}${unit}` : "target unavailable"}</span></div>
                      <Progress value={targetProgress(Number(current), typeof target === "number" ? target : undefined)} />
                    </div>
                  ))}
                </CardContent>
              </Card>

              <Card>
                <CardHeader><CardTitle className="text-base">Optimizer provenance</CardTitle></CardHeader>
                <CardContent className="space-y-2 text-sm">
                  <p><span className="text-muted-foreground">Method:</span> {optimization?.method ?? "not reported"}</p>
                  <p><span className="text-muted-foreground">Deterministic:</span> {optimization ? (optimization.deterministic ? "yes" : "no") : "not reported"}</p>
                  <p><span className="text-muted-foreground">Objective score:</span> {optimization ? formatNumber(optimization.objective_score, 4) : "not reported"}</p>
                  {(optimization?.relaxations.length ?? 0) > 0 && <p><span className="text-muted-foreground">Disclosed relaxations:</span> {optimization?.relaxations.join(", ")}</p>}
                </CardContent>
              </Card>
            </div>
          </div>
        )}

        {warnings.length > 0 && (
          <Card>
            <CardHeader><CardTitle className="text-base">Plan warnings</CardTitle></CardHeader>
            <CardContent><ul className="list-disc space-y-1 pl-5 text-sm">{warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul></CardContent>
          </Card>
        )}
      </div>
    </AppLayout>
  );
}
