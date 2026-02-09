import React, { useState } from 'react';
import { Star, ThumbsUp, ThumbsDown, MessageSquare } from 'lucide-react';
import { motion } from 'framer-motion';

export default function MealRatingInterface({ recipe, onSubmit, onClose }) {
    const [rating, setRating] = useState(0);
    const [hoverRating, setHoverRating] = useState(0);
    const [tags, setTags] = useState([]);
    const [feedback, setFeedback] = useState('');

    const tasteTags = [
        "Too Salty", "Too Sweet", "Too Spicy", "Bland",
        "Perfect Seasoning", "Great Texture", "Filling", "Light"
    ];

    const toggleTag = (tag) => {
        if (tags.includes(tag)) {
            setTags(tags.filter(t => t !== tag));
        } else {
            setTags([...tags, tag]);
        }
    };

    const handleSubmit = () => {
        onSubmit({
            recipeId: recipe.id || recipe.name,
            rating,
            tags,
            feedback,
            timestamp: new Date().toISOString()
        });
    };

    return (
        <div className="space-y-6">
            <div className="text-center">
                <h3 className="text-xl font-semibold mb-2">How was your meal?</h3>
                <p className="text-gray-400 text-sm">Help FoodScope learn your taste preferences</p>
            </div>

            {/* Star Rating */}
            <div className="flex justify-center gap-2">
                {[1, 2, 3, 4, 5].map((star) => (
                    <button
                        key={star}
                        onMouseEnter={() => setHoverRating(star)}
                        onMouseLeave={() => setHoverRating(0)}
                        onClick={() => setRating(star)}
                        className="transition-transform hover:scale-110 active:scale-95 p-1"
                    >
                        <Star
                            size={32}
                            className={`${star <= (hoverRating || rating)
                                    ? 'fill-amber-400 text-amber-400'
                                    : 'text-gray-600'
                                } transition-colors`}
                        />
                    </button>
                ))}
            </div>

            <div className="text-center text-sm font-medium text-amber-400 h-5">
                {rating === 1 && "Not for me"}
                {rating === 2 && "Could be better"}
                {rating === 3 && "It was okay"}
                {rating === 4 && "Really good!"}
                {rating === 5 && "Loved it!"}
            </div>

            {/* Taste Tags */}
            <div>
                <label className="text-sm text-gray-400 block mb-3">What stood out?</label>
                <div className="flex flex-wrap gap-2">
                    {tasteTags.map(tag => (
                        <button
                            key={tag}
                            onClick={() => toggleTag(tag)}
                            className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-all ${tags.includes(tag)
                                    ? 'bg-primary text-white border-primary'
                                    : 'bg-white/5 text-gray-400 border-white/10 hover:bg-white/10'
                                }`}
                        >
                            {tag}
                        </button>
                    ))}
                </div>
            </div>

            {/* Written Feedback */}
            <div>
                <label className="text-sm text-gray-400 block mb-2">Additional Comments (Optional)</label>
                <div className="relative">
                    <MessageSquare className="absolute left-3 top-3 text-gray-600" size={16} />
                    <textarea
                        value={feedback}
                        onChange={(e) => setFeedback(e.target.value)}
                        className="w-full bg-black/40 border border-white/10 rounded-xl py-2 pl-10 pr-4 text-sm focus:outline-none focus:border-primary min-h-[80px] resize-none"
                        placeholder="Any specific ingredients you liked or disliked?"
                    />
                </div>
            </div>

            {/* Actions */}
            <div className="flex gap-3 pt-2">
                <button
                    onClick={onClose}
                    className="flex-1 py-3 rounded-xl border border-white/10 hover:bg-white/5 transition-colors font-medium text-sm"
                >
                    Skip
                </button>
                <button
                    onClick={handleSubmit}
                    disabled={rating === 0}
                    className={`flex-1 py-3 rounded-xl font-medium text-sm transition-all shadow-lg ${rating > 0
                            ? 'bg-gradient-to-r from-primary to-emerald-600 text-white shadow-emerald-900/20 hover:shadow-emerald-900/40'
                            : 'bg-gray-800 text-gray-500 cursor-not-allowed'
                        }`}
                >
                    Submit Feedback
                </button>
            </div>
        </div>
    );
}
