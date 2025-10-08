"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { useSidebar } from "./AppLayout";
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
  const { user, logout } = useAuth();
  const { isSidebarOpen, setIsSidebarOpen } = useSidebar();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // Don't show navigation on auth pages
  if (pathname === "/login" || pathname?.startsWith("/auth/")) {
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
        className="lg:hidden fixed top-4 left-4 z-50 p-2 rounded-lg bg-gray-800 text-white hover:bg-gray-700 transition-colors"
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

      {/* Sidebar */}
      <aside
        className={`
          fixed top-0 left-0 h-full bg-gray-900 border-r border-gray-700 z-40
          transition-all duration-300 ease-in-out
          ${isSidebarOpen ? "w-64" : "w-20"}
          ${isMobileMenuOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}
        `}
      >
        <div className="flex flex-col h-full">
          {/* Logo & Toggle */}
          <div className="flex items-center justify-between p-4 border-b border-gray-700">
            <Link
              href="/"
              className={`flex items-center gap-3 text-white font-bold transition-all ${
                isSidebarOpen ? "text-lg" : "text-base justify-center"
              }`}
              onClick={() => setIsMobileMenuOpen(false)}
            >
              <Shield className="w-7 h-7 text-blue-500 flex-shrink-0" />
              {isSidebarOpen && <span>Rampart</span>}
            </Link>
            
            <button
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              className="hidden lg:block p-1.5 rounded-lg text-gray-400 hover:bg-gray-800 hover:text-white transition-colors"
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
                            ? "bg-blue-600 text-white"
                            : "text-gray-300 hover:bg-gray-800 hover:text-white"
                        }
                        ${!isSidebarOpen && "justify-center"}
                      `}
                      title={!isSidebarOpen ? item.label : undefined}
                    >
                      <Icon
                        className={`w-5 h-5 flex-shrink-0 ${
                          isActive ? "text-white" : "text-gray-400 group-hover:text-white"
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
          <div className="border-t border-gray-700 p-3 space-y-1">
            {/* User Info */}
            {user && isSidebarOpen && (
              <div className="px-3 py-2 mb-2">
                <p className="text-xs text-gray-400 truncate">{user.email}</p>
              </div>
            )}
            
            {/* Settings */}
            <Link
              href="/settings"
              onClick={() => setIsMobileMenuOpen(false)}
              className={`
                flex items-center gap-3 px-3 py-2.5 rounded-lg
                text-gray-300 hover:bg-gray-800 hover:text-white
                transition-colors group
                ${!isSidebarOpen && "justify-center"}
              `}
              title={!isSidebarOpen ? "Settings" : undefined}
            >
              <Settings className="w-5 h-5 flex-shrink-0 text-gray-400 group-hover:text-white" />
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
                text-gray-300 hover:bg-gray-800 hover:text-white
                transition-colors group
                ${!isSidebarOpen && "justify-center"}
              `}
              title={!isSidebarOpen ? "Logout" : undefined}
            >
              <LogOut className="w-5 h-5 flex-shrink-0 text-gray-400 group-hover:text-white" />
              {isSidebarOpen && <span className="text-sm font-medium">Logout</span>}
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
