"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { API_URL, logoutSession, withSession } from "@/utils/auth";

interface User {
  id: string;
  email: string;
  is_super_admin?: boolean;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  /** Re-read the session from the backend (used after the OAuth callback). */
  refreshUser: () => Promise<User | null>;
  logout: () => Promise<void>;
  isAuthenticated: boolean;
  isSuperAdmin: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

async function fetchCurrentUser(): Promise<User | null> {
  // The session is an HttpOnly cookie; the browser attaches it, JS never sees it.
  const res = await fetch(`${API_URL}/auth/me`, withSession());
  if (!res.ok) return null;
  return (await res.json()) as User;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const refreshUser = useCallback(async () => {
    try {
      const u = await fetchCurrentUser();
      setUser(u);
      return u;
    } catch {
      setUser(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Check if user is logged in on mount
    void refreshUser();
  }, [refreshUser]);

  const logout = useCallback(async () => {
    await logoutSession();
    setUser(null);
    router.push("/");
  }, [router]);

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        refreshUser,
        logout,
        isAuthenticated: !!user,
        isSuperAdmin: !!user?.is_super_admin,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
