import React, { createContext, useContext, useReducer } from 'react';
import { getGroceryList, getGroceryPredictions, updateInventory, logPurchase } from '../services/api';

const GroceryContext = createContext();

// Initial state
const initialState = {
    shoppingList: [],
    predictions: [],
    inventory: [],
    loading: false,
    error: null,
};

// Action types
const ACTIONS = {
    SET_SHOPPING_LIST: 'SET_SHOPPING_LIST',
    SET_PREDICTIONS: 'SET_PREDICTIONS',
    SET_INVENTORY: 'SET_INVENTORY',
    UPDATE_ITEM: 'UPDATE_ITEM',
    TOGGLE_ITEM: 'TOGGLE_ITEM',
    SET_LOADING: 'SET_LOADING',
    SET_ERROR: 'SET_ERROR',
    CLEAR_ERROR: 'CLEAR_ERROR',
};

// Reducer
const groceryReducer = (state, action) => {
    switch (action.type) {
        case ACTIONS.SET_SHOPPING_LIST:
            return { ...state, shoppingList: action.payload, loading: false };
        case ACTIONS.SET_PREDICTIONS:
            return { ...state, predictions: action.payload, loading: false };
        case ACTIONS.SET_INVENTORY:
            return { ...state, inventory: action.payload, loading: false };
        case ACTIONS.UPDATE_ITEM:
            return {
                ...state,
                inventory: state.inventory.map((item) =>
                    item.id === action.payload.id ? { ...item, ...action.payload.updates } : item
                ),
                loading: false,
            };
        case ACTIONS.TOGGLE_ITEM:
            return {
                ...state,
                shoppingList: state.shoppingList.map((item) =>
                    item.id === action.payload ? { ...item, checked: !item.checked } : item
                ),
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
export const GroceryProvider = ({ children }) => {
    const [state, dispatch] = useReducer(groceryReducer, initialState);

    const fetchShoppingList = async (userId) => {
        try {
            dispatch({ type: ACTIONS.SET_LOADING, payload: true });
            const list = await getGroceryList(userId);
            dispatch({ type: ACTIONS.SET_SHOPPING_LIST, payload: list });
        } catch (error) {
            dispatch({ type: ACTIONS.SET_ERROR, payload: error.message });
        }
    };

    const fetchPredictions = async (userId) => {
        try {
            dispatch({ type: ACTIONS.SET_LOADING, payload: true });
            const predictions = await getGroceryPredictions(userId);
            dispatch({ type: ACTIONS.SET_PREDICTIONS, payload: predictions });
        } catch (error) {
            dispatch({ type: ACTIONS.SET_ERROR, payload: error.message });
        }
    };

    const updateItem = async (userId, itemId, quantity) => {
        try {
            dispatch({ type: ACTIONS.SET_LOADING, payload: true });
            await updateInventory(userId, itemId, quantity);
            dispatch({ type: ACTIONS.UPDATE_ITEM, payload: { id: itemId, updates: { quantity } } });
        } catch (error) {
            dispatch({ type: ACTIONS.SET_ERROR, payload: error.message });
        }
    };

    const recordPurchase = async (userId, items) => {
        try {
            dispatch({ type: ACTIONS.SET_LOADING, payload: true });
            await logPurchase(userId, items);
            // Refresh shopping list and predictions after purchase
            await fetchShoppingList(userId);
            await fetchPredictions(userId);
        } catch (error) {
            dispatch({ type: ACTIONS.SET_ERROR, payload: error.message });
        }
    };

    const toggleItem = (itemId) => {
        dispatch({ type: ACTIONS.TOGGLE_ITEM, payload: itemId });
    };

    const clearError = () => {
        dispatch({ type: ACTIONS.CLEAR_ERROR });
    };

    const value = {
        shoppingList: state.shoppingList,
        predictions: state.predictions,
        inventory: state.inventory,
        loading: state.loading,
        error: state.error,
        fetchShoppingList,
        fetchPredictions,
        updateItem,
        recordPurchase,
        toggleItem,
        clearError,
    };

    return <GroceryContext.Provider value={value}>{children}</GroceryContext.Provider>;
};

// Custom hook
export const useGrocery = () => {
    const context = useContext(GroceryContext);
    if (!context) {
        throw new Error('useGrocery must be used within a GroceryProvider');
    }
    return context;
};

export default GroceryContext;
