import { useMemo, useState } from "react";
import AppLayout from "@/components/AppLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Crown, Leaf, Lock, Trophy } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import {
  useGamificationAchievements,
  useImpactSummary,
  useLeaderboard,
  useUserRank,
} from "@/hooks/useApi";

const categoryLabels: Record<string, string> = {
  consistency: "Consistency",
  diversity: "Diversity",
  sustainability: "Sustainability",
  milestone: "Milestones",
};

const leaderboardTypes = [
  { key: "carbon_saved", label: "Carbon evidence" },
  { key: "variety_score", label: "Variety score" },
];

interface Achievement {
  id: string;
  title: string;
  description: string;
  category: string;
  progress: number;
  unlocked: boolean;
  icon: string;
  xp: number;
}

function stringValue(value: unknown, fallback: string): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function numberValue(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function booleanValue(value: unknown): boolean {
  return value === true;
}

export default function Achievements() {
  const { user } = useAuth();
  const userId = user?.id ?? "";
  const [leaderboardType, setLeaderboardType] = useState("carbon_saved");

  const achievementsQuery = useGamificationAchievements(userId);
  const leaderboardQuery = useLeaderboard(leaderboardType, "month", 10);
  const rankQuery = useUserRank(userId, leaderboardType);
  const impactQuery = useImpactSummary(userId);

  const achievements = useMemo<Achievement[]>(() => {
    const records = achievementsQuery.data?.achievements ?? [];
    return records.map((record, index) => {
      const unlocked = booleanValue(record.unlocked);
      return {
        id: stringValue(record.id, `achievement-${index}`),
        title: stringValue(record.name, stringValue(record.title, "Achievement")),
        description: stringValue(record.description, ""),
        category: stringValue(record.category, "milestone"),
        progress: numberValue(record.progress, unlocked ? 100 : 0),
        unlocked,
        icon: stringValue(record.icon, "🏆"),
        xp: numberValue(record.xp, numberValue(record.points, 100)),
      };
    });
  }, [achievementsQuery.data]);

  const totalEarned =
    achievementsQuery.data?.total_earned ??
    achievements.filter((achievement) => achievement.unlocked).length;
  const leaderboard = leaderboardQuery.data?.leaderboard ?? [];
  const rankRecord = rankQuery.data ?? {};
  const rank = numberValue(rankRecord.rank, numberValue(rankRecord.position, 0));
  const rankScore =
    typeof rankRecord.score === "number" && Number.isFinite(rankRecord.score)
      ? rankRecord.score
      : null;
  const impact = impactQuery.data;

  return (
    <AppLayout>
      <div className="mx-auto max-w-5xl space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Achievements</h1>
          <p className="text-sm text-muted-foreground">
            Evidence-backed milestones from persisted activity.
          </p>
        </div>

        <Card>
          <CardContent className="p-5">
            <div className="mb-2 flex items-center justify-between">
              <span className="font-semibold">Level {Math.floor(totalEarned / 3) + 1}</span>
              <span className="text-sm text-muted-foreground">
                {achievements.reduce(
                  (sum, achievement) => sum + (achievement.unlocked ? achievement.xp : 0),
                  0,
                )}{" "}
                XP
              </span>
            </div>
            <Progress
              value={(totalEarned / Math.max(achievements.length, 1)) * 100}
              className="h-2"
            />
            <p className="mt-2 text-xs text-muted-foreground">
              {totalEarned} of {achievements.length} achievements unlocked
            </p>
          </CardContent>
        </Card>

        <div className="grid gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            {Object.keys(categoryLabels).map((category) => {
              const items = achievements.filter(
                (achievement) => achievement.category === category,
              );
              if (!items.length) return null;
              return (
                <section key={category}>
                  <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                    {categoryLabels[category]}
                  </h2>
                  <div className="grid gap-4 sm:grid-cols-2">
                    {items.map((achievement) => (
                      <Card
                        key={achievement.id}
                        className={achievement.unlocked ? "" : "opacity-70"}
                      >
                        <CardContent className="p-5">
                          <div className="flex items-start gap-3">
                            <span className="text-2xl" aria-hidden="true">
                              {achievement.icon}
                            </span>
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center gap-2">
                                <h3 className="text-sm font-medium">{achievement.title}</h3>
                                {!achievement.unlocked ? (
                                  <Lock className="h-3 w-3 text-muted-foreground" />
                                ) : null}
                              </div>
                              <p className="mb-2 text-xs text-muted-foreground">
                                {achievement.description}
                              </p>
                              <div className="flex items-center gap-2">
                                <Progress value={achievement.progress} className="h-1.5 flex-1" />
                                <span className="text-xs text-muted-foreground">
                                  {achievement.progress}%
                                </span>
                              </div>
                              <p className="mt-1 text-xs text-muted-foreground">
                                {achievement.xp} XP
                              </p>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </section>
              );
            })}
          </div>

          <div className="space-y-4">
            {rank > 0 ? (
              <Card className="border-primary/20">
                <CardContent className="p-5 text-center">
                  <Crown className="mx-auto mb-2 h-8 w-8 text-taste" />
                  <p className="text-3xl font-bold">#{rank}</p>
                  <p className="text-sm text-muted-foreground">
                    Your rank in {leaderboardType.replaceAll("_", " ")}
                  </p>
                  {rankScore !== null ? (
                    <p className="mt-1 text-xs text-muted-foreground">
                      Score: {rankScore.toFixed(1)}
                    </p>
                  ) : null}
                </CardContent>
              </Card>
            ) : null}

            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center gap-2">
                  <Trophy className="h-4 w-4 text-taste" />
                  <CardTitle className="text-sm">Leaderboard</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <div className="mb-3 flex flex-wrap gap-1">
                  {leaderboardTypes.map((type) => (
                    <button
                      type="button"
                      key={type.key}
                      onClick={() => setLeaderboardType(type.key)}
                      className={`rounded px-2 py-1 text-xs font-medium ${
                        leaderboardType === type.key
                          ? "bg-primary text-primary-foreground"
                          : "bg-secondary text-secondary-foreground"
                      }`}
                    >
                      {type.label}
                    </button>
                  ))}
                </div>
                {leaderboard.length ? (
                  <div className="space-y-2">
                    {leaderboard.map((entry, index) => (
                      <div
                        key={entry.user_id}
                        className="flex items-center gap-3 rounded-lg p-2"
                      >
                        <span className="w-6 text-center text-sm font-bold">
                          {index + 1}
                        </span>
                        <p className="min-w-0 flex-1 truncate text-sm font-medium">
                          {entry.username ?? entry.user_id}
                        </p>
                        <span className="text-sm text-muted-foreground">
                          {entry.score.toFixed(1)}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    No persisted leaderboard evidence is available.
                  </p>
                )}
              </CardContent>
            </Card>

            {impact ? (
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-center gap-2">
                    <Leaf className="h-4 w-4 text-sustainability" />
                    <CardTitle className="text-sm">Recorded impact</CardTitle>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Meals logged</span>
                    <span>{impact.total_meals_logged ?? "—"}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">CO₂ evidence</span>
                    <span>
                      {impact.total_carbon_saved?.toFixed(1) ?? "—"} kg
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Values are displayed only when returned by the persisted evidence API.
                  </p>
                </CardContent>
              </Card>
            ) : null}
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
