import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { authApi } from "@/lib/api";

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

const TOKEN_KEY = "nutriflavor_token";
const USER_KEY = "nfos_user";
const LEGACY_TOKEN_KEY = "nfos_token";

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function parseStoredUser(): User | null {
  const token = localStorage.getItem(TOKEN_KEY);
  const rawUser = localStorage.getItem(USER_KEY);
  if (!token || !rawUser) return null;

  try {
    const parsed = JSON.parse(rawUser) as Partial<User>;
    if (
      typeof parsed.id !== "string" ||
      typeof parsed.email !== "string" ||
      typeof parsed.name !== "string"
    ) {
      throw new Error("Invalid stored session");
    }
    return parsed as User;
  } catch {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    return null;
  }
}

function parseApiUser(raw: Record<string, unknown>): User {
  const id = typeof raw.id === "string" ? raw.id : null;
  const email = typeof raw.email === "string" ? raw.email : null;
  const name = typeof raw.name === "string" && raw.name.trim() ? raw.name : "User";
  if (!id || !email) throw new Error("Authentication response did not contain a valid user");

  return {
    id,
    email,
    name,
    avatar: `https://api.dicebear.com/7.x/avataaars/svg?seed=${encodeURIComponent(id)}`,
  };
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(parseStoredUser);

  const persistSession = useCallback((accessToken: string, nextUser: User) => {
    localStorage.setItem(TOKEN_KEY, accessToken);
    localStorage.setItem(USER_KEY, JSON.stringify(nextUser));
    localStorage.removeItem(LEGACY_TOKEN_KEY);
    setUser(nextUser);
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const response = await authApi.login(email, password);
      persistSession(response.access_token, parseApiUser(response.user));
    },
    [persistSession],
  );

  const signup = useCallback(
    async (name: string, email: string, password: string) => {
      const response = await authApi.signup({
        name,
        email,
        password,
        age: 30,
        weight_kg: 70,
        height_cm: 170,
        gender: "other",
        goal: "maintenance",
        activity_level: 1.4,
      });
      persistSession(response.access_token, parseApiUser(response.user));
    },
    [persistSession],
  );

  const logout = useCallback(() => {
    localStorage.removeItem(USER_KEY);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(LEGACY_TOKEN_KEY);
    setUser(null);
  }, []);

  useEffect(() => {
    const handleUnauthorized = () => logout();
    window.addEventListener("nutriflavor:unauthorized", handleUnauthorized);
    return () => window.removeEventListener("nutriflavor:unauthorized", handleUnauthorized);
  }, [logout]);

  return (
    <AuthContext.Provider value={{ user, isAuthenticated: Boolean(user), login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
};
