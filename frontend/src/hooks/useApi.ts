/**
 * NutriFlavorOS — React Query Hooks for all backend APIs
 * Provides automatic caching, loading states, and error handling
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
    mealApi,
    analyticsApi,
    userApi,
    recipeApi,
    groceryApi,
    gamificationApi,
    sustainabilityApi,
    feedbackApi,
    type UserProfile,
    type PlanResponse,
    type DailyPlan,
    type Recipe,
} from "@/lib/api";

// ─── User ─────────────────────────────────────────────────────────────────────

export function useUserProfile(userId: string) {
    return useQuery({
        queryKey: ["user", userId],
        queryFn: () => userApi.getProfile(userId),
        enabled: !!userId,
        retry: 1,
        staleTime: 5 * 60_000,
    });
}

export function useUpdateProfile() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ userId, profile }: { userId: string; profile: UserProfile }) =>
            userApi.updateProfile(userId, profile),
        onSuccess: (_, { userId }) => qc.invalidateQueries({ queryKey: ["user", userId] }),
    });
}

export function useAddHealthCondition() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ userId, condition }: { userId: string; condition: string }) =>
            userApi.addHealthCondition(userId, condition),
        onSuccess: (_, { userId }) => qc.invalidateQueries({ queryKey: ["user", userId] }),
    });
}

export function useAddMedication() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ userId, medication }: { userId: string; medication: string }) =>
            userApi.addMedication(userId, medication),
        onSuccess: (_, { userId }) => qc.invalidateQueries({ queryKey: ["user", userId] }),
    });
}

// ─── Meals ────────────────────────────────────────────────────────────────────

export function useGenerateMealPlan() {
    return useMutation({
        mutationFn: (profile: UserProfile) => mealApi.generatePlan(profile),
    });
}

export function useRegenerateDay() {
    return useMutation({
        mutationFn: ({ userId, dayIndex }: { userId: string; dayIndex: number }) =>
            mealApi.regenerateDay(userId, dayIndex),
    });
}

export function useSwapMeal() {
    return useMutation({
        mutationFn: ({ userId, mealSlot }: { userId: string; mealSlot: string }) =>
            mealApi.swapMeal(userId, mealSlot),
    });
}

// ─── Analytics ────────────────────────────────────────────────────────────────

export function useHealthInsights(userId: string, period = "30d") {
    return useQuery({
        queryKey: ["analytics", "health", userId, period],
        queryFn: () => analyticsApi.getHealthInsights(userId, period),
        enabled: !!userId,
        retry: 1,
        staleTime: 2 * 60_000,
    });
}

export function useTasteInsights(userId: string) {
    return useQuery({
        queryKey: ["analytics", "taste", userId],
        queryFn: () => analyticsApi.getTasteInsights(userId),
        enabled: !!userId,
        retry: 1,
        staleTime: 2 * 60_000,
    });
}

export function useVarietyInsights(userId: string) {
    return useQuery({
        queryKey: ["analytics", "variety", userId],
        queryFn: () => analyticsApi.getVarietyInsights(userId),
        enabled: !!userId,
        retry: 1,
        staleTime: 2 * 60_000,
    });
}

export function useHealthPrediction() {
    return useMutation({
        mutationFn: (payload: Record<string, unknown>) =>
            analyticsApi.predictHealth(payload),
    });
}

// ─── Recipes ──────────────────────────────────────────────────────────────────

export function useRecipeSearch(q?: string, tags?: string, limit = 20) {
    return useQuery({
        queryKey: ["recipes", "search", q, tags, limit],
        queryFn: () => recipeApi.search(q, tags, limit),
        enabled: !!(q || tags),
        retry: 1,
        staleTime: 5 * 60_000,
    });
}

export function useRecipeDetails(recipeId: string | null) {
    return useQuery({
        queryKey: ["recipes", recipeId],
        queryFn: () => recipeApi.getDetails(recipeId!),
        enabled: !!recipeId,
        retry: 1,
        staleTime: 10 * 60_000,
    });
}

// ─── Grocery ──────────────────────────────────────────────────────────────────

export function useShoppingList(userId: string, daysAhead = 7) {
    return useQuery({
        queryKey: ["grocery", "shopping_list", userId, daysAhead],
        queryFn: () => groceryApi.getShoppingList(userId, daysAhead),
        enabled: !!userId,
        retry: 1,
        staleTime: 5 * 60_000,
    });
}

export function useLogPurchase() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ userId, items }: { userId: string; items: { item: string; quantity: number; price: number }[] }) =>
            groceryApi.logPurchase(userId, items),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["grocery"] }),
    });
}

export function useLogConsumption() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ userId, item, quantity }: { userId: string; item: string; quantity: number }) =>
            groceryApi.logConsumption(userId, item, quantity),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["grocery"] }),
    });
}

// ─── Gamification ─────────────────────────────────────────────────────────────

export function useGamificationAchievements(userId: string) {
    return useQuery({
        queryKey: ["gamification", "achievements", userId],
        queryFn: () => gamificationApi.getAchievements(userId),
        enabled: !!userId,
        retry: 1,
        staleTime: 2 * 60_000,
    });
}

export function useLeaderboard(type = "carbon_saved", period = "month", limit = 10) {
    return useQuery({
        queryKey: ["gamification", "leaderboard", type, period, limit],
        queryFn: () => gamificationApi.getLeaderboard(type, period, limit),
        retry: 1,
        staleTime: 2 * 60_000,
    });
}

export function useUserRank(userId: string, type = "carbon_saved") {
    return useQuery({
        queryKey: ["gamification", "rank", userId, type],
        queryFn: () => gamificationApi.getUserRank(userId, type),
        enabled: !!userId,
        retry: 1,
        staleTime: 2 * 60_000,
    });
}

export function useImpactSummary(userId: string) {
    return useQuery({
        queryKey: ["gamification", "impact", userId],
        queryFn: () => gamificationApi.getImpactSummary(userId),
        enabled: !!userId,
        retry: 1,
        staleTime: 5 * 60_000,
    });
}

export function useLogMealImpact() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({
            userId,
            data,
        }: {
            userId: string;
            data: { carbon_footprint: number; health_score: number; variety_score: number; taste_rating?: number };
        }) => gamificationApi.logMealImpact(userId, data),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["gamification"] }),
    });
}

// ─── Sustainability ───────────────────────────────────────────────────────────

export function useSustainabilityData(userId: string) {
    return useQuery({
        queryKey: ["sustainability", userId],
        queryFn: () => sustainabilityApi.getData(userId),
        enabled: !!userId,
        retry: 1,
        staleTime: 5 * 60_000,
    });
}

export function useCarbonFootprint(userId: string) {
    return useQuery({
        queryKey: ["sustainability", "carbon", userId],
        queryFn: () => sustainabilityApi.getCarbonFootprint(userId),
        enabled: !!userId,
        retry: 1,
        staleTime: 5 * 60_000,
    });
}

// ─── Feedback / Online Learning ───────────────────────────────────────────────

export function useLogTasteFeedback() {
    return useMutation({
        mutationFn: (data: {
            user_id: string;
            recipe_id: string;
            rating: number;
            user_genome: number[];
            recipe_profile: number[];
        }) => feedbackApi.logTasteFeedback(data),
    });
}

export function useLogHealthOutcome() {
    return useMutation({
        mutationFn: (data: {
            user_id: string;
            actual_weight: number;
            actual_hba1c?: number;
            actual_cholesterol?: number;
            meal_history: Record<string, unknown>[];
        }) => feedbackApi.logHealthOutcome(data),
    });
}

export function useLogMealSelection() {
    return useMutation({
        mutationFn: (data: {
            user_id: string;
            state: number[];
            selected_recipe_id: number;
            reward: number;
        }) => feedbackApi.logMealSelection(data),
    });
}

export function useModelStats(modelName: string) {
    return useQuery({
        queryKey: ["models", "stats", modelName],
        queryFn: () => feedbackApi.getModelStats(modelName),
        enabled: !!modelName,
        retry: 1,
        staleTime: 60_000,
    });
}
