/** NutriFlavorOS centralized API client. */

const configuredBase = import.meta.env.VITE_API_BASE_URL as string | undefined;
const defaultBase = import.meta.env.DEV ? "http://localhost:8000/api/v1" : "/api/v1";
const API_BASE = (configuredBase?.trim() || defaultBase).replace(/\/$/, "");
const TOKEN_KEY = "nutriflavor_token";
const USER_KEY = "nfos_user";

function extractErrorMessage(detail: unknown, status: number): string {
    if (typeof detail === "string") return detail;
    if (!detail || typeof detail !== "object") return `Request failed with status ${status}`;

    const body = detail as Record<string, unknown>;
    const nested = body.detail;
    if (typeof nested === "string") return nested;
    if (nested && typeof nested === "object") {
        const nestedBody = nested as Record<string, unknown>;
        if (typeof nestedBody.message === "string") return nestedBody.message;
    }
    if (typeof body.message === "string") return body.message;
    return `Request failed with status ${status}`;
}

export class ApiError extends Error {
    readonly status: number;
    readonly detail: unknown;

    constructor(status: number, detail: unknown) {
        super(extractErrorMessage(detail, status));
        this.name = "ApiError";
        this.status = status;
        this.detail = detail;
    }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const token = localStorage.getItem(TOKEN_KEY);
    const headers = new Headers(options.headers);
    if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
        headers.set("Content-Type", "application/json");
    }
    if (token) headers.set("Authorization", `Bearer ${token}`);

    const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
    if (response.status === 401) {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
        window.dispatchEvent(new CustomEvent("nutriflavor:unauthorized"));
    }

    const contentType = response.headers.get("content-type") || "";
    const payload: unknown = contentType.includes("application/json")
        ? await response.json()
        : await response.text();
    if (!response.ok) throw new ApiError(response.status, payload);
    return payload as T;
}

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
    allergies?: string[];
    dietary_restrictions?: string[];
    health_conditions?: string[];
    medications?: string[];
    target_calories?: number;
    target_protein_g?: number;
    target_carbs_g?: number;
    target_fat_g?: number;
}

export interface IngredientLine {
    raw: string;
    name: string;
    quantity_min?: number | null;
    quantity_max?: number | null;
    unit?: string | null;
    canonical_quantity_min?: number | null;
    canonical_quantity_max?: number | null;
    canonical_unit?: string | null;
    parse_status: "normalized" | "partial" | "unquantified";
}

export interface Recipe {
    id: string;
    name: string;
    description: string;
    image_url?: string;
    ingredients: string[];
    ingredient_lines?: IngredientLine[];
    servings?: number;
    calories: number;
    macros: { protein?: number; carbs?: number; fat?: number; [key: string]: number | undefined };
    flavor_profile?: Record<string, number>;
    tags?: string[];
    cuisine?: string;
    instructions?: string[];
    estimated_cost?: number;
    source_name?: string | null;
    source_url?: string | null;
    source_version?: string | null;
    nutrition_basis?: "per_serving" | "per_100g" | "per_recipe" | "unknown";
}

export interface DailyPlan {
    day: number;
    meals: Record<string, Recipe>;
    portions: Record<string, number>;
    total_stats: Record<string, unknown>;
    scores: Record<string, number>;
}

export interface OptimizationSummary {
    method: string;
    deterministic: boolean;
    objective_score: number;
    beam_width: number;
    candidate_count: number;
    slot_count: number;
    portion_options: number[];
    repeat_window_slots: number;
    max_recipe_occurrences: number;
    relaxations: string[];
    slot_candidate_counts: Record<string, number>;
}

export interface ShoppingQuantity {
    quantity_min: number;
    quantity_max: number;
    unit: string;
}

export interface PlannedShoppingItem {
    display_name: string;
    quantity: string;
    quantity_status: "normalized" | "mixed_or_partial" | "unquantified";
    quantities: ShoppingQuantity[];
    occurrences: number;
    unquantified_occurrences: number;
    source_recipe_ids: string[];
    raw_examples: string[];
}

