import React, { createContext, useContext, useReducer } from 'react';
import { generatePlan, regenerateDay, swapMeal } from '../services/api';

const MealPlanContext = createContext();

// Initial state
const initialState = {
    currentPlan: null,
    planHistory: [],
    loading: false,
    error: null,
};

// Action types
const ACTIONS = {
    SET_PLAN: 'SET_PLAN',
    UPDATE_DAY: 'UPDATE_DAY',
    UPDATE_MEAL: 'UPDATE_MEAL',
    ADD_TO_HISTORY: 'ADD_TO_HISTORY',
    SET_LOADING: 'SET_LOADING',
    SET_ERROR: 'SET_ERROR',
    CLEAR_ERROR: 'CLEAR_ERROR',
};

// Reducer
const mealPlanReducer = (state, action) => {
    switch (action.type) {
        case ACTIONS.SET_PLAN:
            return { ...state, currentPlan: action.payload, loading: false };
        case ACTIONS.UPDATE_DAY:
            const updatedDays = [...state.currentPlan.days];
            updatedDays[action.payload.dayIndex] = action.payload.day;
            return {
                ...state,
                currentPlan: { ...state.currentPlan, days: updatedDays },
                loading: false,
            };
        case ACTIONS.UPDATE_MEAL:
            const days = [...state.currentPlan.days];
            days[action.payload.dayIndex].meals[action.payload.mealSlot] = action.payload.meal;
            return {
                ...state,
                currentPlan: { ...state.currentPlan, days },
                loading: false,
            };
        case ACTIONS.ADD_TO_HISTORY:
            return {
                ...state,
                planHistory: [action.payload, ...state.planHistory].slice(0, 10), // Keep last 10
            };
        case ACTIONS.SET_LOADING:
            return { ...state, loading: action.payload };
        case ACTIONS.SET_ERROR:
            return { ...state, error: action.payload, loading: false };
        case ACTIONS.CLEAR_ERROR:
            return { ...state, error: null };
        default:
            return state;
    }
};

// Provider component
export const MealPlanProvider = ({ children }) => {
    const [state, dispatch] = useReducer(mealPlanReducer, initialState);

    const createPlan = async (profileData) => {
        try {
            dispatch({ type: ACTIONS.SET_LOADING, payload: true });
            const plan = await generatePlan(profileData);
            dispatch({ type: ACTIONS.SET_PLAN, payload: plan });
            dispatch({ type: ACTIONS.ADD_TO_HISTORY, payload: plan });
            return plan;
        } catch (error) {
            dispatch({ type: ACTIONS.SET_ERROR, payload: error.message });
            throw error;
        }
    };

    const regenerateDayPlan = async (userId, dayIndex) => {
        try {
            dispatch({ type: ACTIONS.SET_LOADING, payload: true });
            const updatedDay = await regenerateDay(userId, dayIndex);
            dispatch({ type: ACTIONS.UPDATE_DAY, payload: { dayIndex, day: updatedDay } });
            return updatedDay;
        } catch (error) {
            dispatch({ type: ACTIONS.SET_ERROR, payload: error.message });
            throw error;
        }
    };

    const swapMealSlot = async (userId, dayIndex, mealSlot) => {
        try {
            dispatch({ type: ACTIONS.SET_LOADING, payload: true });
            const newMeal = await swapMeal(userId, dayIndex, mealSlot);
            dispatch({ type: ACTIONS.UPDATE_MEAL, payload: { dayIndex, mealSlot, meal: newMeal } });
            return newMeal;
        } catch (error) {
            dispatch({ type: ACTIONS.SET_ERROR, payload: error.message });
            throw error;
        }
    };

    const setPlan = (plan) => {
        dispatch({ type: ACTIONS.SET_PLAN, payload: plan });
    };

    const clearError = () => {
        dispatch({ type: ACTIONS.CLEAR_ERROR });
    };

    const value = {
        currentPlan: state.currentPlan,
        planHistory: state.planHistory,
        loading: state.loading,
        error: state.error,
        createPlan,
        regenerateDayPlan,
        swapMealSlot,
        setPlan,
        clearError,
    };

    return <MealPlanContext.Provider value={value}>{children}</MealPlanContext.Provider>;
};

// Custom hook
export const useMealPlan = () => {
    const context = useContext(MealPlanContext);
    if (!context) {
        throw new Error('useMealPlan must be used within a MealPlanProvider');
    }
    return context;
};

export default MealPlanContext;
