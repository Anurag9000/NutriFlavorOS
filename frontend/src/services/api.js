import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

// Create axios instance with default config
const api = axios.create({
    baseURL: API_BASE_URL,
    timeout: 30000,
    headers: {
        'Content-Type': 'application/json',
    },
});

// ============================================================================
// MEAL PLANNING
// ============================================================================

export const generatePlan = async (profileData) => {
    const response = await api.post('/generate_plan', profileData);
    return response.data;
};

export const regenerateDay = async (userId, dayIndex) => {
    const response = await api.post('/regenerate_day', { user_id: userId, day_index: dayIndex });
    return response.data;
};

export const swapMeal = async (userId, dayIndex, mealSlot) => {
    const response = await api.post('/swap_meal', {
        user_id: userId,
        day_index: dayIndex,
        meal_slot: mealSlot
    });
    return response.data;
};

// ============================================================================
// ONLINE LEARNING & FEEDBACK
// ============================================================================

export const rateMeal = async (userId, mealId, rating, feedback = null) => {
    const response = await api.post('/rate_meal', {
        user_id: userId,
        meal_id: mealId,
        rating,
        feedback,
    });
    return response.data;
};

export const logMeal = async (userId, mealData) => {
    const response = await api.post('/log_meal', {
        user_id: userId,
        ...mealData,
    });
    return response.data;
};

// ============================================================================
// GAMIFICATION
// ============================================================================

export const getAchievements = async (userId) => {
    const response = await api.get(`/achievements/${userId}`);
    return response.data;
};

export const getLeaderboard = async (type = 'carbon_saved', period = 'monthly') => {
    const response = await api.get('/leaderboard', {
        params: { type, period },
    });
    return response.data;
};

export const getStreak = async (userId) => {
    const response = await api.get(`/streak/${userId}`);
    return response.data;
};

export const getImpactMetrics = async (userId) => {
    const response = await api.get(`/impact_metrics/${userId}`);
    return response.data;
};

// ============================================================================
// GROCERY & INVENTORY
// ============================================================================

export const getGroceryList = async (userId) => {
    const response = await api.get(`/grocery_list/${userId}`);
    return response.data;
};

export const getGroceryPredictions = async (userId) => {
    const response = await api.get(`/grocery_predictions/${userId}`);
    return response.data;
};

export const updateInventory = async (userId, itemId, quantity) => {
    const response = await api.post('/update_inventory', {
        user_id: userId,
        item_id: itemId,
        quantity,
    });
    return response.data;
};

export const logPurchase = async (userId, items) => {
    const response = await api.post('/log_purchase', {
        user_id: userId,
        items,
    });
    return response.data;
};

// ============================================================================
// ANALYTICS & INSIGHTS
// ============================================================================

export const getHealthInsights = async (userId, period = '30d') => {
    const response = await api.get(`/health_insights/${userId}`, {
        params: { period },
    });
    return response.data;
};

export const getTasteInsights = async (userId) => {
    const response = await api.get(`/taste_insights/${userId}`);
    return response.data;
};

export const getVarietyInsights = async (userId) => {
    const response = await api.get(`/variety_insights/${userId}`);
    return response.data;
};

export const predictHealth = async (userId, days = 30) => {
    const response = await api.post('/predict_health', {
        user_id: userId,
        forecast_days: days,
    });
    return response.data;
};

// ============================================================================
// SUSTAINABILITY
// ============================================================================

export const getSustainabilityData = async (userId, period = 'monthly') => {
    const response = await api.get(`/sustainability/${userId}`, {
        params: { period },
    });
    return response.data;
};

export const getCarbonFootprint = async (userId) => {
    const response = await api.get(`/carbon_footprint/${userId}`);
    return response.data;
};

// ============================================================================
// USER PROFILE
// ============================================================================

export const getUserProfile = async (userId) => {
    const response = await api.get(`/user/${userId}`);
    return response.data;
};

export const updateUserProfile = async (userId, profileData) => {
    const response = await api.put(`/user/${userId}`, profileData);
    return response.data;
};

export const addHealthCondition = async (userId, condition) => {
    const response = await api.post(`/user/${userId}/health_condition`, { condition });
    return response.data;
};

export const addMedication = async (userId, medication) => {
    const response = await api.post(`/user/${userId}/medication`, { medication });
    return response.data;
};

// ============================================================================
// RECIPE & VISION
// ============================================================================

export const analyzeImage = async (imageFile) => {
    const formData = new FormData();
    formData.append('image', imageFile);

    const response = await api.post('/analyze_image', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });
    return response.data;
};

export const searchRecipes = async (query, filters = {}) => {
    const response = await api.get('/recipes/search', {
        params: { q: query, ...filters },
    });
    return response.data;
};

export const getRecipeDetails = async (recipeId) => {
    const response = await api.get(`/recipes/${recipeId}`);
    return response.data;
};

// ============================================================================
// ERROR HANDLING
// ============================================================================

api.interceptors.response.use(
    (response) => response,
    (error) => {
        console.error('API Error:', error.response?.data || error.message);
        throw error;
    }
);

export default api;
