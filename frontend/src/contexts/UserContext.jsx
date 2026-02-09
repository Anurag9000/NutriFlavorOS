import React, { createContext, useContext, useReducer, useEffect } from 'react';
import { getUserProfile, updateUserProfile } from '../services/api';

const UserContext = createContext();

// Initial state
const initialState = {
    user: null,
    profile: null,
    loading: false,
    error: null,
};

// Action types
const ACTIONS = {
    SET_USER: 'SET_USER',
    SET_PROFILE: 'SET_PROFILE',
    UPDATE_PROFILE: 'UPDATE_PROFILE',
    SET_LOADING: 'SET_LOADING',
    SET_ERROR: 'SET_ERROR',
    CLEAR_ERROR: 'CLEAR_ERROR',
};

// Reducer
const userReducer = (state, action) => {
    switch (action.type) {
        case ACTIONS.SET_USER:
            return { ...state, user: action.payload, loading: false };
        case ACTIONS.SET_PROFILE:
            return { ...state, profile: action.payload, loading: false };
        case ACTIONS.UPDATE_PROFILE:
            return { ...state, profile: { ...state.profile, ...action.payload }, loading: false };
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
export const UserProvider = ({ children }) => {
    const [state, dispatch] = useReducer(userReducer, initialState);

    // Load user profile from localStorage on mount
    useEffect(() => {
        const savedProfile = localStorage.getItem('userProfile');
        if (savedProfile) {
            dispatch({ type: ACTIONS.SET_PROFILE, payload: JSON.parse(savedProfile) });
        }
    }, []);

    // Save profile to localStorage whenever it changes
    useEffect(() => {
        if (state.profile) {
            localStorage.setItem('userProfile', JSON.stringify(state.profile));
        }
    }, [state.profile]);

    const setUser = (user) => {
        dispatch({ type: ACTIONS.SET_USER, payload: user });
    };

    const setProfile = (profile) => {
        dispatch({ type: ACTIONS.SET_PROFILE, payload: profile });
    };

    const updateProfile = async (updates) => {
        try {
            dispatch({ type: ACTIONS.SET_LOADING, payload: true });

            // If we have a user ID, update on backend
            if (state.user?.id) {
                const updated = await updateUserProfile(state.user.id, updates);
                dispatch({ type: ACTIONS.UPDATE_PROFILE, payload: updated });
            } else {
                // Otherwise just update locally
                dispatch({ type: ACTIONS.UPDATE_PROFILE, payload: updates });
            }
        } catch (error) {
            dispatch({ type: ACTIONS.SET_ERROR, payload: error.message });
            throw error;
        }
    };

    const fetchProfile = async (userId) => {
        try {
            dispatch({ type: ACTIONS.SET_LOADING, payload: true });
            const profile = await getUserProfile(userId);
            dispatch({ type: ACTIONS.SET_PROFILE, payload: profile });
        } catch (error) {
            dispatch({ type: ACTIONS.SET_ERROR, payload: error.message });
            throw error;
        }
    };

    const clearError = () => {
        dispatch({ type: ACTIONS.CLEAR_ERROR });
    };

    const value = {
        user: state.user,
        profile: state.profile,
        loading: state.loading,
        error: state.error,
        setUser,
        setProfile,
        updateProfile,
        fetchProfile,
        clearError,
    };

    return <UserContext.Provider value={value}>{children}</UserContext.Provider>;
};

// Custom hook
export const useUser = () => {
    const context = useContext(UserContext);
    if (!context) {
        throw new Error('useUser must be used within a UserProvider');
    }
    return context;
};

export default UserContext;
