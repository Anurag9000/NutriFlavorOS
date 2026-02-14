/**
 * NutriFlavorOS — Centralized API Client
 * Connects frontend to all backend endpoints
 */

const API_BASE = "http://localhost:8000/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
    const res = await fetch(`${API_BASE}${path}`, {
        headers: { "Content-Type": "application/json", ...options?.headers },
        ...options,
    });
    if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
    return res.json();
}

// ─── Types ────────────────────────────────────────────────────────────────────

export interface UserProfile {
    id?: string;
    name?: string;
    age: number;
    weight_kg: number;
    height_cm: number;
    gender: "male" | "female" | "other";
    activity_level: number;
    goal: "weight_loss" | "maintenance" | "muscle_gain";
    liked_ingredients?: string[];
    disliked_ingredients?: string[];
    dietary_restrictions?: string[];
    health_conditions?: string[];
    medications?: string[];
}

export interface Recipe {
    id: string;
    name: string;
    description: string;
    image_url?: string;
    ingredients: string[];
    calories: number;
    macros: { protein: number; carbs: number; fat: number };
    flavor_profile?: Record<string, number>;
    tags?: string[];
    cuisine?: string;
    instructions?: string[] | string;
    nutrition?: Record<string, unknown>;
    readyInMinutes?: number;
    servings?: number;
    healthScore?: number;
}

export interface DailyPlan {
    day: number;
    meals: Record<string, Recipe>;
    total_stats: Record<string, number>;
    scores: Record<string, number>;
}

export interface PlanResponse {
    user_id: string;
    days: DailyPlan[];
    shopping_list?: Record<string, Record<string, unknown>>;
    prep_timeline?: Record<number, string[]>;
    overall_stats?: Record<string, unknown>;
}

export interface ShoppingListItem {
    item: string;
    predicted_quantity: number;
    estimated_cost: number;
    urgency: number;
    category?: string;
}

export interface ShoppingListResponse {
    shopping_list: ShoppingListItem[];
    summary: {
        total_items: number;
        estimated_total_cost: number;
        days_covered: number;
        urgent_items: number;
    };
}

export interface LeaderboardEntry {
    user_id: string;
    username?: string;
    score: number;
    rank: number;
}

export interface ImpactSummary {
    total_carbon_saved: number;
    total_meals_logged: number;
    average_health_score: number;
    visual_impact?: Record<string, unknown>;
    equivalents?: Record<string, unknown>;
}

export interface HealthPrediction {
    current_score: number;
    predicted_score: number;
    forecast: { day: number; score: number }[];
}

export interface SustainabilityData {
    carbon_saved_kg: number;
    water_saved_l: number;
    trees_planted_equivalent: number;
    sustainable_meals_count: number;
}

export interface CarbonBreakdown {
    total_footprint: number;
    average_meal_footprint: number;
    breakdown: { category: string; value: number }[];
}

export interface TasteDataPoint {
    subject: string;
    A: number;
    fullMark: number;
}

export interface VarietyDataPoint {
    name: string;
    value: number;
}

export interface HealthInsightPoint {
    date: string;
    score: number;
}

// ─── Meal API ─────────────────────────────────────────────────────────────────

export const mealApi = {
    getMealPlan: (userId: string) =>
        request<PlanResponse>(`/meals/plan/${userId}`, {
            method: "GET",
        }),

    generatePlan: (profile: UserProfile) =>
        request<PlanResponse>("/meals/generate", {
            method: "POST",
            body: JSON.stringify(profile),
        }),

    regenerateDay: (userId: string, dayIndex: number) =>
        request<DailyPlan>("/meals/regenerate_day", {
            method: "POST",
            body: JSON.stringify({ user_id: userId, day_index: dayIndex }),
        }),

    swapMeal: (userId: string, mealSlot: string) =>
        request<Recipe>("/meals/swap_meal", {
            method: "POST",
            body: JSON.stringify({ user_id: userId, meal_slot: mealSlot }),
        }),
};

// ─── Analytics API ────────────────────────────────────────────────────────────

export const analyticsApi = {
    getHealthInsights: (userId: string, period = "30d") =>
        request<HealthInsightPoint[]>(`/analytics/health/${userId}?period=${period}`),

    getTasteInsights: (userId: string) =>
        request<TasteDataPoint[]>(`/analytics/taste/${userId}`),

    getVarietyInsights: (userId: string) =>
        request<VarietyDataPoint[]>(`/analytics/variety/${userId}`),

    predictHealth: (payload: Record<string, unknown>) =>
        request<HealthPrediction>("/analytics/predict_health", {
            method: "POST",
            body: JSON.stringify(payload),
        }),

    getInsights: (userId: string) =>
        request<{ insight: string; category: string; priority: string }>(`/analytics/insights/${userId}`, {
            method: "GET",
        }),
};

// ─── User API ─────────────────────────────────────────────────────────────────