export interface PlanResponse {
    user_id: string;
    days: DailyPlan[];
    shopping_list?: Record<string, Record<string, PlannedShoppingItem>>;
    prep_timeline?: Record<number, string[]>;
    overall_stats?: Record<string, unknown>;
    optimization?: OptimizationSummary;
    warnings?: string[];
}

export interface ShoppingListItem {
    item: string;
    predicted_quantity: number;
    quantity_label?: string;
    quantity_status?: string;
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
        cost_status?: string;
    };
}

export interface LeaderboardEntry {
    user_id: string;
    username?: string;
    score: number;
    rank: number;
}

export interface ImpactSummary {
    total_carbon_saved?: number;
    total_meals_logged?: number;
    average_health_score?: number;
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
    planned_carbon_footprint_kg?: number | null;
    data_status?: string;
    baseline_status?: string;
}

export interface CarbonBreakdown {
    total_footprint: number;
    average_meal_footprint: number;
    breakdown: { category: string; value: number; status?: string }[];
    data_status?: string;
}

export interface TasteDataPoint {
    subject: string;
    A: number;
    fullMark: number;
    metric?: string;
}

export interface VarietyDataPoint {
    name: string;
    value: number;
    count?: number;
    metric?: string;
}

export interface HealthInsightPoint {
    date: string;
    score: number;
    metric?: string;
    period?: string;
}

interface AuthResponse {
    access_token: string;
    token_type: string;
    user: Record<string, unknown>;
}

interface AcceptedFeedback {
    status: string;
    event_id: number;
    message: string;
    model_updated: boolean;
}

