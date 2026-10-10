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

// Refresh at most every 10 minutes, and only if the user did something in the last 15.
// Keep SESSION_REFRESH_MS well under the backend's ACCESS_TOKEN_EXPIRE_MINUTES.
const SESSION_REFRESH_MS = 10 * 60 * 1000;
const SESSION_IDLE_MS = 15 * 60 * 1000;

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

  // Sliding session: while the user is active, rotate the HttpOnly cookie before it
  // expires. POST /auth/refresh re-issues the JWT and Set-Cookie; a 401 here means the
  // session is already gone and the next API call will redirect to /login.
  useEffect(() => {
    if (!user) return;
    let lastActivity = Date.now();
    let lastRefresh = Date.now();
    const markActive = () => {
      lastActivity = Date.now();
    };
    const events: (keyof WindowEventMap)[] = ["click", "keydown", "mousemove", "scroll", "focus"];
    events.forEach((e) => window.addEventListener(e, markActive, { passive: true }));

    const timer = window.setInterval(async () => {
      const now = Date.now();
      const activeRecently = now - lastActivity < SESSION_IDLE_MS;
      const due = now - lastRefresh >= SESSION_REFRESH_MS;
      if (!activeRecently || !due || document.visibilityState !== "visible") return;
      lastRefresh = now;
      try {
        const res = await fetch(`${API_URL}/auth/refresh`, withSession({ method: "POST" }));
        if (res.status === 401) setUser(null);
      } catch {
        // transient network error; try again next tick
      }
    }, 60_000);

    return () => {
      window.clearInterval(timer);
      events.forEach((e) => window.removeEventListener(e, markActive));
    };
  }, [user]);

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
