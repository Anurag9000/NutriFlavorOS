import React, { useState } from 'react';
import { Search, Filter, Clock, Flame, ChefHat, X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import RecipeCard from '../RecipeCard';
import RecipeDetailModal from '../meals/RecipeDetailModal';

// Mock data for search results since we don't have a real search API yet
const MOCK_RESULTS = [
    {
        id: 's1',
        name: 'Quinoa Buddha Bowl',
        description: 'Nutrient-packed bowl with roasted veggies and tahini dressing',
        calories: 450,
        macros: { protein: 18, carbs: 55, fat: 16 },
        tags: ['Vegan', 'Gluten-Free', 'High-Fiber'],
        ingredients: ['Quinoa', 'Chickpeas', 'Sweet Potato', 'Kale', 'Tahini'],
        flavor_profile: { Salty: 0.4, Sweet: 0.3, Sour: 0.2, Spicy: 0.1, Umami: 0.6, Bitter: 0.2 }
    },
    {
        id: 's2',
        name: 'Spicy Salmon Tacos',
        description: 'Grilled salmon with mango salsa and chipotle mayo',
        calories: 520,
        macros: { protein: 32, carbs: 35, fat: 22 },
        tags: ['Pescatarian', 'High-Protein', 'Spicy'],
        ingredients: ['Salmon', 'Corn Tortillas', 'Mango', 'Chipotle', 'Cabbage'],
        flavor_profile: { Salty: 0.5, Sweet: 0.4, Sour: 0.6, Spicy: 0.8, Umami: 0.7, Bitter: 0.1 }
    },
    {
        id: 's3',
        name: 'Mushroom Risotto',
        description: 'Creamy arborio rice with wild mushrooms and parmesan',
        calories: 600,
        macros: { protein: 14, carbs: 65, fat: 28 },
        tags: ['Vegetarian', 'Comfort Food', 'Italian'],
        ingredients: ['Arborio Rice', 'Mushrooms', 'Parmesan', 'White Wine', 'Butter'],
        flavor_profile: { Salty: 0.6, Sweet: 0.2, Sour: 0.2, Spicy: 0.0, Umami: 0.9, Bitter: 0.1 }
    }
];

export default function RecipeSearch() {
    const [query, setQuery] = useState('');
    const [activeFilter, setActiveFilter] = useState('All');
    const [isSearching, setIsSearching] = useState(false);
    const [results, setResults] = useState([]);
    const [selectedRecipe, setSelectedRecipe] = useState(null);

    const handleSearch = (e) => {
        e.preventDefault();
        if (!query.trim()) return;

        setIsSearching(true);
        // Simulate API call
        setTimeout(() => {
            const filtered = MOCK_RESULTS.filter(r =>
                r.name.toLowerCase().includes(query.toLowerCase()) ||
                r.tags.some(t => t.toLowerCase().includes(query.toLowerCase()))
            );
            setResults(filtered.length > 0 ? filtered : MOCK_RESULTS); // Fallback to mock if no match
            setIsSearching(false);
        }, 800);
    };

    return (
        <div className="space-y-6">
            <h2 className="text-xl font-semibold">Find Recipes</h2>

            {/* Search Bar */}
            <form onSubmit={handleSearch} className="relative">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" size={20} />
                <input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Search by name, ingredient, or tag..."
                    className="w-full bg-black/40 border border-white/10 rounded-xl py-4 pl-12 pr-4 focus:outline-none focus:border-primary transition-colors"
                />
            </form>

            {/* Filters */}
            <div className="flex gap-2 overflow-x-auto pb-2">
                {['All', 'High Protein', 'Vegan', 'Under 30min', 'Breakfast', 'Dinner'].map(filter => (
                    <button
                        key={filter}
                        onClick={() => setActiveFilter(filter)}
                        className={`px-4 py-2 rounded-full text-sm whitespace-nowrap transition-colors border ${activeFilter === filter
                                ? 'bg-primary text-white border-primary'
                                : 'bg-white/5 text-gray-400 border-white/10 hover:bg-white/10'
                            }`}
                    >
                        {filter}
                    </button>
                ))}
            </div>

            {/* Results */}
            <div className="min-h-[200px]">
                {isSearching ? (
                    <div className="flex justify-center items-center h-40">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                    </div>
                ) : results.length > 0 ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {results.map(recipe => (
                            <div
                                key={recipe.id}
                                onClick={() => setSelectedRecipe(recipe)}
                                className="cursor-pointer transition-transform hover:scale-[1.02]"
                            >
                                <RecipeCard recipe={recipe} />
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="text-center text-gray-500 py-10">
                        <Search size={48} className="mx-auto mb-4 opacity-20" />
                        <p>Search for recipes to add to your plan</p>
                    </div>
                )}
            </div>

            {/* Modal */}
            <AnimatePresence>
                {selectedRecipe && (
                    <RecipeDetailModal
                        recipe={selectedRecipe}
                        onClose={() => setSelectedRecipe(null)}
                        onSwap={() => {
                            // In a real app, this would open a slot selector
                            console.log("Add to plan clicked");
                            setSelectedRecipe(null);
                        }}
                    />
                )}
            </AnimatePresence>
        </div>
    );
}
