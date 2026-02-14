import AppLayout from "@/components/AppLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { pillarScores as mockPillarScores, dashboardMetrics as mockMetrics, todayMeals as mockMeals, achievements as mockAchievements } from "@/data/mockData";
import { Heart, Palette, Sparkles, Leaf, Flame, Zap, TrendingUp, Brain, TreePine, Droplets, Award } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { useHealthInsights, useSustainabilityData, useGamificationAchievements, useImpactSummary } from "@/hooks/useApi";

const pillarConfig = [
  { key: "health" as const, label: "Health", icon: Heart, color: "text-health", bg: "bg-health/10" },
  { key: "taste" as const, label: "Taste", icon: Palette, color: "text-taste", bg: "bg-taste/10" },
  { key: "variety" as const, label: "Variety", icon: Sparkles, color: "text-variety", bg: "bg-variety/10" },
  { key: "sustainability" as const, label: "Sustain.", icon: Leaf, color: "text-sustainability", bg: "bg-sustainability/10" },
];

const mealTypeLabels: Record<string, string> = { breakfast: "Breakfast", lunch: "Lunch", dinner: "Dinner", snack: "Snack" };

export default function Dashboard() {
  const { user } = useAuth();
  const userId = user?.id ?? "usr_1";

  // API calls — fall back to mock data on failure
  const healthQ = useHealthInsights(userId);
  const sustainQ = useSustainabilityData(userId);
  const achieveQ = useGamificationAchievements(userId);
  const impactQ = useImpactSummary(userId);

  // Derive pillar scores — use API average health score if available, else mock
  const healthAvg = healthQ.data
    ? Math.round(healthQ.data.reduce((s, d) => s + d.score, 0) / healthQ.data.length)
    : mockPillarScores.health;

  const pillarScores = {
    health: healthAvg,
    taste: mockPillarScores.taste, // taste comes from taste insights; keep mock for dashboard summary
    variety: mockPillarScores.variety,
    sustainability: mockPillarScores.sustainability,
  };

  const dashboardMetrics = mockMetrics; // calorie/protein targets stay from settings later
  const todayMeals = mockMeals;

  // Achievements — use API data if available
  const displayAchievements = achieveQ.data?.achievements
    ? achieveQ.data.achievements.filter((a: any) => a.unlocked !== false).slice(0, 3).map((a: any, i: number) => ({
      id: a.id ?? `ach_${i}`,
      title: a.name ?? a.title ?? "Achievement",
      icon: a.icon ?? "🏆",
      xp: a.xp ?? a.points ?? 100,
    }))
    : mockAchievements.filter((a) => a.unlocked).slice(0, 3);

  // Sustainability impact
  const sustain = sustainQ.data;
  const impact = impactQ.data;

  const caloriePercent = Math.round((dashboardMetrics.calories.current / dashboardMetrics.calories.target) * 100);

  return (
    <AppLayout>
      <div className="space-y-6 max-w-6xl mx-auto">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-muted-foreground text-sm">Your nutrition overview for today</p>
        </div>

        {/* Pillar Scores */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {pillarConfig.map((p) => (
            <Card key={p.key}>
              <CardContent className="p-5">
                <div className="flex items-center gap-3 mb-3">
                  <div className={`p-2 rounded-lg ${p.bg}`}>
                    <p.icon className={`h-4 w-4 ${p.color}`} />
                  </div>
                  <span className="text-sm font-medium">{p.label}</span>
                </div>
                <div className="text-3xl font-bold mb-2">{pillarScores[p.key]}%</div>
                <Progress value={pillarScores[p.key]} className="h-1.5" />
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Metrics Row */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-5 flex items-center gap-3">
              <div className="p-2 rounded-lg bg-taste/10"><Flame className="h-4 w-4 text-taste" /></div>
              <div>
                <p className="text-sm text-muted-foreground">Calories</p>
                <p className="text-xl font-bold">{dashboardMetrics.calories.current}<span className="text-sm font-normal text-muted-foreground">/{dashboardMetrics.calories.target}</span></p>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-5 flex items-center gap-3">
              <div className="p-2 rounded-lg bg-health/10"><Zap className="h-4 w-4 text-health" /></div>
              <div>
                <p className="text-sm text-muted-foreground">Protein</p>
                <p className="text-xl font-bold">{dashboardMetrics.protein.current}g<span className="text-sm font-normal text-muted-foreground">/{dashboardMetrics.protein.target}g</span></p>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-5 flex items-center gap-3">
              <div className="p-2 rounded-lg bg-variety/10"><TrendingUp className="h-4 w-4 text-variety" /></div>
              <div>
                <p className="text-sm text-muted-foreground">Streak</p>
                <p className="text-xl font-bold">{dashboardMetrics.streak} days</p>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-5 flex items-center gap-3">
              <div className="p-2 rounded-lg bg-sustainability/10"><TrendingUp className="h-4 w-4 text-sustainability" /></div>
              <div>
                <p className="text-sm text-muted-foreground">Weekly Score</p>
                <p className="text-xl font-bold">{dashboardMetrics.weeklyScore}%</p>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="grid lg:grid-cols-3 gap-6">
          {/* Today's Meals */}
          <div className="lg:col-span-2 space-y-4">
            <h2 className="text-lg font-semibold">Today's Meals</h2>
            <div className="grid sm:grid-cols-2 gap-4">
              {todayMeals.map((meal) => (
                <Card key={meal.id}>
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between mb-2">
                      <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{mealTypeLabels[meal.type]}</span>
                      <span className="text-xs text-muted-foreground">{meal.calories} cal</span>
                    </div>
                    <h3 className="font-medium mb-3">{meal.name}</h3>
                    <div className="flex gap-3 text-xs text-muted-foreground">
                      <span>P {meal.protein}g</span>
                      <span>C {meal.carbs}g</span>
                      <span>F {meal.fat}g</span>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>

          {/* AI Insight + Achievements + Sustainability */}
          <div className="space-y-4">
            <Card className="border-primary/20">
              <CardHeader className="pb-2">
                <div className="flex items-center gap-2">
                  <Brain className="h-4 w-4 text-primary" />
                  <CardTitle className="text-sm">AI Insight</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">Your protein intake has been consistently strong this week. Consider adding more leafy greens to boost your micronutrient variety score.</p>
              </CardContent>
            </Card>

            {/* Sustainability Impact Card */}
            {sustain && (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">Sustainability Impact</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-sustainability/10"><Leaf className="h-4 w-4 text-sustainability" /></div>
                    <div>
                      <p className="text-sm font-medium">{sustain.carbon_saved_kg} kg CO₂ saved</p>
                      <p className="text-xs text-muted-foreground">This month</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-blue-500/10"><Droplets className="h-4 w-4 text-blue-400" /></div>
                    <div>
                      <p className="text-sm font-medium">{sustain.water_saved_l}L water saved</p>
                      <p className="text-xs text-muted-foreground">{sustain.sustainable_meals_count} sustainable meals</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-health/10"><TreePine className="h-4 w-4 text-health" /></div>
                    <div>
                      <p className="text-sm font-medium">{sustain.trees_planted_equivalent} trees equivalent</p>
                      <p className="text-xs text-muted-foreground">Carbon offset</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Recent Achievements</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {displayAchievements.map((a: any) => (
                  <div key={a.id} className="flex items-center gap-3">
                    <span className="text-lg">{a.icon}</span>
                    <div>
                      <p className="text-sm font-medium">{a.title}</p>
                      <p className="text-xs text-muted-foreground">{a.xp} XP</p>
                    </div>
                  </div>
                ))}
                <Button variant="ghost" size="sm" className="w-full" asChild>
                  <Link to="/achievements">View All</Link>
                </Button>
              </CardContent>
            </Card>

            {/* Gamification Impact Summary */}
            {impact && (
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-center gap-2">
                    <Award className="h-4 w-4 text-taste" />
                    <CardTitle className="text-sm">Monthly Impact</CardTitle>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-3 text-center">
                    <div>
                      <p className="text-lg font-bold">{impact.total_meals_logged}</p>
                      <p className="text-xs text-muted-foreground">Meals Logged</p>
                    </div>
                    <div>
                      <p className="text-lg font-bold">{impact.average_health_score?.toFixed?.(0) ?? "—"}</p>
                      <p className="text-xs text-muted-foreground">Avg Health</p>
                    </div>
                    <div>
                      <p className="text-lg font-bold">{impact.total_carbon_saved?.toFixed?.(1) ?? "—"}</p>
                      <p className="text-xs text-muted-foreground">kg CO₂ Saved</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
