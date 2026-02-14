
import { useState, useCallback, useEffect } from "react";
import AppLayout from "@/components/AppLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { RefreshCw, Sparkles, Clock, ChefHat, AlertCircle } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { useGetMealPlan, useGenerateMealPlan, useRegenerateDay, useSwapMeal } from "@/hooks/useApi";
import type { PlanResponse } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import { RecipeDetailModal } from "@/components/RecipeDetailModal";
import { MealCard } from "@/components/MealCard";
import { AnimatePresence, motion } from "framer-motion";
import { Skeleton } from "@/components/ui/skeleton";

const mealTypeLabels: Record<string, string> = { breakfast: "Breakfast", lunch: "Lunch", dinner: "Dinner", snack: "Snack" };
const mealTypes = ["breakfast", "lunch", "dinner", "snack"] as const;
const dayNames = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

// Convert API plan to the display format
function apiPlanToDisplay(plan: PlanResponse) {
  return plan.days.map((d, i) => ({
    day: dayNames[i] ?? `Day ${d.day}`,
    meals: Object.entries(d.meals).map(([type, recipe]) => ({
      id: recipe.id,
      name: recipe.name,
      type: type as "breakfast" | "lunch" | "dinner" | "snack",
      calories: recipe.calories,
      protein: recipe.macros?.protein ?? 0,
      carbs: recipe.macros?.carbs ?? 0,
      fat: recipe.macros?.fat ?? 0,
      sustainabilityScore: 7,
    })),
    scores: d.scores,
    prepTimeline: plan.prep_timeline?.[d.day] ?? [],
  }));
}

