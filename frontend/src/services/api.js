import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api/v1';

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
    const response = await api.post('/meals/generate', profileData);
    return response.data;
};

export const regenerateDay = async (userId, dayIndex) => {
    const response = await api.post('/meals/regenerate_day', { user_id: userId, day_index: dayIndex });
    return response.data;
};

export const swapMeal = async (userId, dayIndex, mealSlot) => {
    const response = await api.post('/meals/swap_meal', {
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
    const response = await api.post('/learning/feedback/taste', {
        user_id: userId,
        recipe_id: mealId, // Backend expects recipe_id
        rating,
        // Mocking user_genome and recipe_profile for now as they are required by backend model
        user_genome: [0.5, 0.5, 0.5],
        recipe_profile: [0.5, 0.5, 0.5]
    });
    return response.data;
};

export const logMeal = async (userId, mealData) => {
    // aligning with backend/api/online_learning_routes.py: log_meal_selection
    const response = await api.post('/learning/feedback/meal_selection', {
        user_id: userId,
        ...mealData,
    });
    return response.data;
};

// ============================================================================
// GAMIFICATION
// ============================================================================

export const getAchievements = async (userId) => {
    const response = await api.get(`/gamification/achievements/${userId}`);
    return response.data;
};

export const getLeaderboard = async (type = 'carbon_saved', period = 'monthly') => {
    const response = await api.get('/gamification/leaderboard', {
        params: { leaderboard_type: type, period }, // Backend expects leaderboard_type
    });
    return response.data;
};

export const getStreak = async (userId) => {
    // Mocking streak endpoint if not yet in backend
    // Or we can add it to gamification routes
    const response = await api.get(`/gamification/impact_summary/${userId}`);
    return response.data; // Impact summary might contain streak or we create specific endpoint
};

export const getImpactMetrics = async (userId) => {
    const response = await api.get(`/gamification/impact_summary/${userId}`);
    return response.data;
};

// ============================================================================
// GROCERY & INVENTORY
// ============================================================================

export const getGroceryList = async (userId) => {
    const response = await api.get(`/grocery/shopping_list/${userId}`);
    return response.data;
};

export const getGroceryPredictions = async (userId) => {
    // Backend: /grocery/predict/{user_id}/{item}
    // This frontend function seems to imply getting ALL predictions.
    // We might need a new endpoint in backend or iterate.
    // For now, let's assume we want general predictions, maybe via shopping list or a new endpoint.
    // Let's use shopping list as a proxy or create a specific endpoint in backend later.
    const response = await api.get(`/grocery/shopping_list/${userId}`);
    return response.data;
};

export const updateInventory = async (userId, itemId, quantity) => {
    const response = await api.post('/grocery/consume', {
        user_id: userId,
        item: itemId,
        quantity,
    });
    return response.data;
};

export const logPurchase = async (userId, items) => {
    const response = await api.post('/grocery/purchase', {
        user_id: userId,
        items,
    });
    return response.data;
};

// ============================================================================
// ANALYTICS & INSIGHTS
// ============================================================================

export const getHealthInsights = async (userId, period = '30d') => {
    const response = await api.get(`/analytics/health/${userId}`, {
        params: { period },
    });
    return response.data;
};

export const getTasteInsights = async (userId) => {
    const response = await api.get(`/analytics/taste/${userId}`);
    return response.data;
};

export const getVarietyInsights = async (userId) => {
    const response = await api.get(`/analytics/variety/${userId}`);
    return response.data;
};

export const predictHealth = async (userId, days = 30) => {
    const response = await api.post('/analytics/predict_health', {
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
    const response = await api.get(`/sustainability/carbon/${userId}`);
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

    const response = await api.post('/vision/analyze', formData, {
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
