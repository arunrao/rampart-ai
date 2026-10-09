"use client";

import { Suspense, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";

// Force dynamic rendering for this page
export const dynamic = 'force-dynamic';

function AuthCallbackContent() {
  const router = useRouter();
  const { refreshUser } = useAuth();
  const handled = useRef(false);

  useEffect(() => {
    // Run once (React strict mode double-invokes effects in dev)
    if (handled.current) return;
    handled.current = true;

    // The backend already set the HttpOnly session cookie before redirecting here, so
    // nothing sensitive is in the URL. Just confirm the session and move on.
    refreshUser()
      .then((user) => {
        if (!user) throw new Error("No session");
        router.push("/");
      })
      .catch((error) => {
        console.error("Auth callback error:", error);
        router.push("/login?error=auth_failed");
      });
  }, [refreshUser, router]);

  return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center">
      <div className="text-white">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white mx-auto mb-4"></div>
        <p>Completing sign in...</p>
      </div>
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-white">Loading...</div>
      </div>
    }>
      <AuthCallbackContent />
    </Suspense>
  );
}
