/**
 * ⚠️ DEPRECATED - DO NOT USE THIS FILE ⚠️
 * 
 * This file contains mock data that was used for development.
 * All pages should now connect to the real backend API.
 * 
 * If you see imports from this file, they should be removed and replaced
 * with proper API calls using the hooks from @/hooks/useApi.ts
 */

// ─── Meals ───
export interface Meal {
  id: string;
  name: string;
  type: "breakfast" | "lunch" | "dinner" | "snack";
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
  sustainabilityScore: number; // 1-10
  image?: string;
}

export interface DayPlan {
  day: string;
  meals: Meal[];
}

// ... rest of the file remains for TypeScript interfaces only
// All actual mock data arrays have been removed or should not be used
