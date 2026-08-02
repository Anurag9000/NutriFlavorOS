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
const HouseholdPlanReview = lazy(() => import("./pages/HouseholdPlanReview"));
const ApprovedPlanOccurrences = lazy(
  () => import("./pages/ApprovedPlanOccurrences"),
);
const Analytics = lazy(() => import("./pages/Analytics"));
const Household = lazy(() => import("./pages/Household"));
const Preparation = lazy(() => import("./pages/Preparation"));
const PreparationPipeline = lazy(() => import("./pages/PreparationPipeline"));
const PreparationOperations = lazy(() => import("./pages/PreparationOperations"));
const PreparationRepairReview = lazy(
  () => import("./pages/PreparationRepairReview"),
);
const PreparationRepairProposals = lazy(
  () => import("./pages/PreparationRepairProposals"),
);
const PreparationTaskExecution = lazy(
  () => import("./pages/PreparationTaskExecution"),
);
const PreparationScheduleDerivation = lazy(
  () => import("./pages/PreparationScheduleDerivation"),
);
const PreparationCalendarBuilder = lazy(
  () => import("./pages/PreparationCalendarBuilder"),
);
const PreparationOperationsCoverage = lazy(
  () => import("./pages/PreparationOperationsCoverage"),
);
const Research = lazy(() => import("./pages/Research"));
const SettingsPage = lazy(() => import("./pages/Settings"));
const NotFound = lazy(() => import("./pages/NotFound"));

function RouteLoading() {
  return (
    <main
      className="min-h-screen grid place-items-center p-6"
      aria-live="polite"
      aria-busy="true"
    >
      <p className="text-sm text-muted-foreground">Loading page…</p>
    </main>
  );
}

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <RouteLoading />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function ProfileRoute({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  if (user && !user.profileComplete) {
    return <Navigate to="/settings?completeProfile=1" replace />;
  }
  return <>{children}</>;
}

function ProtectedPage({ children }: { children: ReactNode }) {
  return (
    <ProtectedRoute>
      <PageTransition>{children}</PageTransition>
    </ProtectedRoute>
  );
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
          <Route path="/dashboard" element={<ProtectedPage><Dashboard /></ProtectedPage>} />
          <Route
            path="/meals"
            element={
              <ProtectedRoute>
                <ProfileRoute><PageTransition><MealPlanner /></PageTransition></ProfileRoute>
              </ProtectedRoute>
            }
          />
          <Route path="/household/plans" element={<ProtectedPage><HouseholdPlanReview /></ProtectedPage>} />
          <Route path="/household/plans/occurrences" element={<ProtectedPage><ApprovedPlanOccurrences /></ProtectedPage>} />
          <Route
            path="/analytics"
            element={
              <ProtectedRoute>
                <ProfileRoute><PageTransition><Analytics /></PageTransition></ProfileRoute>
              </ProtectedRoute>
            }
          />
          <Route path="/household" element={<ProtectedPage><Household /></ProtectedPage>} />
          <Route path="/preparation" element={<ProtectedPage><Preparation /></ProtectedPage>} />
          <Route path="/preparation/pipeline" element={<ProtectedPage><PreparationPipeline /></ProtectedPage>} />
          <Route path="/preparation/operations" element={<ProtectedPage><PreparationOperations /></ProtectedPage>} />
          <Route path="/preparation/operations/repair" element={<ProtectedPage><PreparationRepairReview /></ProtectedPage>} />
          <Route path="/preparation/operations/repair-proposals" element={<ProtectedPage><PreparationRepairProposals /></ProtectedPage>} />
          <Route path="/preparation/operations/execution" element={<ProtectedPage><PreparationTaskExecution /></ProtectedPage>} />
          <Route path="/preparation/operations/derivation" element={<ProtectedPage><PreparationScheduleDerivation /></ProtectedPage>} />
          <Route path="/preparation/operations/calendars/new" element={<ProtectedPage><PreparationCalendarBuilder /></ProtectedPage>} />
          <Route path="/preparation/operations/coverage" element={<ProtectedPage><PreparationOperationsCoverage /></ProtectedPage>} />
          <Route path="/research" element={<ProtectedPage><Research /></ProtectedPage>} />
          <Route path="/settings" element={<ProtectedPage><SettingsPage /></ProtectedPage>} />
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
    const raf = (time: number) => {
      lenis.raf(time);
      animationFrame.current = requestAnimationFrame(raf);
    };
    animationFrame.current = requestAnimationFrame(raf);
    return () => {
      if (animationFrame.current !== null) {
        cancelAnimationFrame(animationFrame.current);
      }
      lenis.destroy();
    };
  }, []);
  return (
    <TooltipProvider>
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-md focus:bg-background focus:px-4 focus:py-2 focus:shadow"
      >
        Skip to main content
      </a>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </BrowserRouter>
    </TooltipProvider>
  );
}
