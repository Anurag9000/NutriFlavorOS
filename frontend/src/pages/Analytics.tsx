import AppLayout from "@/components/AppLayout";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/contexts/AuthContext";
import { useGetMealPlan, useUserProfile } from "@/hooks/useApi";
import type { Recipe } from "@/lib/api";
import { AlertCircle } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

function format(value: number, digits = 0): string {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: digits }).format(value);
}

export default function Analytics() {
  const { user } = useAuth();
  const userId = user?.id ?? "";
  const planQ = useGetMealPlan(userId);
  const profileQ = useUserProfile(userId);
  const plan = planQ.data;

  const dailyData = (plan?.days ?? []).map((day) => {
    let calories = 0;
    let protein = 0;
    let carbs = 0;
    let fat = 0;
    let meals = 0;
    for (const [slot, recipe] of Object.entries(day.meals ?? {}) as [string, Recipe][]) {
      const portion = day.portions?.[slot] ?? 1;
      calories += (recipe.calories || 0) * portion;
      protein += (recipe.macros?.protein ?? 0) * portion;
      carbs += (recipe.macros?.carbs ?? 0) * portion;
      fat += (recipe.macros?.fat ?? 0) * portion;
      meals += 1;
    }
    return { day: `Day ${day.day}`, calories, protein, carbs, fat, meals };
  });

  const totals = dailyData.reduce(
    (state, day) => ({
      calories: state.calories + day.calories,
      protein: state.protein + day.protein,
      carbs: state.carbs + day.carbs,
      fat: state.fat + day.fat,
      meals: state.meals + day.meals,
    }),
    { calories: 0, protein: 0, carbs: 0, fat: 0, meals: 0 },
  );
  const days = dailyData.length;
  const averages = {
    calories: days ? totals.calories / days : 0,
    protein: days ? totals.protein / days : 0,
    carbs: days ? totals.carbs / days : 0,
    fat: days ? totals.fat / days : 0,
  };

  const targetRows = [
    { name: "Calories", planned: averages.calories, target: profileQ.data?.target_calories ?? null, unit: "kcal" },
    { name: "Protein", planned: averages.protein, target: profileQ.data?.target_protein_g ?? null, unit: "g" },
    { name: "Carbohydrate", planned: averages.carbs, target: profileQ.data?.target_carbs_g ?? null, unit: "g" },
    { name: "Fat", planned: averages.fat, target: profileQ.data?.target_fat_g ?? null, unit: "g" },
  ];

  return (
    <AppLayout>
      <div className="mx-auto max-w-6xl space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Plan analytics</h1>
          <p className="text-sm text-muted-foreground">Descriptive statistics derived only from the persisted plan. They do not represent consumed food or predicted health outcomes.</p>
        </div>

        {(planQ.error || profileQ.error) && (
          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Some analytics inputs are unavailable</AlertTitle>
            <AlertDescription>{planQ.error instanceof Error ? planQ.error.message : profileQ.error instanceof Error ? profileQ.error.message : "No compatible plan or profile is available."}</AlertDescription>
          </Alert>
        )}

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          <Card><CardContent className="p-5"><p className="text-xs text-muted-foreground">Planned days</p><p className="text-2xl font-bold">{days}</p></CardContent></Card>
          <Card><CardContent className="p-5"><p className="text-xs text-muted-foreground">Meal slots</p><p className="text-2xl font-bold">{totals.meals}</p></CardContent></Card>
          <Card><CardContent className="p-5"><p className="text-xs text-muted-foreground">Average energy</p><p className="text-2xl font-bold">{days ? format(averages.calories) : "—"}</p><p className="text-xs text-muted-foreground">kcal / planned day</p></CardContent></Card>
          <Card><CardContent className="p-5"><p className="text-xs text-muted-foreground">Average protein</p><p className="text-2xl font-bold">{days ? format(averages.protein, 1) : "—"}</p><p className="text-xs text-muted-foreground">g / planned day</p></CardContent></Card>
          <Card><CardContent className="p-5"><p className="text-xs text-muted-foreground">Optimizer score</p><p className="text-2xl font-bold">{plan?.optimization ? format(plan.optimization.objective_score, 4) : "—"}</p><p className="text-xs text-muted-foreground">objective-specific, not a health score</p></CardContent></Card>
        </div>

        <Card>
          <CardHeader><CardTitle className="text-base">Planned energy by day</CardTitle><CardDescription>Portion-adjusted energy from recipe records.</CardDescription></CardHeader>
          <CardContent>
            {dailyData.length ? (
              <div className="h-72" aria-label="Line chart of planned calories by day">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={dailyData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="day" />
                    <YAxis />
                    <Tooltip />
                    <Line type="monotone" dataKey="calories" name="Planned kcal" stroke="currentColor" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : <p className="text-sm text-muted-foreground">Generate a persisted plan to view this chart.</p>}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Planned macronutrients by day</CardTitle><CardDescription>These values depend on source-recipe nutrition basis and portion multipliers.</CardDescription></CardHeader>
          <CardContent>
            {dailyData.length ? (
              <div className="h-80" aria-label="Bar chart of planned macronutrients by day">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={dailyData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="day" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="protein" name="Protein (g)" />
                    <Bar dataKey="carbs" name="Carbohydrate (g)" />
                    <Bar dataKey="fat" name="Fat (g)" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : <p className="text-sm text-muted-foreground">No plan data is available.</p>}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Average plan versus saved targets</CardTitle><CardDescription>Targets are displayed only when present in the persisted profile.</CardDescription></CardHeader>
          <CardContent className="space-y-3">
            {targetRows.map((row) => (
              <div key={row.name} className="grid gap-2 rounded-md border p-3 sm:grid-cols-[180px_1fr_1fr]">
                <span className="font-medium">{row.name}</span>
                <span><span className="text-xs text-muted-foreground">Planned average</span><br />{days ? `${format(row.planned, 1)} ${row.unit}` : "—"}</span>
                <span><span className="text-xs text-muted-foreground">Saved target</span><br />{row.target === null ? "Not available" : `${format(row.target)} ${row.unit}`}</span>
              </div>
            ))}
          </CardContent>
        </Card>

        {(plan?.optimization?.relaxations.length ?? 0) > 0 && (
          <Card>
            <CardHeader><CardTitle className="text-base">Disclosed optimizer relaxations</CardTitle></CardHeader>
            <CardContent><ul className="list-disc space-y-1 pl-5 text-sm">{plan?.optimization?.relaxations.map((value) => <li key={value}>{value}</li>)}</ul></CardContent>
          </Card>
        )}
      </div>
    </AppLayout>
  );
}
