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

export const todayMeals: Meal[] = [
  { id: "m1", name: "Greek Yogurt Bowl", type: "breakfast", calories: 380, protein: 22, carbs: 45, fat: 12, sustainabilityScore: 8 },
  { id: "m2", name: "Grilled Chicken Salad", type: "lunch", calories: 520, protein: 38, carbs: 28, fat: 22, sustainabilityScore: 7 },
  { id: "m3", name: "Salmon & Roasted Vegetables", type: "dinner", calories: 640, protein: 42, carbs: 35, fat: 28, sustainabilityScore: 6 },
  { id: "m4", name: "Mixed Nuts & Apple", type: "snack", calories: 220, protein: 6, carbs: 18, fat: 14, sustainabilityScore: 9 },
];

export const weeklyPlan: DayPlan[] = [
  { day: "Monday", meals: todayMeals },
  { day: "Tuesday", meals: [
    { id: "t1", name: "Overnight Oats", type: "breakfast", calories: 340, protein: 14, carbs: 52, fat: 10, sustainabilityScore: 9 },
    { id: "t2", name: "Lentil Soup & Bread", type: "lunch", calories: 480, protein: 24, carbs: 62, fat: 12, sustainabilityScore: 9 },
    { id: "t3", name: "Beef Stir-Fry", type: "dinner", calories: 580, protein: 36, carbs: 42, fat: 24, sustainabilityScore: 4 },
    { id: "t4", name: "Hummus & Veggies", type: "snack", calories: 180, protein: 8, carbs: 20, fat: 8, sustainabilityScore: 9 },
  ]},
  { day: "Wednesday", meals: [
    { id: "w1", name: "Smoothie Bowl", type: "breakfast", calories: 360, protein: 16, carbs: 54, fat: 8, sustainabilityScore: 8 },
    { id: "w2", name: "Quinoa Buddha Bowl", type: "lunch", calories: 510, protein: 20, carbs: 58, fat: 18, sustainabilityScore: 9 },
    { id: "w3", name: "Baked Cod & Sweet Potato", type: "dinner", calories: 490, protein: 38, carbs: 40, fat: 16, sustainabilityScore: 7 },
    { id: "w4", name: "Dark Chocolate & Berries", type: "snack", calories: 160, protein: 4, carbs: 22, fat: 8, sustainabilityScore: 7 },
  ]},
  { day: "Thursday", meals: [
    { id: "th1", name: "Avocado Toast", type: "breakfast", calories: 320, protein: 12, carbs: 32, fat: 18, sustainabilityScore: 7 },
    { id: "th2", name: "Turkey Wrap", type: "lunch", calories: 460, protein: 30, carbs: 38, fat: 18, sustainabilityScore: 6 },
    { id: "th3", name: "Vegetable Curry", type: "dinner", calories: 520, protein: 18, carbs: 60, fat: 20, sustainabilityScore: 9 },
    { id: "th4", name: "Protein Bar", type: "snack", calories: 200, protein: 20, carbs: 22, fat: 8, sustainabilityScore: 5 },
  ]},
  { day: "Friday", meals: [
    { id: "f1", name: "Eggs Benedict", type: "breakfast", calories: 440, protein: 24, carbs: 28, fat: 26, sustainabilityScore: 5 },
    { id: "f2", name: "Poke Bowl", type: "lunch", calories: 540, protein: 32, carbs: 52, fat: 16, sustainabilityScore: 6 },
    { id: "f3", name: "Pasta Primavera", type: "dinner", calories: 560, protein: 18, carbs: 72, fat: 18, sustainabilityScore: 8 },
    { id: "f4", name: "Trail Mix", type: "snack", calories: 240, protein: 8, carbs: 24, fat: 14, sustainabilityScore: 8 },
  ]},
  { day: "Saturday", meals: [
    { id: "s1", name: "Pancakes & Fruit", type: "breakfast", calories: 420, protein: 12, carbs: 64, fat: 14, sustainabilityScore: 7 },
    { id: "s2", name: "Grilled Veggie Sandwich", type: "lunch", calories: 380, protein: 16, carbs: 42, fat: 16, sustainabilityScore: 9 },
    { id: "s3", name: "Herb-Crusted Chicken", type: "dinner", calories: 580, protein: 44, carbs: 28, fat: 28, sustainabilityScore: 6 },
    { id: "s4", name: "Edamame", type: "snack", calories: 150, protein: 14, carbs: 10, fat: 6, sustainabilityScore: 9 },
  ]},
  { day: "Sunday", meals: [
    { id: "su1", name: "Açai Bowl", type: "breakfast", calories: 380, protein: 10, carbs: 58, fat: 12, sustainabilityScore: 6 },
    { id: "su2", name: "Chicken Caesar Salad", type: "lunch", calories: 480, protein: 34, carbs: 18, fat: 28, sustainabilityScore: 6 },
    { id: "su3", name: "Mushroom Risotto", type: "dinner", calories: 540, protein: 16, carbs: 68, fat: 20, sustainabilityScore: 8 },
    { id: "su4", name: "Greek Yogurt", type: "snack", calories: 140, protein: 16, carbs: 12, fat: 4, sustainabilityScore: 8 },
  ]},
];

// ─── Pillar Scores ───
export const pillarScores = {
  health: 82,
  taste: 88,
  variety: 74,
  sustainability: 79,
};

// ─── Dashboard Metrics ───
export const dashboardMetrics = {
  calories: { current: 1760, target: 2100 },
  protein: { current: 108, target: 130 },
  streak: 14,
  weeklyScore: 81,
};

