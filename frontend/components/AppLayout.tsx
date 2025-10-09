"use client";

import { useState, createContext, useContext } from "react";
import { usePathname } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import Navigation from "./Navigation";

interface SidebarContextType {
  isSidebarOpen: boolean;
  setIsSidebarOpen: (open: boolean) => void;
}

const SidebarContext = createContext<SidebarContextType>({
  isSidebarOpen: true,
  setIsSidebarOpen: () => {},
});

export const useSidebar = () => useContext(SidebarContext);

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const pathname = usePathname();
  const { user, loading } = useAuth();
  
  // Check if we're on auth pages (login, callback)
  const isAuthPage = pathname === "/login" || pathname?.startsWith("/auth/");
  
  // Check if we're on public pages (landing, docs) without auth
  const isPublicPage = !loading && !user && (pathname === "/" || pathname === "/landing" || pathname === "/docs");

  return (
    <SidebarContext.Provider value={{ isSidebarOpen, setIsSidebarOpen }}>
      <div className="min-h-screen bg-background transition-colors duration-200">
        <Navigation />
        
        {/* Main Content Area - account for sidebar and top bar */}
        <main
          className={
            isAuthPage || isPublicPage
              ? ""
              : `transition-all duration-300 ease-in-out pt-16 ${isSidebarOpen ? "lg:ml-64" : "lg:ml-20"}`
          }
        >
          {children}
        </main>
      </div>
    </SidebarContext.Provider>
  );
}

