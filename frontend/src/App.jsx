import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { UserProvider } from './contexts/UserContext';
import { MealPlanProvider } from './contexts/MealPlanContext';
import { GamificationProvider } from './contexts/GamificationContext';
import { GroceryProvider } from './contexts/GroceryContext';
import { Toaster } from 'react-hot-toast';

// Pages
import LandingPage from './pages/LandingPage';
import DashboardPage from './pages/DashboardPage';
import MealPlanPage from './pages/MealPlanPage';
import GroceryPage from './pages/GroceryPage';
import AnalyticsPage from './pages/AnalyticsPage';
import GamificationPage from './pages/GamificationPage';
import SustainabilityPage from './pages/SustainabilityPage';
import ProfilePage from './pages/ProfilePage';

// Layout
import Layout from './components/layout/Layout';

function App() {
  return (
    <Router>
      <UserProvider>
        <MealPlanProvider>
          <GamificationProvider>
            <GroceryProvider>
              <Toaster position="top-right" />
              <Routes>
                {/* Landing/Onboarding */}
                <Route path="/" element={<LandingPage />} />

                {/* Main App with Layout */}
                <Route path="/app" element={<Layout />}>
                  <Route index element={<Navigate to="/app/dashboard" replace />} />
                  <Route path="dashboard" element={<DashboardPage />} />
                  <Route path="meal-plan" element={<MealPlanPage />} />
                  <Route path="grocery" element={<GroceryPage />} />
                  <Route path="analytics" element={<AnalyticsPage />} />
                  <Route path="gamification" element={<GamificationPage />} />
                  <Route path="sustainability" element={<SustainabilityPage />} />
                  <Route path="profile" element={<ProfilePage />} />
                </Route>
              </Routes>
            </GroceryProvider>
          </GamificationProvider>
        </MealPlanProvider>
      </UserProvider>
    </Router>
  );
}

export default App;
