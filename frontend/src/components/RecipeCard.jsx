import React from 'react';
import { ChefHat, Flame, Leaf } from 'lucide-react';

export default function RecipeCard({ recipe, metrics }) {
    // recipe has {name, description, ingredients, tags, flavor_profile}
    // metrics has {health_match, taste_match} if available, or just generic scores

    return (
        <div className="card h-full flex flex-col gap-3">
            <div className="flex justify-between items-start">
                <h3 className="text-lg font-bold text-white">{recipe.name}</h3>
                <span className="badge badge-taste">{recipe.calories} kcal</span>
            </div>

            <p className="text-sm text-gray-400 line-clamp-2">{recipe.description}</p>

            <div className="flex flex-wrap gap-2 my-2">
                {recipe.tags.map(tag => (
                    <span key={tag} className="text-xs bg-gray-800 px-2 py-1 rounded-md text-gray-300">
                        #{tag}
                    </span>
                ))}
            </div>

            <div className="bg-black/20 p-3 rounded-lg text-sm space-y-2 mt-auto">
                <div className="flex justify-between">
                    <span className="text-gray-400 flex items-center gap-1"><Leaf size={14} /> Protein</span>
                    <span>{recipe.macros.protein}g</span>
                </div>
                <div className="flex justify-between">
                    <span className="text-gray-400 flex items-center gap-1"><Flame size={14} /> Carbs</span>
                    <span>{recipe.macros.carbs}g</span>
                </div>
                <div className="flex justify-between">
                    <span className="text-gray-400 flex items-center gap-1"><ChefHat size={14} /> Fat</span>
                    <span>{recipe.macros.fat}g</span>
                </div>
            </div>

            {/* Flavor Genome Viz */}
            <div className="flex items-center gap-1 h-2 bg-gray-800 rounded-full overflow-hidden mt-1">
                {Object.entries(recipe.flavor_profile).map(([key, val], i) => (
                    <div
                        key={key}
                        className="h-full"
                        style={{
                            width: `${val * 100}%`,
                            background: i % 2 === 0 ? 'var(--secondary)' : 'var(--accent)',
                            opacity: 0.8
                        }}
                    />
                ))}
            </div>
        </div>
    );
}