export const userApi = {
    getProfile: (userId: string) =>
        request<UserProfile>(`/user/${userId}`),

    updateProfile: (userId: string, profile: UserProfile) =>
        request<UserProfile>(`/user/${userId}`, {
            method: "PUT",
            body: JSON.stringify(profile),
        }),

    addHealthCondition: (userId: string, condition: string) =>
        request<{ status: string; message: string; dataset_verified: boolean }>(
            `/user/${userId}/health_condition`,
            { method: "POST", body: JSON.stringify({ condition }) }
        ),

    addMedication: (userId: string, medication: string) =>
        request<{ status: string; message: string }>(
            `/user/${userId}/medication`,
            { method: "POST", body: JSON.stringify({ medication }) }
        ),
};

// ─── Auth API ─────────────────────────────────────────────────────────────────

export const authApi = {
    login: (email: string, password: string) =>
        request<{ access_token: string; token_type: string; user: any }>("/auth/login", {
            method: "POST",
            body: JSON.stringify({ email, password }),
        }),

    signup: (data: any) =>
        request<{ access_token: string; token_type: string; user: any }>("/auth/signup", {
            method: "POST",
            body: JSON.stringify(data),
        }),
};

// ─── Recipe API ───────────────────────────────────────────────────────────────

export const recipeApi = {
    search: (q?: string, tags?: string, limit = 20) => {
        const params = new URLSearchParams();
        if (q) params.set("q", q);
        if (tags) params.set("tags", tags);
        params.set("limit", String(limit));
        return request<Record<string, unknown>[]>(`/recipes/search?${params}`);
    },

    getDetails: (recipeId: string) =>
        request<Recipe>(`/recipes/${recipeId}`),
};

// ─── Grocery API ──────────────────────────────────────────────────────────────

export const groceryApi = {
    getShoppingList: (userId: string, daysAhead = 7) =>
        request<ShoppingListResponse>(`/grocery/shopping_list/${userId}?days_ahead=${daysAhead}`),

    logPurchase: (userId: string, items: { item: string; quantity: number; price: number }[]) =>
        request<{ status: string; message: string; total_items_tracked: number }>(
            "/grocery/purchase",
            { method: "POST", body: JSON.stringify({ user_id: userId, items }) }
        ),

    logConsumption: (userId: string, item: string, quantity: number) =>
        request<{ status: string; message: string; current_stock: number; consumption_rate: number }>(
            "/grocery/consume",
            { method: "POST", body: JSON.stringify({ user_id: userId, item, quantity }) }
        ),

    predictNextPurchase: (userId: string, item: string) =>
        request<{ item: string; prediction: Record<string, unknown>; recommendation: string }>(
            `/grocery/predict/${userId}/${encodeURIComponent(item)}`
        ),
};

// ─── Gamification API ─────────────────────────────────────────────────────────

export const gamificationApi = {
    getAchievements: (userId: string) =>
        request<{ achievements: Record<string, unknown>[]; total_earned: number }>(
            `/gamification/achievements/${userId}`
        ),

    getLeaderboard: (type = "carbon_saved", period = "month", limit = 100) =>
        request<{ leaderboard: LeaderboardEntry[]; type: string; period: string }>(
            `/gamification/leaderboard?leaderboard_type=${type}&period=${period}&limit=${limit}`
        ),

    getUserRank: (userId: string, type = "carbon_saved") =>
        request<Record<string, unknown>>(
            `/gamification/rank/${userId}?leaderboard_type=${type}`
        ),

    getImpactSummary: (userId: string) =>
        request<ImpactSummary>(`/gamification/impact_summary/${userId}`),

    logMealImpact: (userId: string, data: { carbon_footprint: number; health_score: number; variety_score: number; taste_rating?: number }) =>
        request<{ status: string; visual_impact: Record<string, unknown>; new_achievements: unknown[]; total_points: number }>(
            "/gamification/log_meal",
            { method: "POST", body: JSON.stringify({ user_id: userId, ...data }) }
        ),
};

// ─── Sustainability API ───────────────────────────────────────────────────────

export const sustainabilityApi = {
    getData: (userId: string, period = "monthly") =>
        request<SustainabilityData>(`/sustainability/${userId}?period=${period}`),

    getCarbonFootprint: (userId: string) =>
        request<CarbonBreakdown>(`/sustainability/carbon-footprint/${userId}`),
};

// ─── Feedback / Online Learning API ───────────────────────────────────────────

export const feedbackApi = {
    logTasteFeedback: (data: {
        user_id: string;
        recipe_id: string;
        rating: number;
        user_genome: number[];
        recipe_profile: number[];
    }) =>
        request<{ status: string; message: string; current_buffer_size: number }>(
            "/feedback/taste",
            { method: "POST", body: JSON.stringify(data) }
        ),

    logHealthOutcome: (data: {
        user_id: string;
        actual_weight: number;
        actual_hba1c?: number;
        actual_cholesterol?: number;
        meal_history: Record<string, unknown>[];
    }) =>
        request<{ status: string; message: string; current_buffer_size: number }>(
            "/feedback/health",
            { method: "POST", body: JSON.stringify(data) }
        ),

    logMealSelection: (data: {
        user_id: string;
        state: number[];
        selected_recipe_id: number;
        reward: number;
    }) =>
        request<{ status: string; message: string }>(
            "/feedback/meal_selection",
            { method: "POST", body: JSON.stringify(data) }
        ),

    getModelStats: (modelName: string) =>
        request<Record<string, unknown>>(`/models/stats/${modelName}`),
};
