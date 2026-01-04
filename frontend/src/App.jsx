import React, { useState } from 'react';
import axios from 'axios';
import { ChefHat } from 'lucide-react';
import OnboardingForm from './components/OnboardingForm';
import Dashboard from './components/Dashboard';

// Set generic base URL
const API_URL = 'http://localhost:8000';

function App() {
  const [userProfile, setUserProfile] = useState(null);
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleGenerate = async (profileData) => {
    setLoading(true);
    setUserProfile(profileData);
    setError(null);
    try {
      // Small delay for effect
      await new Promise(r => setTimeout(r, 800));

      const res = await axios.post(`${API_URL}/generate_plan`, profileData);
      setPlan(res.data);
    } catch (err) {
      console.error(err);
      setError("Failed to generate plan. Ensure backend is running.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen">
      {/* Navbar */}
      <nav className="flex justify-between items-center mb-10 py-4 border-b border-white/10">
        <div className="flex items-center gap-3">
          <div className="bg-gradient-to-br from-primary to-emerald-700 p-2 rounded-lg">
            <ChefHat className="text-white" size={24} />
          </div>
          <h1 className="text-2xl font-bold tracking-tight">NutriFlavor<span className="text-primary">OS</span></h1>
        </div>
        <div className="text-sm text-gray-400">
          Hackathon Edition v0.1
        </div>
      </nav>

      {/* Content */}
      <main>
        {error && (
          <div className="p-4 bg-red-500/20 text-red-200 rounded-lg mb-6 border border-red-500/30">
            {error}
          </div>
        )}

        {!plan && !loading && (
          <div className="animate-enter">
            <div className="text-center mb-10">
              <h2 className="text-4xl font-bold mb-4">The Operating System for <span className="text-gradient">Personal Nutrition</span></h2>
              <p className="text-gray-400 max-w-2xl mx-auto">
                Optimize your health, satisfy your taste buds, and discover culinary variety with our AI-powered engine.
              </p>
            </div>
            <OnboardingForm onSubmit={handleGenerate} />
          </div>
        )}

        {loading && (
          <div className="flex flex-col items-center justify-center py-20 animate-enter">
            <div className="w-16 h-16 border-4 border-primary border-t-transparent rounded-full animate-spin mb-6"></div>
            <h3 className="text-xl font-semibold">Generating Your Flavor Genome...</h3>
            <p className="text-gray-400">Analyzing macronutrients and molecular pairings</p>
          </div>
        )}

        {plan && (
          <Dashboard planResponse={plan} userProfile={userProfile} />
        )}
      </main>
    </div>
  );
}

export default App;
