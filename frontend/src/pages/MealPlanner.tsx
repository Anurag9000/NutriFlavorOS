import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import AppLayout from "@/components/AppLayout";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/contexts/AuthContext";
import { useGenerateMealPlan, useGetMealPlan, useUserProfile } from "@/hooks/useApi";
import { useToast } from "@/hooks/use-toast";
import type { PlanResponse, Recipe } from "@/lib/api";
import { AlertCircle, ChefHat, RefreshCw, ShoppingBasket } from "lucide-react";

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "The request could not be completed";
}

function format(value: number, digits = 0): string {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: digits }).format(value);
}

function dayLabel(day: number): string {
  return `Day ${day}`;
}

export default function MealPlanner() {
  const { user } = useAuth();
  const userId = user?.id ?? "";
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [selectedDay, setSelectedDay] = useState(0);

  const profileQ = useUserProfile(userId);
  const planQ = useGetMealPlan(userId);
  const generatePlan = useGenerateMealPlan();

  const plan = planQ.data;
  const day = plan?.days?.[selectedDay];

  const handleGenerate = async () => {
    if (!profileQ.data) {
      toast({ title: "Profile unavailable", description: "Complete and save the required profile fields before generating a plan.", variant: "destructive" });
      return;
    }
    try {
      const generated = await generatePlan.mutateAsync(profileQ.data);
      queryClient.setQueryData<PlanResponse>(["mealPlan", userId], generated);
      setSelectedDay(0);
      toast({ title: "Plan generated", description: `${generated.days.length} planned day(s) persisted by the backend.` });
    } catch (error) {
      toast({ title: "Plan generation failed", description: messageOf(error), variant: "destructive" });
    }
  };

  const shoppingGroups = Object.entries(plan?.shopping_list ?? {});

  return (
    <AppLayout>
      <div className="mx-auto max-w-6xl space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold">Meal planner</h1>
            <p className="text-sm text-muted-foreground">Deterministic, persisted planning using your saved profile and explicit recipe evidence.</p>
          </div>
          <Button type="button" onClick={handleGenerate} disabled={generatePlan.isPending || profileQ.isLoading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${generatePlan.isPending ? "animate-spin" : ""}`} />
            {generatePlan.isPending ? "Generating…" : plan ? "Regenerate plan" : "Generate plan"}
          </Button>
        </div>

        {profileQ.error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Profile is incomplete or unavailable</AlertTitle>
            <AlertDescription>{messageOf(profileQ.error)}</AlertDescription>
          </Alert>
        )}

        {planQ.isLoading && <p className="text-sm text-muted-foreground" aria-live="polite">Loading persisted plan…</p>}
        {planQ.error && !plan && (
          <Alert>
            <ChefHat className="h-4 w-4" />
            <AlertTitle>No compatible plan is stored</AlertTitle>
            <AlertDescription>{messageOf(planQ.error)} Generate a plan only after reviewing your profile inputs.</AlertDescription>
          </Alert>
        )}

        {plan && (
          <>
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Planning provenance</CardTitle>
                <CardDescription>Plan selections are planned intake, not observed consumption or clinical outcomes.</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div><p className="text-xs text-muted-foreground">Method</p><p className="font-medium">{plan.optimization?.method ?? "not reported"}</p></div>
                <div><p className="text-xs text-muted-foreground">Objective score</p><p className="font-medium">{plan.optimization ? format(plan.optimization.objective_score, 4) : "not reported"}</p></div>
                <div><p className="text-xs text-muted-foreground">Candidate recipes</p><p className="font-medium">{plan.optimization?.candidate_count ?? "not reported"}</p></div>
                <div><p className="text-xs text-muted-foreground">Deterministic</p><p className="font-medium">{plan.optimization ? (plan.optimization.deterministic ? "yes" : "no") : "not reported"}</p></div>
              </CardContent>
            </Card>

            <div className="flex gap-2 overflow-x-auto pb-2" role="tablist" aria-label="Plan days">
              {plan.days.map((value, index) => (
                <button
                  type="button"
                  role="tab"
                  aria-selected={selectedDay === index}
                  key={value.day}
                  onClick={() => setSelectedDay(index)}
                  className={`whitespace-nowrap rounded-md border px-4 py-2 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${selectedDay === index ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card"}`}
                >
                  {dayLabel(value.day)}
                </button>
              ))}
            </div>

            {day && (
              <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
                <Card>
                  <CardHeader><CardTitle className="text-base">{dayLabel(day.day)} selections</CardTitle><CardDescription>Portion multipliers are applied to the source recipe's declared nutrition basis.</CardDescription></CardHeader>
                  <CardContent className="grid gap-3 sm:grid-cols-2">
                    {Object.entries(day.meals).map(([slot, recipe]: [string, Recipe]) => {
                      const portion = day.portions?.[slot] ?? 1;
                      return (
                        <article key={slot} className="rounded-md border p-4">
                          <div className="flex items-start justify-between gap-3">
                            <div><p className="text-xs uppercase tracking-wide text-muted-foreground">{slot.replaceAll("_", " ")}</p><h2 className="font-semibold">{recipe.name}</h2></div>
                            <Badge variant="outline">{portion}× portion</Badge>
                          </div>
                          <dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
                            <div><dt className="text-xs text-muted-foreground">Energy</dt><dd>{format(recipe.calories * portion)} kcal</dd></div>
                            <div><dt className="text-xs text-muted-foreground">Protein</dt><dd>{format((recipe.macros?.protein ?? 0) * portion, 1)} g</dd></div>
                            <div><dt className="text-xs text-muted-foreground">Carbohydrate</dt><dd>{format((recipe.macros?.carbs ?? 0) * portion, 1)} g</dd></div>
                            <div><dt className="text-xs text-muted-foreground">Fat</dt><dd>{format((recipe.macros?.fat ?? 0) * portion, 1)} g</dd></div>
                          </dl>
                          <p className="mt-3 text-xs text-muted-foreground">Basis: {recipe.nutrition_basis ?? "unknown"}{recipe.source_name ? ` · source ${recipe.source_name}` : ""}</p>
                        </article>
                      );
                    })}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader><CardTitle className="text-base">Daily totals</CardTitle></CardHeader>
                  <CardContent className="space-y-3 text-sm">
                    {Object.entries(day.total_stats ?? {}).map(([key, value]) => (
                      <div key={key} className="flex justify-between gap-3 border-b pb-2 last:border-0"><span className="capitalize text-muted-foreground">{key.replaceAll("_", " ")}</span><span>{typeof value === "number" ? format(value, 2) : String(value)}</span></div>
                    ))}
                    {Object.keys(day.total_stats ?? {}).length === 0 && <p className="text-muted-foreground">No aggregate statistics were reported.</p>}
                  </CardContent>
                </Card>
              </div>
            )}

            <Card>
              <CardHeader><CardTitle className="flex items-center gap-2 text-base"><ShoppingBasket className="h-4 w-4" />Serving-scaled shopping requirements</CardTitle><CardDescription>Only compatible units are combined. Partial and unquantified items remain explicit.</CardDescription></CardHeader>
              <CardContent className="space-y-5">
                {shoppingGroups.map(([group, items]) => (
                  <section key={group}>
                    <h2 className="mb-2 font-medium capitalize">{group.replaceAll("_", " ")}</h2>
                    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                      {Object.entries(items).map(([key, item]) => (
                        <div key={key} className="rounded-md border p-3 text-sm">
                          <div className="flex items-start justify-between gap-2"><span className="font-medium">{item.display_name}</span><Badge variant="outline">{item.quantity_status}</Badge></div>
                          <p className="mt-1">{item.quantity}</p>
                          <p className="mt-1 text-xs text-muted-foreground">{item.occurrences} occurrence(s); {item.source_recipe_ids.length} source recipe(s)</p>
                        </div>
                      ))}
                    </div>
                  </section>
                ))}
                {shoppingGroups.length === 0 && <p className="text-sm text-muted-foreground">No shopping requirements were returned.</p>}
              </CardContent>
            </Card>

            {(plan.warnings?.length ?? 0) > 0 && (
              <Alert>
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Plan warnings</AlertTitle>
                <AlertDescription><ul className="list-disc space-y-1 pl-5">{plan.warnings?.map((warning) => <li key={warning}>{warning}</li>)}</ul></AlertDescription>
              </Alert>
            )}
          </>
        )}
      </div>
    </AppLayout>
  );
}