// ─── Analytics Data ───
export const weeklyTrends = [
  { day: "Mon", health: 78, taste: 85, variety: 70, sustainability: 82, calories: 1820 },
  { day: "Tue", health: 80, taste: 82, variety: 72, sustainability: 78, calories: 1760 },
  { day: "Wed", health: 84, taste: 88, variety: 78, sustainability: 80, calories: 1900 },
  { day: "Thu", health: 76, taste: 84, variety: 68, sustainability: 76, calories: 1680 },
  { day: "Fri", health: 82, taste: 90, variety: 75, sustainability: 74, calories: 1950 },
  { day: "Sat", health: 86, taste: 86, variety: 80, sustainability: 82, calories: 2020 },
  { day: "Sun", health: 82, taste: 88, variety: 74, sustainability: 79, calories: 1760 },
];

export const macroDistribution = [
  { name: "Protein", value: 30, color: "hsl(152, 60%, 48%)" },
  { name: "Carbs", value: 45, color: "hsl(38, 92%, 55%)" },
  { name: "Fat", value: 25, color: "hsl(265, 60%, 58%)" },
];

// ─── Grocery Predictions ───
export interface GroceryItem {
  id: string;
  name: string;
  category: string;
  quantity: string;
  frequency: string;
  confidence: number;
}

export const groceryItems: GroceryItem[] = [
  { id: "g1", name: "Chicken Breast", category: "Protein", quantity: "1.5 kg", frequency: "Weekly", confidence: 94 },
  { id: "g2", name: "Salmon Fillet", category: "Protein", quantity: "600g", frequency: "Weekly", confidence: 88 },
  { id: "g3", name: "Greek Yogurt", category: "Dairy", quantity: "1 kg", frequency: "Weekly", confidence: 96 },
  { id: "g4", name: "Eggs", category: "Dairy", quantity: "12 pcs", frequency: "Weekly", confidence: 92 },
  { id: "g5", name: "Spinach", category: "Produce", quantity: "300g", frequency: "Weekly", confidence: 90 },
  { id: "g6", name: "Avocados", category: "Produce", quantity: "4 pcs", frequency: "Weekly", confidence: 85 },
  { id: "g7", name: "Sweet Potatoes", category: "Produce", quantity: "1 kg", frequency: "Weekly", confidence: 82 },
  { id: "g8", name: "Brown Rice", category: "Pantry", quantity: "1 kg", frequency: "Bi-weekly", confidence: 78 },
  { id: "g9", name: "Quinoa", category: "Pantry", quantity: "500g", frequency: "Bi-weekly", confidence: 80 },
  { id: "g10", name: "Olive Oil", category: "Pantry", quantity: "500ml", frequency: "Monthly", confidence: 95 },
  { id: "g11", name: "Blueberries", category: "Produce", quantity: "250g", frequency: "Weekly", confidence: 76 },
  { id: "g12", name: "Almonds", category: "Pantry", quantity: "200g", frequency: "Bi-weekly", confidence: 84 },
  { id: "g13", name: "Broccoli", category: "Produce", quantity: "500g", frequency: "Weekly", confidence: 88 },
  { id: "g14", name: "Oats", category: "Pantry", quantity: "500g", frequency: "Bi-weekly", confidence: 90 },
  { id: "g15", name: "Lentils", category: "Pantry", quantity: "500g", frequency: "Bi-weekly", confidence: 72 },
];

// ─── Achievements ───
export interface Achievement {
  id: string;
  title: string;
  description: string;
  category: "consistency" | "diversity" | "sustainability" | "milestone";
  progress: number; // 0-100
  unlocked: boolean;
  icon: string;
  xp: number;
}

export const achievements: Achievement[] = [
  { id: "a1", title: "Week Warrior", description: "Log meals for 7 consecutive days", category: "consistency", progress: 100, unlocked: true, icon: "🔥", xp: 100 },
  { id: "a2", title: "Fortnight Focus", description: "Maintain a 14-day streak", category: "consistency", progress: 100, unlocked: true, icon: "⚡", xp: 200 },
  { id: "a3", title: "Month Master", description: "Complete 30 days of tracking", category: "consistency", progress: 68, unlocked: false, icon: "🏆", xp: 500 },
  { id: "a4", title: "World Palate", description: "Try cuisines from 10 different cultures", category: "diversity", progress: 70, unlocked: false, icon: "🌍", xp: 300 },
  { id: "a5", title: "Rainbow Plate", description: "Eat 5 different colored foods in one day", category: "diversity", progress: 100, unlocked: true, icon: "🌈", xp: 150 },
  { id: "a6", title: "Protein Pro", description: "Hit protein goals for 7 days straight", category: "milestone", progress: 85, unlocked: false, icon: "💪", xp: 250 },
  { id: "a7", title: "Green Guardian", description: "Achieve 80%+ sustainability for a week", category: "sustainability", progress: 60, unlocked: false, icon: "🌱", xp: 300 },
  { id: "a8", title: "Zero Waste Week", description: "Use all predicted groceries without waste", category: "sustainability", progress: 40, unlocked: false, icon: "♻️", xp: 400 },
  { id: "a9", title: "First Steps", description: "Complete your first day of tracking", category: "milestone", progress: 100, unlocked: true, icon: "👣", xp: 50 },
  { id: "a10", title: "Macro Master", description: "Hit all macro targets for 5 days", category: "milestone", progress: 90, unlocked: false, icon: "📊", xp: 350 },
];

export const userStats = {
  level: 8,
  currentXP: 1150,
  nextLevelXP: 1500,
  totalAchievements: achievements.length,
  unlockedAchievements: achievements.filter((a) => a.unlocked).length,
};
