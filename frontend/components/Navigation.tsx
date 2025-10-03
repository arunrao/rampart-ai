"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { Settings, LogOut, Shield } from "lucide-react";

export default function Navigation() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  // Don't show navigation on auth pages
  if (pathname === "/login" || pathname?.startsWith("/auth/")) {
    return null;
  }

  const navItems = [
    { href: "/", label: "Dashboard" },
    { href: "/observability", label: "Observability" },
    { href: "/security", label: "Security" },
    { href: "/policies", label: "Policies" },
    { href: "/content-filter", label: "Content Filter" },
  ];

  return (
    <nav className="bg-gray-800 border-b border-gray-700">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo and main nav */}
          <div className="flex items-center">
            <Link href="/" className="flex items-center gap-2 text-white font-bold text-xl">
              <Shield className="w-6 h-6 text-blue-500" />
              <span>Project Rampart</span>
            </Link>
            
            <div className="hidden md:block ml-10">
              <div className="flex items-baseline space-x-4">
                {navItems.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                      pathname === item.href
                        ? "bg-gray-900 text-white"
                        : "text-gray-300 hover:bg-gray-700 hover:text-white"
                    }`}
                  >
                    {item.label}
                  </Link>
                ))}
              </div>
            </div>
          </div>

          {/* User menu */}
          <div className="flex items-center gap-4">
            {user && (
              <span className="text-sm text-gray-400 hidden sm:block">
                {user.email}
              </span>
            )}
            
            <Link
              href="/settings"
              className="p-2 rounded-md text-gray-300 hover:bg-gray-700 hover:text-white transition-colors"
              title="Settings"
            >
              <Settings className="w-5 h-5" />
            </Link>
            
            <button
              onClick={logout}
              className="p-2 rounded-md text-gray-300 hover:bg-gray-700 hover:text-white transition-colors"
              title="Logout"
            >
              <LogOut className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
}
