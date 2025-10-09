"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { useSidebar } from "./AppLayout";
import ThemeToggle from "./ThemeToggle";
import {
  Settings,
  LogOut,
  Shield,
  LayoutDashboard,
  Eye,
  ShieldAlert,
  FileText,
  Filter,
  Key,
  BookOpen,
  FlaskConical,
  Menu,
  X,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

export default function Navigation() {
  const pathname = usePathname();
  const { user, logout, loading } = useAuth();
  const { isSidebarOpen, setIsSidebarOpen } = useSidebar();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // Don't show navigation on auth pages
  if (pathname === "/login" || pathname?.startsWith("/auth/")) {
    return null;
  }

  // Don't show navigation on landing page or docs for non-authenticated users
  if (!loading && !user && (pathname === "/" || pathname === "/landing" || pathname === "/docs")) {
    return null;
  }

  const navItems = [
    { href: "/", label: "Dashboard", icon: LayoutDashboard },
    { href: "/observability", label: "Observability", icon: Eye },
    { href: "/security", label: "Security", icon: ShieldAlert },
    { href: "/policies", label: "Policies", icon: FileText },
    { href: "/content-filter", label: "Content Filter", icon: Filter },
    { href: "/api-keys", label: "API Keys", icon: Key },
    { href: "/docs", label: "API Docs", icon: BookOpen },
    { href: "/testing", label: "Testing", icon: FlaskConical },
  ];

  return (
    <>
      {/* Mobile Menu Button */}
      <button
        onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
        className="lg:hidden fixed top-4 left-4 z-50 p-2 rounded-lg bg-card border border-border shadow-lg hover:bg-accent transition-colors"
        aria-label="Toggle menu"
      >
        {isMobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
      </button>

      {/* Overlay for mobile */}
      {isMobileMenuOpen && (
        <div
          className="lg:hidden fixed inset-0 bg-black/50 z-30"
          onClick={() => setIsMobileMenuOpen(false)}
        />
      )}

      {/* Top Bar (Desktop Only) */}
      <div 
        className={`
          hidden lg:block fixed top-0 right-0 h-16 bg-card border-b border-border z-30 
          transition-all duration-300 ease-in-out
          ${isSidebarOpen ? "left-64" : "left-20"}
        `}
      >
        <div className="flex items-center justify-end h-full px-6 gap-4">
          <ThemeToggle />
        </div>
      </div>

      {/* Sidebar */}
      <aside
        className={`
          fixed top-0 left-0 h-full bg-card dark:bg-gray-900 border-r border-border z-40
          transition-all duration-300 ease-in-out
          ${isSidebarOpen ? "w-64" : "w-20"}
          ${isMobileMenuOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}
        `}
      >
        <div className="flex flex-col h-full">
          {/* Logo & Toggle */}
          <div className="flex items-center justify-between p-4 border-b border-border">
            <Link
              href="/"
              className={`flex items-center gap-3 font-bold transition-all ${
                isSidebarOpen ? "text-lg" : "text-base justify-center"
              }`}
              onClick={() => setIsMobileMenuOpen(false)}
            >
              <Shield className="w-7 h-7 text-primary flex-shrink-0" />
              {isSidebarOpen && <span>Rampart</span>}
            </Link>
            
            <button
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              className="hidden lg:block p-1.5 rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
              aria-label="Toggle sidebar"
            >
              {isSidebarOpen ? (
                <ChevronLeft className="w-5 h-5" />
              ) : (
                <ChevronRight className="w-5 h-5" />
              )}
            </button>
          </div>

          {/* Navigation Items */}
          <nav className="flex-1 overflow-y-auto py-4">
            <ul className="space-y-1 px-3">
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = pathname === item.href;
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      onClick={() => setIsMobileMenuOpen(false)}
                      className={`
                        flex items-center gap-3 px-3 py-2.5 rounded-lg
                        transition-all duration-200 group
                        ${
                          isActive
                            ? "bg-primary text-primary-foreground"
                            : "text-foreground/70 hover:bg-accent hover:text-foreground"
                        }
                        ${!isSidebarOpen && "justify-center"}
                      `}
                      title={!isSidebarOpen ? item.label : undefined}
                    >
                      <Icon
                        className={`w-5 h-5 flex-shrink-0 ${
                          isActive ? "" : "text-muted-foreground group-hover:text-foreground"
                        }`}
                      />
                      {isSidebarOpen && (
                        <span className="text-sm font-medium">{item.label}</span>
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>

          {/* User Section */}
          <div className="border-t border-border p-3 space-y-1">
            {/* Theme Toggle (Mobile Only) */}
            <div className="lg:hidden mb-3 px-3">
              <ThemeToggle />
            </div>

            {/* User Info */}
            {user && isSidebarOpen && (
              <div className="px-3 py-2 mb-2">
                <p className="text-xs text-muted-foreground truncate">{user.email}</p>
              </div>
            )}
            
            {/* Settings */}
            <Link
              href="/settings"
              onClick={() => setIsMobileMenuOpen(false)}
              className={`
                flex items-center gap-3 px-3 py-2.5 rounded-lg
                text-foreground/70 hover:bg-accent hover:text-foreground
                transition-colors group
                ${!isSidebarOpen && "justify-center"}
              `}
              title={!isSidebarOpen ? "Settings" : undefined}
            >
              <Settings className="w-5 h-5 flex-shrink-0 text-muted-foreground group-hover:text-foreground" />
              {isSidebarOpen && <span className="text-sm font-medium">Settings</span>}
            </Link>

            {/* Logout */}
            <button
              onClick={() => {
                logout();
                setIsMobileMenuOpen(false);
              }}
              className={`
                w-full flex items-center gap-3 px-3 py-2.5 rounded-lg
                text-foreground/70 hover:bg-accent hover:text-foreground
                transition-colors group
                ${!isSidebarOpen && "justify-center"}
              `}
              title={!isSidebarOpen ? "Logout" : undefined}
            >
              <LogOut className="w-5 h-5 flex-shrink-0 text-muted-foreground group-hover:text-foreground" />
              {isSidebarOpen && <span className="text-sm font-medium">Logout</span>}
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
