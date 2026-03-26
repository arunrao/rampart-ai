"use client";

import { useState } from "react";
import Link from "next/link";
import { Shield, Terminal, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getApiDocsUrl, getGithubRepoUrl } from "@/lib/site";
import DocsSidebar from "./DocsSidebar";

export default function DocsChrome({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const apiDocsUrl = getApiDocsUrl();
  const githubUrl = getGithubRepoUrl();

  const closeSidebar = () => setSidebarOpen(false);

  return (
    <>
      <div className="border-b border-marketing-border bg-marketing-elevated/90">
        <div className="container mx-auto px-4 sm:px-6 py-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3 min-w-0">
            <button
              type="button"
              onClick={() => setSidebarOpen((o) => !o)}
              className="lg:hidden p-2 rounded-lg hover:bg-marketing-surface text-marketing-heading"
              aria-label="Open documentation menu"
              aria-expanded={sidebarOpen}
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            <div className="flex items-center gap-2 min-w-0">
              <Shield className="h-6 w-6 text-marketing-accent shrink-0" />
              <div className="min-w-0">
                <p className="text-xs font-semibold uppercase tracking-wide text-marketing-muted">Documentation</p>
                <h1 className="text-lg sm:text-xl font-bold truncate text-marketing-heading">Rampart</h1>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Link href={apiDocsUrl} target="_blank" rel="noopener noreferrer">
              <Button variant="outline" size="sm" className="border-marketing-border">
                <Terminal className="mr-2 h-4 w-4" />
                OpenAPI / Swagger
                <ExternalLink className="ml-2 h-3 w-3 opacity-70" />
              </Button>
            </Link>
            <Link href="/try">
              <Button variant="outline" size="sm" className="border-marketing-border">
                Playground
              </Button>
            </Link>
            <Link href={githubUrl} target="_blank" rel="noopener noreferrer">
              <Button size="sm" className="marketing-btn-primary">
                GitHub
              </Button>
            </Link>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-4 sm:px-6 py-8 lg:py-12 flex gap-8">
        <aside
          className={`fixed lg:static inset-y-0 left-0 z-50 w-72 max-w-[85vw] flex-shrink-0 bg-marketing-elevated lg:bg-transparent border-r border-marketing-border lg:border-0 transform transition-transform duration-300 overflow-y-auto lg:overflow-visible ${
            sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
          }`}
        >
          <DocsSidebar onNavigate={closeSidebar} />
        </aside>

        {sidebarOpen ? (
          <button
            type="button"
            className="fixed inset-0 bg-black/50 z-40 lg:hidden border-0 cursor-default"
            aria-label="Close menu"
            onClick={closeSidebar}
          />
        ) : null}

        <main className="flex-1 min-w-0 max-w-4xl">{children}</main>
      </div>
    </>
  );
}
