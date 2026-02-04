# Unused API Endpoint Integration Strategy

**Objective:** Achieve 100% utilization of all 73 available API endpoints to maximize the "Nutrition Operating System" capabilities.

## 📊 Status Overview
- **Total Endpoints:** 73
- **Currently Used:** 18
- **Target for Integration:** 55 unused endpoints

---

## 🍳 RecipeDB Strategy (15 Unused Endpoints)

### A. Advanced Search & Discovery
**Goal:** Replace local filtering with server-side API power for speed and breadth.

1. **`search-recipe/{id}` & `recipeByTitle`**
   - **Plan:** Implement an "Instant Search" bar in the UI header.
   - **Usage:** As user types, call `recipeByTitle` for robust autocomplete instead of filtering local mock DB.

2. **`recipes-by-carbs`, `protein-range`, `calories`**
   - **Plan:** Build a "Macro-Precision Finder" feature.
   - **Usage:** In the "Swap Meal" interface, allow users to find replacements that EXACTLY match the macro gap (e.g., "Find me a dinner with 25-30g protein and <500 calories").

3. **`recipes_cuisine/cuisine/{region}`**
   - **Plan:** enhance Variety Engine.
   - **Usage:** Instead of just tracking variety, *proactively* fetch recipes from unexplored regions when the Variety Engine detects a "cuisine rut."

4. **`recipes-method/{method}` & `bydetails/utensils`**
   - **Plan:** "Kitchen Inventory Match."
   - **Usage:** specific onboarding step: "What equipment do you have?" (Air Fryer, Blender, etc.). Filter recommendations to only show recipes compatible with user's hardware.

### B. Dietary Intelligence
5. **`region-diet` & `recipe-diet`**
   - **Plan:** Cultural Diet Overlay.
   - **Usage:** Cross-reference user's cultural background with `region-diet` to suggest "Comfort Foods" that fit their nutritional goals.

6. **`by-ingredients-categories-title`**
   - **Plan:** "The Pantry Chef" (Reverse Search).
   - **Usage:** User inputs 3 random ingredients they have; API returns valid recipes.

---

## 🌶️ FlavorDB Strategy (27 Unused Endpoints)

### A. Molecular Safety & Science
1. **`by-fema`, `by-jecfa`, `by-efsa`, `by-coe`** (Regulatory Bodies)
   - **Plan:** "Global Safety Audit" Badge.
   - **Usage:** For every ingredient in a plan, display a "Safety Verification" checkmark. If an ingredient is approved by FEMA (flavor extract manufacturers) but not EFSA, flag it for user review.

2. **`by-naturalOccurrence`**
   - **Plan:** "Natural vs. Synthetic" Meter.
   - **Usage:** Calculate a percentage score for every meal: "98% Natural Origin." Use this to prioritize whole food ingredients over processed additives.

### B. Deep Chemical Analysis
3. **`by-functionalGroups` (Expanded Use)**
   - **Plan:** "Functional Mood Matching."
   - **Usage:** Correlate specific functional groups (e.g., esters -> fruity/calming) with user mood logs.

4. **`by-monoisotopicMass`, `by-alogp` (Lipophilicity)**
   - **Plan:** "Flavor Lingering Prediction."
   - **Usage:** Use logP (solubility) to predict how long a flavor stays on the palate. Heavy molecules (high logP) linger long. Suggest "Palate Cleanser" pairings for heavy meals.

5. **`by-aromaThresholdValues` (Expanded)**
   - **Plan:** "Smell-Before-You-Eat" AR Feature.
   - **Usage:** Visualize aroma clouds in AR. High threshold = small cloud, Low threshold = giant cloud.

---

## 💊 DietRxDB Strategy (9 Unused Endpoints)

### A. Medical Personalization (High Impact)
1. **`disease/{diseaseName}` & `all-details`**
   - **Plan:** "Condition-Specific Meal Plans" (Premium Feature).
   - **Usage:** If user indicates "Diabetes," fetch all associated positive/negative food interactions. Hard-filter the Plan Generator to exclude contraindicated foods.

2. **`gene-source/{foodName}`**
   - **Plan:** Nutrigenomics Explorer.
   - **Usage:** Show users *why* certain foods interact with their biology. "This broccoli interacts with the GSTM1 gene, helping your detox pathways."

3. **`drug-food-interactions`**
   - **Plan:** "Medication Safety Check."
   - **Usage:** User scans their pill bottle. App checks every meal plan against known interactions (e.g., Grapefruit vs. Statins).

4. **`publication/{foodName}`**
   - **Plan:** "Evidence-Based Eating."
   - **Usage:** Add a "Science" tab to every recipe. List the number of research papers backing the health benefits of its main ingredients.

---

## 🌱 SustainableFoodDB Strategy (4 Unused Endpoints)

1. **`search` & `by-ingredient`**
   - **Plan:** "Eco-Swap" smart button.
   - **Usage:** If a user modifies a plan to add "Beef," proactively search for "Impossible Burger" or "Lentils" and show the Carbon Delta immediately (-90% CO2).

2. **`carbon-footprint-sum`**
   - **Plan:** "Climate Impact Dashboard."
   - **Usage:** Visualize valid total footprint history vs. national average. Gamify the reduction using `carbon_saved_kg` in the Gamification Engine.

---

## 🚀 Implementation Timeline for "Total Usage"

| Phase | Usage Area | Est. Time | Value Prop |
|-------|------------|-----------|------------|
| **1** | Recipe Search & Utensils | 1 Week | UX Convenience |
| **2** | DietRx Medical Filters | 2 Weeks | B2B/Medical Sales |
| **3** | FlavorDB Safety Checks | 3 Days | Trust & Transparency |
| **4** | Sustainable Swaps | 1 Week | Gen Z/Climate Market |
| **5** | Deep Molecular Logic | 2 Weeks | "Hard Tech" Differentiator |

**Total Time to 100% Usage:** ~6 Weeks of Engineering.
