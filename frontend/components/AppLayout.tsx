"use client";

import { useState, createContext, useContext } from "react";
import { usePathname } from "next/navigation";
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
  
  // Check if we're on auth pages (login, callback)
  const isAuthPage = pathname === "/login" || pathname?.startsWith("/auth/");

  return (
    <SidebarContext.Provider value={{ isSidebarOpen, setIsSidebarOpen }}>
      <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900">
        <Navigation />
        
        {/* Main Content Area - no margin on auth pages */}
        <main
          className={
            isAuthPage
              ? ""
              : `transition-all duration-300 ease-in-out ${isSidebarOpen ? "lg:ml-64" : "lg:ml-20"}`
          }
        >
          {children}
        </main>
      </div>
    </SidebarContext.Provider>
  );
}