export const mealApi = {
    getMealPlan: (userId: string) => request<PlanResponse>(`/meals/plan/${encodeURIComponent(userId)}`),
    generatePlan: (profile?: UserProfile) =>
        request<PlanResponse>("/meals/generate", {
            method: "POST",
            body: profile ? JSON.stringify(profile) : undefined,
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

export const analyticsApi = {
    getHealthInsights: (userId: string, period = "30d") =>
        request<HealthInsightPoint[]>(`/analytics/health/${encodeURIComponent(userId)}?period=${encodeURIComponent(period)}`),
    getTasteInsights: (userId: string) =>
        request<TasteDataPoint[]>(`/analytics/taste/${encodeURIComponent(userId)}`),
    getVarietyInsights: (userId: string) =>
        request<VarietyDataPoint[]>(`/analytics/variety/${encodeURIComponent(userId)}`),
    predictHealth: (payload: Record<string, unknown>) =>
        request<HealthPrediction>("/analytics/predict_health", {
            method: "POST",
            body: JSON.stringify(payload),
        }),
    getInsights: (userId: string) =>
        request<{ insight: string; category: string; priority: string }>(
            `/analytics/insights/${encodeURIComponent(userId)}`,
        ),
};

export const userApi = {
    getProfile: (userId: string) => request<UserProfile>(`/user/${encodeURIComponent(userId)}`),
    updateProfile: (userId: string, profile: UserProfile) =>
        request<UserProfile>(`/user/${encodeURIComponent(userId)}`, {
            method: "PUT",
            body: JSON.stringify(profile),
        }),
    addHealthCondition: (userId: string, condition: string) =>
        request<{ status: string; message: string; dataset_verified: boolean }>(
            `/user/${encodeURIComponent(userId)}/health_condition`,
            { method: "POST", body: JSON.stringify({ condition }) },
        ),
    addMedication: (userId: string, medication: string) =>
        request<{ status: string; message: string }>(
            `/user/${encodeURIComponent(userId)}/medication`,
            { method: "POST", body: JSON.stringify({ medication }) },
        ),
};

export const authApi = {
    login: (email: string, password: string) =>
        request<AuthResponse>("/auth/login", {
            method: "POST",
            body: JSON.stringify({ email, password }),
        }),
    signup: (data: Record<string, unknown>) =>
        request<AuthResponse>("/auth/signup", {
            method: "POST",
            body: JSON.stringify(data),
        }),
    me: () => request<{ id: string; email: string; name: string }>("/auth/me"),
};

export const recipeApi = {
    search: (q?: string, tags?: string, limit = 20) => {
        const params = new URLSearchParams({ limit: String(limit) });
        if (q) params.set("q", q);
        if (tags) params.set("tags", tags);
        return request<Recipe[]>(`/recipes/search?${params}`);
    },
    getDetails: (recipeId: string) => request<Recipe>(`/recipes/${encodeURIComponent(recipeId)}`),
};

export const groceryApi = {
    getShoppingList: (userId: string, daysAhead = 7) =>
        request<ShoppingListResponse>(
            `/grocery/shopping_list/${encodeURIComponent(userId)}?days_ahead=${daysAhead}`,
        ),
    logPurchase: (userId: string, items: { item: string; quantity: number; price: number }[]) =>
        request<Record<string, unknown>>("/grocery/purchase", {
            method: "POST",
            body: JSON.stringify({ user_id: userId, items }),
        }),
    logConsumption: (userId: string, item: string, quantity: number) =>
        request<Record<string, unknown>>("/grocery/consume", {
            method: "POST",
            body: JSON.stringify({ user_id: userId, item, quantity }),
        }),
    predictNextPurchase: (userId: string, item: string) =>
        request<Record<string, unknown>>(
            `/grocery/predict/${encodeURIComponent(userId)}/${encodeURIComponent(item)}`,
        ),
};

export const gamificationApi = {
    getAchievements: (userId: string) =>
        request<{ achievements: Record<string, unknown>[]; total_earned: number }>(
            `/gamification/achievements/${encodeURIComponent(userId)}`,
        ),
    getLeaderboard: (type = "carbon_saved", period = "month", limit = 100) =>
        request<{ leaderboard: LeaderboardEntry[]; type: string; period: string }>(
            `/gamification/leaderboard?leaderboard_type=${encodeURIComponent(type)}&period=${encodeURIComponent(period)}&limit=${limit}`,
        ),
    getUserRank: (userId: string, type = "carbon_saved") =>
        request<Record<string, unknown>>(
            `/gamification/rank/${encodeURIComponent(userId)}?leaderboard_type=${encodeURIComponent(type)}`,
        ),
    getImpactSummary: (userId: string) =>
        request<ImpactSummary>(`/gamification/impact_summary/${encodeURIComponent(userId)}`),
    logMealImpact: (
        userId: string,
        data: { carbon_footprint: number; health_score: number; variety_score: number; taste_rating?: number },
    ) =>
        request<Record<string, unknown>>("/gamification/log_meal", {
            method: "POST",
            body: JSON.stringify({ user_id: userId, ...data }),
        }),
};

export const sustainabilityApi = {
    getData: (userId: string, period = "monthly") =>
        request<SustainabilityData>(
            `/sustainability/${encodeURIComponent(userId)}?period=${encodeURIComponent(period)}`,
        ),
    getCarbonFootprint: (userId: string) =>
        request<CarbonBreakdown>(`/sustainability/carbon-footprint/${encodeURIComponent(userId)}`),
};

export const feedbackApi = {
    logTasteFeedback: (data: {
        user_id: string;
        recipe_id: string;
        rating: number;
        user_genome: number[];
        recipe_profile: number[];
    }) =>
        request<AcceptedFeedback>("/feedback/taste", {
            method: "POST",
            body: JSON.stringify(data),
        }),
    logHealthOutcome: (data: {
        user_id: string;
        actual_weight: number;
        actual_hba1c?: number;
        actual_cholesterol?: number;
        meal_history: Record<string, unknown>[];
        consent_to_store: boolean;
    }) =>
        request<AcceptedFeedback>("/feedback/health", {
            method: "POST",
            body: JSON.stringify(data),
        }),
    logMealSelection: (data: {
        user_id: string;
        state: number[];
        selected_recipe_id: number;
        reward: number;
    }) =>
        request<AcceptedFeedback>("/feedback/meal_selection", {
            method: "POST",
            body: JSON.stringify(data),
        }),
    getModelStats: (modelName: string) =>
        request<Record<string, unknown>>(`/models/stats/${encodeURIComponent(modelName)}`),
};
