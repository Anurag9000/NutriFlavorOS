import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { authApi, type AuthUser } from "@/lib/api";

interface User {
  id: string;
  name: string;
  email: string;
  profileComplete: boolean;
  missingProfileFields: string[];
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (name: string, email: string, password: string) => Promise<void>;
  refreshSession: () => Promise<void>;
  logout: () => void;
}

const TOKEN_KEY = "nutriflavor_token";
const USER_KEY = "nfos_user";
const LEGACY_TOKEN_KEY = "nfos_token";
const AuthContext = createContext<AuthContextType | undefined>(undefined);

function parseApiUser(raw: AuthUser): User {
  if (!raw.id || !raw.email) {
    throw new Error("Authentication response did not contain a valid user");
  }
  return {
    id: raw.id,
    email: raw.email,
    name: raw.name.trim() ? raw.name : "User",
    profileComplete: raw.profile_complete,
    missingProfileFields: raw.missing_profile_fields.filter(
      (value): value is string => typeof value === "string",
    ),
  };
}

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
    return {
      id: parsed.id,
      email: parsed.email,
      name: parsed.name,
      profileComplete: parsed.profileComplete === true,
      missingProfileFields: Array.isArray(parsed.missingProfileFields)
        ? parsed.missingProfileFields.filter(
            (value): value is string => typeof value === "string",
          )
        : [],
    };
  } catch {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    return null;
  }
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [user, setUser] = useState<User | null>(parseStoredUser);
  const [isLoading, setIsLoading] = useState(true);

  const persistUser = useCallback((nextUser: User) => {
    localStorage.setItem(USER_KEY, JSON.stringify(nextUser));
    localStorage.removeItem(LEGACY_TOKEN_KEY);
    setUser(nextUser);
  }, []);

  const persistSession = useCallback(
    (accessToken: string, nextUser: User) => {
      localStorage.setItem(TOKEN_KEY, accessToken);
      persistUser(nextUser);
    },
    [persistUser],
  );

  const logout = useCallback(() => {
    localStorage.removeItem(USER_KEY);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(LEGACY_TOKEN_KEY);
    setUser(null);
    setIsLoading(false);
  }, []);

  const refreshSession = useCallback(async () => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      setUser(null);
      setIsLoading(false);
      return;
    }
    try {
      const response = await authApi.me();
      persistUser(parseApiUser(response));
    } catch {
      logout();
    } finally {
      setIsLoading(false);
    }
  }, [logout, persistUser]);

  const login = useCallback(
    async (email: string, password: string) => {
      const response = await authApi.login(email, password);
      persistSession(response.access_token, parseApiUser(response.user));
      setIsLoading(false);
    },
    [persistSession],
  );

  const signup = useCallback(
    async (name: string, email: string, password: string) => {
      const response = await authApi.signup({ name, email, password });
      persistSession(response.access_token, parseApiUser(response.user));
      setIsLoading(false);
    },
    [persistSession],
  );

  useEffect(() => {
    void refreshSession();
  }, [refreshSession]);

  useEffect(() => {
    const handleUnauthorized = () => logout();
    window.addEventListener("nutriflavor:unauthorized", handleUnauthorized);
    return () =>
      window.removeEventListener("nutriflavor:unauthorized", handleUnauthorized);
  }, [logout]);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: Boolean(user),
        isLoading,
        login,
        signup,
        refreshSession,
        logout,
      }}
    >
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