export default function MealPlanner() {
  const { user } = useAuth();
  const userId = user?.id ?? "usr_1";
  const { toast } = useToast();

  const [selectedDay, setSelectedDay] = useState(0);
  const [displayPlan, setDisplayPlan] = useState<any[]>([]);
  const [prepTimeline, setPrepTimeline] = useState<Record<number, string[]>>({});
  const [ratings, setRatings] = useState<Record<string, number>>({});
  const [isApiPlan, setIsApiPlan] = useState(false);
  const [isInitialLoad, setIsInitialLoad] = useState(true);

  // Modal state
  const [selectedRecipeId, setSelectedRecipeId] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // API hooks
  const getMealPlanQ = useGetMealPlan(userId);
  const generateMutation = useGenerateMealPlan();
  const regenerateMutation = useRegenerateDay();
  const swapMutation = useSwapMeal();

  const plan = displayPlan[selectedDay];

  // Generate AI plan
  const handleGenerate = useCallback(async () => {
    try {
      const result = await generateMutation.mutateAsync({
        age: 30,
        weight_kg: 70,
        height_cm: 175,
        gender: "male",
        activity_level: 1.5,
        goal: "maintenance",
      });
      const converted = apiPlanToDisplay(result);
      setDisplayPlan(converted as any);
      setPrepTimeline(result.prep_timeline ?? {});
      setIsApiPlan(true);
      toast({ title: "✨ AI Plan Generated", description: "Real recipes from your backend!" });
    } catch (error) {
      toast({ title: "Backend Error", description: "Failed to generate meal plan. Please ensure backend is running.", variant: "destructive" });
      console.error("Meal plan generation failed:", error);
    }
  }, [generateMutation, toast]);

  // Load from localStorage on mount (offline persistence)
  useEffect(() => {
    const cached = localStorage.getItem(`mealPlan_${userId}`);
    if (cached) {
      try {
        const { plan, prepTimeline, timestamp } = JSON.parse(cached);
        // Only use if less than 24 hours old
        if (Date.now() - timestamp < 24 * 60 * 60 * 1000) {
          setDisplayPlan(plan);
          setPrepTimeline(prepTimeline || {});
          setIsApiPlan(true);
          console.log("Loaded meal plan from localStorage");
        }
      } catch (e) {
        console.error("Failed to load cached plan:", e);
      }
    }
  }, [userId]);

  // Save to localStorage when plan changes
  useEffect(() => {
    if (displayPlan.length > 0 && isApiPlan) {
      localStorage.setItem(`mealPlan_${userId}`, JSON.stringify({
        plan: displayPlan,
        prepTimeline,
        timestamp: Date.now(),
      }));
    }
  }, [displayPlan, prepTimeline, isApiPlan, userId]);

  // Fetch existing plan first, only generate if none exists
  useEffect(() => {
    if (isInitialLoad) {
      setIsInitialLoad(false);

      // Try to load existing plan from API first
      if (getMealPlanQ.data) {
        const converted = apiPlanToDisplay(getMealPlanQ.data);
        setDisplayPlan(converted as any);
        setPrepTimeline(getMealPlanQ.data.prep_timeline ?? {});
        setIsApiPlan(true);
        console.log("Loaded existing meal plan from backend");
      } else if (!getMealPlanQ.isLoading && !getMealPlanQ.data && displayPlan.length === 0) {
        // No existing plan and no cached plan, generate new one
        console.log("No existing plan found, generating new one...");
        handleGenerate().catch(() => {
          console.log("Auto-generation skipped - user can manually generate");
        });
      }
    }
  }, [isInitialLoad, getMealPlanQ.data, getMealPlanQ.isLoading, handleGenerate, displayPlan.length]);

  // Regenerate a specific day
  const handleRegenerateDay = useCallback(async () => {
    try {
      await regenerateMutation.mutateAsync({ userId, dayIndex: selectedDay });
      toast({ title: "Day regenerated", description: `${displayPlan[selectedDay].day} meals refreshed` });
    } catch {
      toast({ title: "Regeneration unavailable", description: "Backend not connected", variant: "destructive" });
    }
  }, [regenerateMutation, userId, selectedDay, displayPlan, toast]);

  // Swap a specific meal
  const handleSwap = useCallback(async (mealSlot: string) => {
    try {
      const newRecipe = await swapMutation.mutateAsync({ userId, mealSlot });
      // Update local state with swapped meal
      setDisplayPlan((prev) => {
        const updated = [...prev];
        const dayMeals = [...updated[selectedDay].meals];
        const idx = dayMeals.findIndex((m) => m.type === mealSlot);
        if (idx >= 0) {
          dayMeals[idx] = {
            ...dayMeals[idx],
            id: newRecipe.id,
            name: newRecipe.name,
            calories: newRecipe.calories,
            protein: newRecipe.macros?.protein ?? dayMeals[idx].protein,
            carbs: newRecipe.macros?.carbs ?? dayMeals[idx].carbs,
            fat: newRecipe.macros?.fat ?? dayMeals[idx].fat,
          };
        }
        updated[selectedDay] = { ...updated[selectedDay], meals: dayMeals };
        return updated;
      });
      toast({ title: "Meal swapped", description: `Replaced with ${newRecipe.name}` });
    } catch {
      toast({ title: "Swap unavailable", description: "Backend not connected", variant: "destructive" });
    }
  }, [swapMutation, userId, selectedDay, toast]);

  // Rate a meal
  const handleRate = (mealId: string, rating: number) => {
    setRatings((prev) => ({ ...prev, [mealId]: rating }));
    toast({ title: "Rating saved", description: `Rated ${rating}/5 — helps AI learn your preferences` });
  };

  const openRecipeDetails = (id: string) => {
    setSelectedRecipeId(id);
    setIsModalOpen(true);
  };

  return (
    <AppLayout>
      <div className="space-y-6 max-w-5xl mx-auto">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}>
            <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-primary to-purple-600">Meal Planner</h1>
            <p className="text-muted-foreground text-sm">Your personalized AI usage plan</p>
          </motion.div>
          <div className="flex gap-2">
            <Button
              onClick={handleGenerate}
              disabled={generateMutation.isPending}
              size="sm"
              className="bg-gradient-to-r from-primary to-purple-600 hover:from-primary/90 hover:to-purple-600/90 text-white shadow-md transition-all hover:scale-105"
            >
              {generateMutation.isPending ? (
                <Sparkles className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4 mr-2" />
              )}
              {generateMutation.isPending ? "Generating..." : "Generate AI Plan"}
            </Button>
            <Button variant="outline" size="sm" onClick={handleRegenerateDay} disabled={regenerateMutation.isPending}>
              <RefreshCw className={`h-4 w-4 mr-2 ${regenerateMutation.isPending ? "animate-spin" : ""}`} />
              Regenerate Day
            </Button>
          </div>
        </div>

        {/* Day selector */}
        {displayPlan.length > 0 && (
          <div className="flex gap-2 overflow-x-auto pb-4 scrollbar-hide">
            {displayPlan.map((d, i) => (
              <motion.button
                key={d.day}
                whileTap={{ scale: 0.95 }}
                onClick={() => setSelectedDay(i)}
                className={`px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-all shadow-sm ${i === selectedDay
                  ? "bg-primary text-primary-foreground shadow-md ring-2 ring-primary/20"
                  : "bg-card hover:bg-accent border border-border"
                  }`}
              >
                {d.day}
              </motion.button>
            ))}
          </div>
        )}

        {/* Meals by type */}
        <div className="space-y-4 min-h-[400px]">
          <AnimatePresence mode="wait">
            {generateMutation.isPending ? (
              <motion.div
                key="loading"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="space-y-4"
              >
                {[1, 2, 3].map((i) => (
                  <div key={i} className="flex items-center space-x-4 p-4 border rounded-lg bg-card/50">
                    <Skeleton className="h-12 w-12 rounded-full" />
                    <div className="space-y-2 flex-1">
                      <Skeleton className="h-4 w-[250px]" />
                      <Skeleton className="h-4 w-[200px]" />
                    </div>
                  </div>
                ))}
              </motion.div>
            ) : displayPlan.length === 0 ? (
              <motion.div
                key="empty"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="flex items-center justify-center min-h-[400px]"
              >
                <Card className="max-w-md w-full border-dashed">
                  <CardContent className="p-8 text-center">
                    <ChefHat className="h-16 w-16 mx-auto mb-4 text-muted-foreground opacity-50" />
                    <h3 className="text-lg font-semibold mb-2">No Meal Plan Yet</h3>
                    <p className="text-sm text-muted-foreground mb-4">
                      Click "Generate AI Plan" above to create your personalized weekly meal plan using real recipes from the backend.
                    </p>
                    <Button
                      onClick={handleGenerate}
                      disabled={generateMutation.isPending}
                      className="bg-gradient-to-r from-primary to-purple-600"
                    >
                      <Sparkles className="h-4 w-4 mr-2" />
                      Generate Your First Plan
                    </Button>
                  </CardContent>
                </Card>
              </motion.div>
            ) : (
              <motion.div
                key={selectedDay}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.3 }}
                className="space-y-4"
              >
                {mealTypes.map((type) => {
                  const meal = plan.meals.find((m) => m.type === type);
                  if (!meal) return null;
                  const currentRating = ratings[meal.id] ?? 0;
                  return (
                    <MealCard
                      key={`${selectedDay}-${type}`}
                      meal={meal}
                      label={mealTypeLabels[type]}
                      currentRating={currentRating}
                      onRate={handleRate}
                      onSwap={handleSwap}
                      onClick={openRecipeDetails}
                      isSwapping={swapMutation.isPending}
                    />
                  );
                })}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Prep Timeline */}
        {isApiPlan && prepTimeline && Object.keys(prepTimeline).length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            <Card className="border-primary/20 bg-gradient-to-br from-card via-card to-primary/5">
              <CardHeader className="pb-4">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
                    <ChefHat className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <CardTitle className="text-lg">Weekly Prep Timeline</CardTitle>
                    <p className="text-xs text-muted-foreground mt-0.5">Plan ahead for efficient cooking</p>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4">
                  {Object.entries(prepTimeline).map(([day, tasks], dayIndex) => (
                    <motion.div
                      key={day}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: dayIndex * 0.05 }}
                      className="group relative overflow-hidden rounded-lg border bg-gradient-to-r from-muted/30 to-muted/10 p-4 hover:shadow-md transition-all"
                    >
                      {/* Day Header */}
                      <div className="flex items-center gap-2 mb-3">
                        <div className="h-8 w-8 rounded-full bg-primary/20 flex items-center justify-center text-primary font-bold text-sm">
                          {day}
                        </div>
                        <div>
                          <p className="font-semibold text-sm">Day {day}</p>
                          <p className="text-xs text-muted-foreground">{(tasks as string[]).length} tasks</p>
                        </div>
                      </div>

                      {/* Tasks List */}
                      <div className="space-y-2 pl-10">
                        {(tasks as string[]).map((task, i) => {
                          // Parse time and task from string like "8:00 AM - Prepare B'stilla"
                          const match = task.match(/^(\d{1,2}:\d{2}\s*(?:AM|PM)?)\s*-\s*(.+)$/i);
                          const time = match ? match[1] : "";
                          const taskText = match ? match[2] : task;

                          return (
                            <div
                              key={i}
                              className="flex items-start gap-3 p-2 rounded-md bg-background/50 hover:bg-background transition-colors"
                            >
                              <Clock className="h-4 w-4 text-primary mt-0.5 shrink-0" />
                              <div className="flex-1 min-w-0">
                                {time && (
                                  <p className="text-xs font-medium text-primary mb-0.5">{time}</p>
                                )}
                                <p className="text-sm text-foreground leading-relaxed">{taskText}</p>
                              </div>
                            </div>
                          );
                        })}
                      </div>

                      {/* Decorative gradient */}
                      <div className="absolute top-0 right-0 h-full w-1 bg-gradient-to-b from-primary/50 via-primary/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                    </motion.div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Day summary */}
        {plan && displayPlan.length > 0 && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.3 }}
          >
            <Card className="bg-gradient-to-br from-card to-secondary/20 border-border/60">
              <CardContent className="p-5">
                <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-purple-500" />
                  Daily Nutrition Summary
                </h3>
                <div className="grid grid-cols-4 gap-4 text-center divide-x divide-border/40">
                  <div>
                    <p className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-br from-orange-400 to-red-600">
                      {plan.meals.reduce((s, m) => s + m.calories, 0)}
                    </p>
                    <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider mt-1">Calories</p>
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-blue-500">{plan.meals.reduce((s, m) => s + m.protein, 0)}g</p>
                    <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider mt-1">Protein</p>
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-amber-500">{plan.meals.reduce((s, m) => s + m.carbs, 0)}g</p>
                    <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider mt-1">Carbs</p>
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-rose-500">{plan.meals.reduce((s, m) => s + m.fat, 0)}g</p>
                    <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider mt-1">Fat</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        <RecipeDetailModal
          recipeId={selectedRecipeId}
          open={isModalOpen}
          onOpenChange={setIsModalOpen}
        />
      </div>
    </AppLayout>
  );
}
