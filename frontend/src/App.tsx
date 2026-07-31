import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import { AnimatePresence } from "framer-motion";
import Lenis from "lenis";
import { lazy, Suspense, useEffect, useRef, type ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { PageTransition } from "./components/PageTransition";

const Landing = lazy(() => import("./pages/Landing"));
const Login = lazy(() => import("./pages/Login"));
const Signup = lazy(() => import("./pages/Signup"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const MealPlanner = lazy(() => import("./pages/MealPlanner"));
const Analytics = lazy(() => import("./pages/Analytics"));
const Household = lazy(() => import("./pages/Household"));
const Preparation = lazy(() => import("./pages/Preparation"));
const Research = lazy(() => import("./pages/Research"));
const SettingsPage = lazy(() => import("./pages/Settings"));
const NotFound = lazy(() => import("./pages/NotFound"));

function RouteLoading() {
  return <main className="min-h-screen grid place-items-center p-6" aria-live="polite" aria-busy="true"><p className="text-sm text-muted-foreground">Loading page…</p></main>;
}
function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <RouteLoading />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
function ProfileRoute({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  if (user && !user.profileComplete) return <Navigate to="/settings?completeProfile=1" replace />;
  return <>{children}</>;
}
function AppRoutes() {
  const location = useLocation();
  return (
    <Suspense fallback={<RouteLoading />}>
      <AnimatePresence mode="wait">
        <Routes location={location} key={location.pathname}>
          <Route path="/" element={<PageTransition><Landing /></PageTransition>} />
          <Route path="/login" element={<PageTransition><Login /></PageTransition>} />
          <Route path="/signup" element={<PageTransition><Signup /></PageTransition>} />
          <Route path="/dashboard" element={<ProtectedRoute><PageTransition><Dashboard /></PageTransition></ProtectedRoute>} />
          <Route path="/meals" element={<ProtectedRoute><ProfileRoute><PageTransition><MealPlanner /></PageTransition></ProfileRoute></ProtectedRoute>} />
          <Route path="/analytics" element={<ProtectedRoute><ProfileRoute><PageTransition><Analytics /></PageTransition></ProfileRoute></ProtectedRoute>} />
          <Route path="/household" element={<ProtectedRoute><PageTransition><Household /></PageTransition></ProtectedRoute>} />
          <Route path="/preparation" element={<ProtectedRoute><PageTransition><Preparation /></PageTransition></ProtectedRoute>} />
          <Route path="/research" element={<ProtectedRoute><PageTransition><Research /></PageTransition></ProtectedRoute>} />
          <Route path="/settings" element={<ProtectedRoute><PageTransition><SettingsPage /></PageTransition></ProtectedRoute>} />
          <Route path="*" element={<PageTransition><NotFound /></PageTransition>} />
        </Routes>
      </AnimatePresence>
    </Suspense>
  );
}

export default function App() {
  const animationFrame = useRef<number | null>(null);
  useEffect(() => {
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (reducedMotion.matches) return;
    const lenis = new Lenis();
    const raf = (time: number) => { lenis.raf(time); animationFrame.current = requestAnimationFrame(raf); };
    animationFrame.current = requestAnimationFrame(raf);
    return () => { if (animationFrame.current !== null) cancelAnimationFrame(animationFrame.current); lenis.destroy(); };
  }, []);
  return (
    <TooltipProvider>
      <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-md focus:bg-background focus:px-4 focus:py-2 focus:shadow">Skip to main content</a>
      <Toaster /><Sonner />
      <BrowserRouter><AuthProvider><AppRoutes /></AuthProvider></BrowserRouter>
    </TooltipProvider>
  );
}
