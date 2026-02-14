import AppLayout from "@/components/AppLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { achievements as mockAchievements, userStats } from "@/data/mockData";
import { Lock, Trophy, Medal, Crown, TrendingUp, Leaf } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { useGamificationAchievements, useLeaderboard, useUserRank, useImpactSummary } from "@/hooks/useApi";
import { useState } from "react";

const categoryLabels: Record<string, string> = {
  consistency: "Consistency",
  diversity: "Diversity",
  sustainability: "Sustainability",
  milestone: "Milestones",
};
const cats = Object.keys(categoryLabels);

const leaderboardTypes = [
  { key: "carbon_saved", label: "Carbon Saved" },
  { key: "health_score", label: "Health Score" },
  { key: "variety_score", label: "Variety Score" },
];

export default function Achievements() {
  const { user } = useAuth();
  const userId = user?.id ?? "usr_1";

  const [lbType, setLbType] = useState("carbon_saved");

  const achieveQ = useGamificationAchievements(userId);
  const leaderboardQ = useLeaderboard(lbType, "month", 10);
  const rankQ = useUserRank(userId, lbType);
  const impactQ = useImpactSummary(userId);

  // Use API achievements if available, else mock
  const achievements = achieveQ.data?.achievements
    ? (achieveQ.data.achievements as any[]).map((a: any, i: number) => ({
      id: a.id ?? `ach_${i}`,
      title: a.name ?? a.title ?? "Achievement",
      description: a.description ?? "",
      category: a.category ?? "milestone",
      progress: a.progress ?? (a.unlocked ? 100 : 0),
      unlocked: a.unlocked ?? false,
      icon: a.icon ?? "🏆",
      xp: a.xp ?? a.points ?? 100,
    }))
    : mockAchievements;

  const totalEarned = achieveQ.data?.total_earned ?? userStats.unlockedAchievements;
  const leaderboard = leaderboardQ.data?.leaderboard ?? [];
  const userRank = rankQ.data as any;
  const impact = impactQ.data;

  return (
    <AppLayout>
      <div className="space-y-6 max-w-5xl mx-auto">
        <div>
          <h1 className="text-2xl font-bold">Achievements</h1>
          <p className="text-muted-foreground text-sm">Track your progress and earn rewards</p>
        </div>

        {/* Level Bar */}
        <Card>
          <CardContent className="p-5">
            <div className="flex items-center justify-between mb-2">
              <span className="font-semibold">Level {userStats.level}</span>
              <span className="text-sm text-muted-foreground">{userStats.currentXP} / {userStats.nextLevelXP} XP</span>
            </div>
            <Progress value={(userStats.currentXP / userStats.nextLevelXP) * 100} className="h-2" />
            <p className="text-xs text-muted-foreground mt-2">{totalEarned} of {achievements.length} achievements unlocked</p>
          </CardContent>
        </Card>

        <div className="grid lg:grid-cols-3 gap-6">
          {/* Left: Achievements */}
          <div className="lg:col-span-2 space-y-6">
            {cats.map((cat) => {
              const items = achievements.filter((a: any) => a.category === cat);
              if (!items.length) return null;
              return (
                <div key={cat}>
                  <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">{categoryLabels[cat]}</h2>
                  <div className="grid sm:grid-cols-2 gap-4">
                    {items.map((a: any) => (
                      <Card key={a.id} className={`relative ${!a.unlocked ? "opacity-70" : ""}`}>
                        <CardContent className="p-5">
                          <div className="flex items-start gap-3">
                            <span className="text-2xl">{a.icon}</span>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <h3 className="font-medium text-sm">{a.title}</h3>
                                {!a.unlocked && <Lock className="h-3 w-3 text-muted-foreground" />}
                              </div>
                              <p className="text-xs text-muted-foreground mb-2">{a.description}</p>
                              <div className="flex items-center gap-2">
                                <Progress value={a.progress} className="h-1.5 flex-1" />
                                <span className="text-xs text-muted-foreground">{a.progress}%</span>
                              </div>
                              <p className="text-xs text-muted-foreground mt-1">{a.xp} XP</p>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Right: Leaderboard + Impact */}
          <div className="space-y-4">
            {/* User Rank */}
            {userRank && (
              <Card className="border-primary/20">
                <CardContent className="p-5 text-center">
                  <Crown className="h-8 w-8 text-taste mx-auto mb-2" />
                  <p className="text-3xl font-bold">#{userRank.rank ?? userRank.position ?? "—"}</p>
                  <p className="text-sm text-muted-foreground">Your rank in {lbType.replace("_", " ")}</p>
                  {userRank.score != null && (
                    <p className="text-xs text-muted-foreground mt-1">Score: {userRank.score}</p>
                  )}
                </CardContent>
              </Card>
            )}

            {/* Leaderboard */}
            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center gap-2">
                  <Trophy className="h-4 w-4 text-taste" />
                  <CardTitle className="text-sm">Leaderboard</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex gap-1 mb-3 flex-wrap">
                  {leaderboardTypes.map((t) => (
                    <button
                      key={t.key}
                      onClick={() => setLbType(t.key)}
                      className={`px-2 py-1 rounded text-xs font-medium transition-colors ${lbType === t.key
                          ? "bg-primary text-primary-foreground"
                          : "bg-secondary text-secondary-foreground hover:bg-accent"
                        }`}
                    >
                      {t.label}
                    </button>
                  ))}
                </div>

                {leaderboard.length > 0 ? (
                  <div className="space-y-2">
                    {leaderboard.map((entry, i) => (
                      <div key={entry.user_id ?? i} className="flex items-center gap-3 p-2 rounded-lg hover:bg-accent/50 transition-colors">
                        <span className="text-sm font-bold w-6 text-center">
                          {i === 0 ? "🥇" : i === 1 ? "🥈" : i === 2 ? "🥉" : `${i + 1}`}
                        </span>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">{entry.username ?? entry.user_id}</p>
                        </div>
                        <span className="text-sm font-medium text-muted-foreground">{typeof entry.score === "number" ? entry.score.toFixed(1) : entry.score}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground">No leaderboard data yet. Start logging meals to compete!</p>
                )}
              </CardContent>
            </Card>

            {/* Monthly Impact Summary */}
            {impact && (
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-center gap-2">
                    <Leaf className="h-4 w-4 text-sustainability" />
                    <CardTitle className="text-sm">Monthly Impact</CardTitle>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Meals Logged</span>
                      <span className="text-sm font-medium">{impact.total_meals_logged}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Avg Health Score</span>
                      <span className="text-sm font-medium">{impact.average_health_score?.toFixed?.(0) ?? "—"}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">CO₂ Saved</span>
                      <span className="text-sm font-medium text-sustainability">{impact.total_carbon_saved?.toFixed?.(1) ?? "—"} kg</span>
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
