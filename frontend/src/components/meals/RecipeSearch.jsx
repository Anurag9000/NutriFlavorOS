import React, { useState } from 'react';
import { Search, Filter, Clock, Flame, ChefHat, X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import RecipeCard from '../RecipeCard';
import RecipeDetailModal from '../meals/RecipeDetailModal';
import { useRecipeSearch } from '../../hooks/useApi';

export default function RecipeSearch() {
    const [query, setQuery] = useState('');
    const [activeFilter, setActiveFilter] = useState('All');
    const [debouncedQuery, setDebouncedQuery] = useState('');
    const [selectedRecipe, setSelectedRecipe] = useState(null);

    // Debounce search
    React.useEffect(() => {
        const timer = setTimeout(() => {
            setDebouncedQuery(query);
        }, 500);
        return () => clearTimeout(timer);
    }, [query]);

    const { data: results, isLoading: isSearching } = useRecipeSearch(debouncedQuery, activeFilter !== 'All' ? activeFilter : undefined);

    const handleSearch = (e) => {
        e.preventDefault();
        // Trigger generic search immediately if needed, but debounce handles it
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
                ) : results?.length > 0 ? (
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
