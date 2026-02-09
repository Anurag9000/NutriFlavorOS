import React, { createContext, useContext, useReducer, useEffect } from 'react';
import { getAchievements, getLeaderboard, getStreak, getImpactMetrics } from '../services/api';

const GamificationContext = createContext();

// Initial state
const initialState = {
    achievements: [],
    leaderboards: {},
    streak: 0,
    impactMetrics: null,
    loading: false,
    error: null,
};

// Action types
const ACTIONS = {
    SET_ACHIEVEMENTS: 'SET_ACHIEVEMENTS',
    UNLOCK_ACHIEVEMENT: 'UNLOCK_ACHIEVEMENT',
    SET_LEADERBOARD: 'SET_LEADERBOARD',
    SET_STREAK: 'SET_STREAK',
    SET_IMPACT_METRICS: 'SET_IMPACT_METRICS',
    SET_LOADING: 'SET_LOADING',
    SET_ERROR: 'SET_ERROR',
    CLEAR_ERROR: 'CLEAR_ERROR',
};

// Reducer
const gamificationReducer = (state, action) => {
    switch (action.type) {
        case ACTIONS.SET_ACHIEVEMENTS:
            return { ...state, achievements: action.payload, loading: false };
        case ACTIONS.UNLOCK_ACHIEVEMENT:
            return {
                ...state,
                achievements: state.achievements.map((ach) =>
                    ach.id === action.payload.id ? { ...ach, unlocked: true } : ach
                ),
            };
        case ACTIONS.SET_LEADERBOARD:
            return {
                ...state,
                leaderboards: { ...state.leaderboards, [action.payload.type]: action.payload.data },
                loading: false,
            };
        case ACTIONS.SET_STREAK:
            return { ...state, streak: action.payload, loading: false };
        case ACTIONS.SET_IMPACT_METRICS:
            return { ...state, impactMetrics: action.payload, loading: false };
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
export const GamificationProvider = ({ children }) => {
    const [state, dispatch] = useReducer(gamificationReducer, initialState);

    const fetchAchievements = async (userId) => {
        try {
            dispatch({ type: ACTIONS.SET_LOADING, payload: true });
            const achievements = await getAchievements(userId);
            dispatch({ type: ACTIONS.SET_ACHIEVEMENTS, payload: achievements });
        } catch (error) {
            dispatch({ type: ACTIONS.SET_ERROR, payload: error.message });
        }
    };

    const fetchLeaderboard = async (type, period = 'monthly') => {
        try {
            dispatch({ type: ACTIONS.SET_LOADING, payload: true });
            const data = await getLeaderboard(type, period);
            dispatch({ type: ACTIONS.SET_LEADERBOARD, payload: { type, data } });
        } catch (error) {
            dispatch({ type: ACTIONS.SET_ERROR, payload: error.message });
        }
    };

    const fetchStreak = async (userId) => {
        try {
            const streak = await getStreak(userId);
            dispatch({ type: ACTIONS.SET_STREAK, payload: streak });
        } catch (error) {
            dispatch({ type: ACTIONS.SET_ERROR, payload: error.message });
        }
    };

    const fetchImpactMetrics = async (userId) => {
        try {
            const metrics = await getImpactMetrics(userId);
            dispatch({ type: ACTIONS.SET_IMPACT_METRICS, payload: metrics });
        } catch (error) {
            dispatch({ type: ACTIONS.SET_ERROR, payload: error.message });
        }
    };

    const unlockAchievement = (achievementId) => {
        dispatch({ type: ACTIONS.UNLOCK_ACHIEVEMENT, payload: { id: achievementId } });
    };

    const clearError = () => {
        dispatch({ type: ACTIONS.CLEAR_ERROR });
    };

    const value = {
        achievements: state.achievements,
        leaderboards: state.leaderboards,
        streak: state.streak,
        impactMetrics: state.impactMetrics,
        loading: state.loading,
        error: state.error,
        fetchAchievements,
        fetchLeaderboard,
        fetchStreak,
        fetchImpactMetrics,
        unlockAchievement,
        clearError,
    };

    return <GamificationContext.Provider value={value}>{children}</GamificationContext.Provider>;
};

// Custom hook
export const useGamification = () => {
    const context = useContext(GamificationContext);
    if (!context) {
        throw new Error('useGamification must be used within a GamificationProvider');
    }
    return context;
};

export default GamificationContext;
