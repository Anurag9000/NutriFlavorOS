import React, { createContext, useContext, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { userApi, authApi, UserProfile } from "@/lib/api";

interface User {
  id: string;
  name: string;
  email: string;
  avatar?: string;
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const MOCK_USER: User = {
  id: "usr_1",
  name: "Alex Chen",
  email: "alex@nutriflavoros.com",
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(() => {
    const stored = localStorage.getItem("nfos_user");
    return stored ? JSON.parse(stored) : null;
  });

  const login = useCallback(async (email: string, password: string) => {
    try {
      const response = await authApi.login(email, password);

      if (response && response.user) {
        const user: User = {
          id: response.user.id,
          name: response.user.name || "User",
          email: response.user.email,
          avatar: `https://api.dicebear.com/7.x/avataaars/svg?seed=${response.user.id}`
        };

        // Store session
        localStorage.setItem("nfos_token", response.access_token);
        localStorage.setItem("nfos_user", JSON.stringify(user));
        setUser(user);
      }
    } catch (error) {
      console.error("Login failed:", error);
      throw error;
    }
  }, []);

  const signup = useCallback(async (name: string, email: string, password: string) => {
    try {
      // Basic profile data for signup
      const signupData = {
        name,
        email,
        password,
        age: 30, // Default
        weight_kg: 70, // Default
        height_cm: 170, // Default
        gender: "other", // Default
        goal: "maintenance", // Default
        activity_level: 1.4 // Default
      };

      const response = await authApi.signup(signupData);

      if (response && response.user) {
        const newUser: User = {
          id: response.user.id,
          name: response.user.name,
          email: response.user.email,
          avatar: `https://api.dicebear.com/7.x/avataaars/svg?seed=${response.user.id}`
        };

        localStorage.setItem("nfos_token", response.access_token);
        localStorage.setItem("nfos_user", JSON.stringify(newUser));
        setUser(newUser);
      }
    } catch (error) {
      console.error("Signup failed:", error);
      throw error;
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("nfos_user");
    localStorage.removeItem("nfos_token");
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, isAuthenticated: !!user, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
};
