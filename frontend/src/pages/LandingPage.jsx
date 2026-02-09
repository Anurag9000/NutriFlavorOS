import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChefHat } from 'lucide-react';
import OnboardingForm from '../components/OnboardingForm';
import { useUser } from '../contexts/UserContext';
import { useMealPlan } from '../contexts/MealPlanContext';

export default function LandingPage() {
    const navigate = useNavigate();
    const { setProfile } = useUser();
    const { createPlan } = useMealPlan();
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const handleGenerate = async (profileData) => {
        setLoading(true);
        setError(null);
        try {
            // Save profile
            setProfile(profileData);

            // Generate plan
            await createPlan(profileData);

            // Navigate to dashboard
            navigate('/app/dashboard');
        } catch (err) {
            console.error(err);
            setError('Failed to generate plan. Ensure backend is running.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen p-8">
            {/* Navbar */}
            <nav className="flex justify-between items-center mb-10 py-4 border-b border-white/10">
                <div className="flex items-center gap-3">
                    <div className="bg-gradient-to-br from-primary to-emerald-700 p-2 rounded-lg">
                        <ChefHat className="text-white" size={24} />
                    </div>
                    <h1 className="text-2xl font-bold tracking-tight">
                        NutriFlavor<span className="text-primary">OS</span>
                    </h1>
                </div>
                <div className="text-sm text-gray-400">v2.0 - Full Edition</div>
            </nav>

            {/* Content */}
            <main>
                {error && (
                    <div className="p-4 bg-red-500/20 text-red-200 rounded-lg mb-6 border border-red-500/30">
                        {error}
                    </div>
                )}

                {loading ? (
                    <div className="flex flex-col items-center justify-center py-20 animate-enter">
                        <div className="w-16 h-16 border-4 border-primary border-t-transparent rounded-full animate-spin mb-6"></div>
                        <h3 className="text-xl font-semibold">Generating Your Flavor Genome...</h3>
                        <p className="text-gray-400">Analyzing macronutrients and molecular pairings</p>
                    </div>
                ) : (
                    <div className="animate-enter">
                        <div className="text-center mb-10">
                            <h2 className="text-4xl font-bold mb-4">
                                The Operating System for <span className="text-gradient">Personal Nutrition</span>
                            </h2>
                            <p className="text-gray-400 max-w-2xl mx-auto">
                                Optimize your health, satisfy your taste buds, and discover culinary variety with our AI-powered engine.
                            </p>
                        </div>
                        <OnboardingForm onSubmit={handleGenerate} />
                    </div>
                )}
            </main>
        </div>
    );
}
