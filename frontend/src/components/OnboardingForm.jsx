import React, { useState } from 'react';
import { ArrowRight, Check } from 'lucide-react';

export default function OnboardingForm({ onSubmit }) {
    const [step, setStep] = useState(1);
    const [formData, setFormData] = useState({
        age: 25,
        gender: 'male',
        weight_kg: 70,
        height_cm: 175,
        activity_level: 1.55,
        goal: 'maintenance',
        liked_ingredients: '',
        disliked_ingredients: '',
    });

    const handleChange = (e) => {
        setFormData({ ...formData, [e.target.name]: e.target.value });
    };

    const handleNext = () => setStep(step + 1);

    const handleSubmit = (e) => {
        e.preventDefault();
        // Transform string inputs to lists
        const payload = {
            ...formData,
            liked_ingredients: formData.liked_ingredients.split(',').map(s => s.trim()).filter(Boolean),
            disliked_ingredients: formData.disliked_ingredients.split(',').map(s => s.trim()).filter(Boolean),
            age: parseInt(formData.age),
            weight_kg: parseFloat(formData.weight_kg),
            height_cm: parseFloat(formData.height_cm),
            activity_level: parseFloat(formData.activity_level)
        };
        onSubmit(payload);
    };

    return (
        <div className="max-w-xl mx-auto mt-10">
            <div className="flex gap-2 mb-8 justify-center">
                {[1, 2, 3].map(i => (
                    <div key={i} className={`h-2 flex-1 rounded-full ${step >= i ? 'bg-primary' : 'bg-gray-800'}`} style={{ background: step >= i ? 'var(--primary)' : 'rgba(255,255,255,0.1)' }} />
                ))}
            </div>

            <div className="card relative overflow-hidden">
                {/* Background Glow */}
                <div className="absolute top-0 right-0 w-64 h-64 bg-primary rounded-full blur-[100px] opacity-10 -mr-32 -mt-32"></div>

                <h2 className="text-2xl mb-6 relative z-10">
                    {step === 1 && "Basic Biometrics"}
                    {step === 2 && "Health Goals"}
                    {step === 3 && "Taste Profile"}
                </h2>

                <form onSubmit={handleSubmit} className="space-y-6 relative z-10">

                    {step === 1 && (
                        <div className="space-y-4 animate-enter">
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm text-gray-400 mb-1">Age</label>
                                    <input name="age" type="number" value={formData.age} onChange={handleChange} className="input-field" />
                                </div>
                                <div>
                                    <label className="block text-sm text-gray-400 mb-1">Gender</label>
                                    <select name="gender" value={formData.gender} onChange={handleChange} className="input-field">
                                        <option value="male">Male</option>
                                        <option value="female">Female</option>
                                    </select>
                                </div>
                                <div>
                                    <label className="block text-sm text-gray-400 mb-1">Weight (kg)</label>
                                    <input name="weight_kg" type="number" value={formData.weight_kg} onChange={handleChange} className="input-field" />
                                </div>
                                <div>
                                    <label className="block text-sm text-gray-400 mb-1">Height (cm)</label>
                                    <input name="height_cm" type="number" value={formData.height_cm} onChange={handleChange} className="input-field" />
                                </div>
                            </div>
                            <button type="button" onClick={handleNext} className="btn-primary w-full flex justify-center items-center gap-2">
                                Next <ArrowRight size={18} />
                            </button>
                        </div>
                    )}

                    {step === 2 && (
                        <div className="space-y-4 animate-enter">
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">Activity Level</label>
                                <select name="activity_level" value={formData.activity_level} onChange={handleChange} className="input-field">
                                    <option value="1.2">Sedentary (Office job)</option>
                                    <option value="1.375">Light Exercise</option>
                                    <option value="1.55">Moderate Exercise</option>
                                    <option value="1.725">Heavy Exercise</option>
                                </select>
                            </div>
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">Goal</label>
                                <select name="goal" value={formData.goal} onChange={handleChange} className="input-field">
                                    <option value="weight_loss">Weight Loss</option>
                                    <option value="maintenance">Maintenance</option>
                                    <option value="muscle_gain">Muscle Gain</option>
                                </select>
                            </div>
                            <button type="button" onClick={handleNext} className="btn-primary w-full flex justify-center items-center gap-2">
                                Next <ArrowRight size={18} />
                            </button>
                        </div>
                    )}

                    {step === 3 && (
                        <div className="space-y-4 animate-enter">
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">Liked Ingredients/Cuisines (comma sep)</label>
                                <input name="liked_ingredients" placeholder="e.g. Italian, Salmon, Spicy" value={formData.liked_ingredients} onChange={handleChange} className="input-field" />
                            </div>
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">Dislikes / Allergies</label>
                                <input name="disliked_ingredients" placeholder="e.g. Mushrooms, Peanuts" value={formData.disliked_ingredients} onChange={handleChange} className="input-field" />
                            </div>
                            <button type="submit" className="btn-primary w-full flex justify-center items-center gap-2">
                                Generate Plan <Check size={18} />
                            </button>
                        </div>
                    )}
                </form>
            </div>
        </div>
    );
}
