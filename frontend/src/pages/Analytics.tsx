import AppLayout from "@/components/AppLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, BarChart, Bar, RadarChart, PolarGrid, PolarAngleAxis,
  PolarRadiusAxis, Radar, LineChart, Line,
} from "recharts";
import { useAuth } from "@/contexts/AuthContext";
import { useHealthInsights, useTasteInsights, useVarietyInsights, useCarbonFootprint, useHealthPrediction, useGetMealPlan } from "@/hooks/useApi";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { TrendingUp, Leaf } from "lucide-react";

const chartTooltipStyle = {
  background: "hsl(228, 14%, 11%)",
  border: "1px solid hsl(228, 12%, 18%)",
  borderRadius: "8px",
  color: "#F8FAFC",
};

export default function Analytics() {
  const { user } = useAuth();
  const userId = user?.id ?? "usr_1";

  const healthQ = useHealthInsights(userId);
  const tasteQ = useTasteInsights(userId);
  const varietyQ = useVarietyInsights(userId);
  const carbonQ = useCarbonFootprint(userId);
  const mealPlanQ = useGetMealPlan(userId);

  const predictionMutation = useHealthPrediction();
  const [showPrediction, setShowPrediction] = useState(false);

  // Use API data only - NO HARDCODED FALLBACKS
  const healthData = healthQ.data ?? [];
  const tasteData = tasteQ.data ?? [];
  const varietyData = varietyQ.data ?? [];
  const carbonBreakdown = carbonQ.data;
  const mealPlan = mealPlanQ.data;

  // Calculate summary metrics from meal plan
  const calculateSummaryMetrics = () => {
    if (!mealPlan?.days || mealPlan.days.length === 0) {
      return { avgCalories: 0, avgProtein: 0, totalMeals: 0 };
    }

    let totalCalories = 0;
    let totalProtein = 0;
    let mealCount = 0;

    mealPlan.days.forEach(day => {
      if (day.meals) {
        Object.values(day.meals).forEach((meal: any) => {
          totalCalories += meal.calories || 0;
          totalProtein += meal.macros?.protein || 0;
          mealCount++;
        });
      }
    });

    return {
      avgCalories: mealCount > 0 ? Math.round(totalCalories / mealPlan.days.length) : 0,
      avgProtein: mealCount > 0 ? Math.round(totalProtein / mealPlan.days.length) : 0,
      totalMeals: mealCount,
    };
  };

  const summaryMetrics = calculateSummaryMetrics();

  // Calculate overall score from pillar scores
  const healthAvg = healthData.length > 0
    ? Math.round(healthData.reduce((s, d) => s + d.score, 0) / healthData.length)
    : 0;
  const tasteScore = tasteData.length > 0
    ? Math.round(tasteData.reduce((s, d) => s + (d.A || 0), 0) / tasteData.length / 1.5)
    : 0;
  const varietyScore = varietyData.length > 0
    ? Math.round(varietyData.reduce((s, d) => s + d.value, 0))
    : 0;
  const sustainScore = carbonBreakdown
    ? Math.min(100 - carbonBreakdown.average_meal_footprint * 10, 100)
    : 0;

  const overallScore = Math.round((healthAvg + tasteScore + varietyScore + sustainScore) / 4);
  const consistency = mealPlan?.days?.length === 7 ? 100 : Math.round((mealPlan?.days?.length || 0) / 7 * 100);

  // Calculate pillar data from API if available
  const pillarData = healthData.length > 0 ? [
    { name: "Health", value: healthAvg, color: "hsl(152, 60%, 48%)" },
    { name: "Taste", value: tasteScore, color: "hsl(38, 92%, 55%)" },
    { name: "Variety", value: varietyScore, color: "hsl(265, 60%, 58%)" },
    { name: "Sustain.", value: sustainScore, color: "hsl(174, 62%, 47%)" },
  ] : [];

  // Calculate macro distribution from meal plan
  const calculateMacroDistribution = () => {
    if (!mealPlan?.days || mealPlan.days.length === 0) return [];

    let totalProtein = 0;
    let totalCarbs = 0;
    let totalFat = 0;

    mealPlan.days.forEach(day => {
      if (day.meals) {
        Object.values(day.meals).forEach((meal: any) => {
          totalProtein += meal.macros?.protein || 0;
          totalCarbs += meal.macros?.carbs || 0;
          totalFat += meal.macros?.fat || 0;
        });
      }
    });

    const total = totalProtein + totalCarbs + totalFat;
    if (total === 0) return [];

    return [
      { name: "Protein", value: Math.round((totalProtein / total) * 100), color: "hsl(152, 60%, 48%)" },
      { name: "Carbs", value: Math.round((totalCarbs / total) * 100), color: "hsl(38, 92%, 55%)" },
      { name: "Fat", value: Math.round((totalFat / total) * 100), color: "hsl(265, 60%, 58%)" },
    ];
  };

  const macroDistribution = calculateMacroDistribution();

  const handlePredict = async () => {
    await predictionMutation.mutateAsync({ user_id: userId });
    setShowPrediction(true);
  };

  const prediction = predictionMutation.data;
  const varietyColors = ["hsl(152, 60%, 48%)", "hsl(38, 92%, 55%)", "hsl(265, 60%, 58%)", "hsl(174, 62%, 47%)", "hsl(340, 65%, 55%)"];


  return (
    <AppLayout>
      <div className="space-y-6 max-w-6xl mx-auto">
        <div>
          <h1 className="text-2xl font-bold">Analytics</h1>
          <p className="text-muted-foreground text-sm">Your nutrition performance over time</p>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <Card><CardContent className="p-5"><p className="text-sm text-muted-foreground">Avg Calories</p><p className="text-2xl font-bold">{summaryMetrics.avgCalories.toLocaleString()}</p><p className="text-xs text-muted-foreground">Per day</p></CardContent></Card>
          <Card><CardContent className="p-5"><p className="text-sm text-muted-foreground">Avg Protein</p><p className="text-2xl font-bold">{summaryMetrics.avgProtein}g</p><p className="text-xs text-muted-foreground">Per day</p></CardContent></Card>
          <Card><CardContent className="p-5"><p className="text-sm text-muted-foreground">Overall Score</p><p className="text-2xl font-bold">{overallScore}%</p><p className="text-xs text-muted-foreground">Avg of pillars</p></CardContent></Card>
          <Card><CardContent className="p-5"><p className="text-sm text-muted-foreground">Consistency</p><p className="text-2xl font-bold">{consistency}%</p><p className="text-xs text-muted-foreground">{consistency === 100 ? 'Excellent' : 'Good'}</p></CardContent></Card>
        </div>

        {/* Weekly Health Score Trend */}
        <Card>
          <CardHeader><CardTitle className="text-base">Health Score Trend</CardTitle></CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={healthData}>
                  <defs>
                    <linearGradient id="calGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="hsl(152, 60%, 48%)" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="hsl(152, 60%, 48%)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(228, 12%, 18%)" />
                  <XAxis dataKey="date" stroke="hsl(220, 10%, 55%)" fontSize={12} />
                  <YAxis stroke="hsl(220, 10%, 55%)" fontSize={12} />
                  <Tooltip contentStyle={chartTooltipStyle} itemStyle={{ color: "#F8FAFC" }} />
                  <Area type="monotone" dataKey="score" stroke="hsl(152, 60%, 48%)" fill="url(#calGrad)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <div className="grid lg:grid-cols-2 gap-6">
          {/* Taste Profile Radar */}
          <Card>
            <CardHeader><CardTitle className="text-base">Taste Profile</CardTitle></CardHeader>
            <CardContent>
              <div className="h-52">
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart data={tasteData}>
                    <PolarGrid stroke="hsl(228, 12%, 18%)" />
                    <PolarAngleAxis dataKey="subject" stroke="hsl(220, 10%, 55%)" fontSize={12} />
                    <PolarRadiusAxis stroke="hsl(220, 10%, 55%)" fontSize={10} />
                    <Radar name="Your Profile" dataKey="A" stroke="hsl(38, 92%, 55%)" fill="hsl(38, 92%, 55%)" fillOpacity={0.25} strokeWidth={2} />
                    <Tooltip contentStyle={chartTooltipStyle} itemStyle={{ color: "#F8FAFC" }} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          {/* Pillar Performance */}
          <Card>
            <CardHeader><CardTitle className="text-base">Pillar Performance</CardTitle></CardHeader>
            <CardContent>
              <div className="h-52">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={pillarData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(228, 12%, 18%)" />
                    <XAxis dataKey="name" stroke="hsl(220, 10%, 55%)" fontSize={12} />
                    <YAxis stroke="hsl(220, 10%, 55%)" fontSize={12} domain={[0, 100]} />
                    <Tooltip contentStyle={chartTooltipStyle} itemStyle={{ color: "#F8FAFC" }} cursor={{ fill: 'transparent' }} />
                    <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                      {pillarData.map((entry, i) => (<Cell key={i} fill={entry.color} />))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="grid lg:grid-cols-2 gap-6">
          {/* Variety Distribution */}
          <Card>
            <CardHeader><CardTitle className="text-base">Food Group Variety</CardTitle></CardHeader>
            <CardContent>
              <div className="h-52 flex items-center justify-center">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={varietyData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={4} dataKey="value">
                      {varietyData.map((_, i) => (<Cell key={i} fill={varietyColors[i % varietyColors.length]} />))}
                    </Pie>
                    <Tooltip contentStyle={chartTooltipStyle} itemStyle={{ color: "#F8FAFC" }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="flex flex-wrap justify-center gap-4 mt-2">
                {varietyData.map((m, i) => (
                  <div key={m.name} className="flex items-center gap-2 text-sm">
                    <div className="h-3 w-3 rounded-full" style={{ background: varietyColors[i % varietyColors.length] }} />
                    <span className="text-muted-foreground">{m.name} {m.value}%</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Macro Distribution */}
          <Card>
            <CardHeader><CardTitle className="text-base">Macro Distribution</CardTitle></CardHeader>
            <CardContent>
              <div className="h-52 flex items-center justify-center">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={macroDistribution} cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={4} dataKey="value">
                      {macroDistribution.map((entry, i) => (<Cell key={i} fill={entry.color} />))}
                    </Pie>
                    <Tooltip contentStyle={chartTooltipStyle} itemStyle={{ color: "#F8FAFC" }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="flex justify-center gap-6 mt-2">
                {macroDistribution.map((m) => (
                  <div key={m.name} className="flex items-center gap-2 text-sm">
                    <div className="h-3 w-3 rounded-full" style={{ background: m.color }} />
                    <span className="text-muted-foreground">{m.name} {m.value}%</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Carbon Footprint Breakdown */}
        {carbonBreakdown && (
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Leaf className="h-4 w-4 text-sustainability" />
                <CardTitle className="text-base">Carbon Footprint Breakdown</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-6 mb-4">
                <div>
                  <p className="text-2xl font-bold">{carbonBreakdown.total_footprint}</p>
                  <p className="text-xs text-muted-foreground">Total kg CO₂</p>
                </div>
                <div>
                  <p className="text-2xl font-bold">{carbonBreakdown.average_meal_footprint}</p>
                  <p className="text-xs text-muted-foreground">Avg per meal</p>
                </div>
              </div>
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={carbonBreakdown.breakdown} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(228, 12%, 18%)" />
                    <XAxis type="number" stroke="hsl(220, 10%, 55%)" fontSize={12} />
                    <YAxis dataKey="category" type="category" stroke="hsl(220, 10%, 55%)" fontSize={12} width={80} />
                    <Tooltip contentStyle={chartTooltipStyle} itemStyle={{ color: "#F8FAFC" }} cursor={{ fill: 'transparent' }} />
                    <Bar dataKey="value" fill="hsl(174, 62%, 47%)" radius={[0, 6, 6, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Health Prediction */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-health" />
              <CardTitle className="text-base">Health Score Prediction</CardTitle>
            </div>
            <Button size="sm" variant="outline" onClick={handlePredict} disabled={predictionMutation.isPending}>
              {predictionMutation.isPending ? "Predicting…" : "Predict 30 Days"}
            </Button>
          </CardHeader>
          <CardContent>
            {showPrediction && prediction ? (
              <div>
                <div className="flex gap-6 mb-4">
                  <div>
                    <p className="text-2xl font-bold text-muted-foreground">{prediction.current_score}</p>
                    <p className="text-xs text-muted-foreground">Current</p>
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-health">{prediction.predicted_score}</p>
                    <p className="text-xs text-muted-foreground">Predicted (30d)</p>
                  </div>
                </div>
                <div className="h-48">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={prediction.forecast}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(228, 12%, 18%)" />
                      <XAxis dataKey="day" stroke="hsl(220, 10%, 55%)" fontSize={12} label={{ value: "Day", position: "insideBottomRight", offset: -5 }} />
                      <YAxis stroke="hsl(220, 10%, 55%)" fontSize={12} domain={[70, 100]} />
                      <Tooltip contentStyle={chartTooltipStyle} itemStyle={{ color: "#F8FAFC" }} />
                      <Line type="monotone" dataKey="score" stroke="hsl(152, 60%, 48%)" strokeWidth={2} dot={{ r: 4 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Click "Predict 30 Days" to see your health score forecast based on current eating patterns.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </AppLayout>
  );
}
