"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  Shield,
  Github,
  Code,
  BookOpen,
  ChevronDown,
  Terminal,
  FileText,
  Layers,
  Zap,
  ExternalLink,
  ArrowRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  getApiDocsUrl,
  DOCS_API_REFERENCE_HREF,
  DOCS_INTEGRATION_HREF,
  getGithubRepoUrl,
} from "@/lib/site";

type MarketingNavProps = {
  /** Optional badge next to the wordmark (e.g. version). */
  badge?: string;
};

export default function MarketingNav({ badge = "v0.2.6" }: MarketingNavProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [devOpen, setDevOpen] = useState(false);
  const devRef = useRef<HTMLDivElement | null>(null);

  const apiDocsUrl = getApiDocsUrl();
  const githubUrl = getGithubRepoUrl();

  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (!devRef.current?.contains(e.target as Node)) setDevOpen(false);
    };
    document.addEventListener("click", onDocClick);
    return () => document.removeEventListener("click", onDocClick);
  }, []);

  const devLinks = [
    {
      href: "/docs",
      label: "Documentation",
      description: "Quick start, REST API overview, deployment",
      icon: BookOpen,
      external: false,
    },
    {
      href: apiDocsUrl,
      label: "Interactive API",
      description: "OpenAPI / Swagger — try requests in the browser",
      icon: Terminal,
      external: true,
    },
    {
      href: DOCS_INTEGRATION_HREF,
      label: "Integration guide",
      description: "End-to-end patterns for securing LLM apps",
      icon: FileText,
      external: false,
    },
    {
      href: DOCS_API_REFERENCE_HREF,
      label: "API reference",
      description: "Routes, payloads, and examples on this site",
      icon: Code,
      external: false,
    },
    {
      href: githubUrl,
      label: "Source on GitHub",
      description: "Examples, issues, and contributions",
      icon: Github,
      external: true,
    },
  ];

  return (
    <nav className="marketing-nav-bar">
      <div className="container mx-auto px-4 sm:px-6 py-4 flex justify-between items-center gap-4">
        <div className="flex items-center gap-8 min-w-0">
          <Link href="/" className="flex items-center gap-2 shrink-0">
            <Shield className="h-7 w-7 text-marketing-accent" />
            <span className="text-xl sm:text-2xl font-bold text-gradient-marketing-wordmark">
              Rampart
            </span>
            {badge ? (
              <span className="hidden sm:inline text-xs font-medium text-marketing-muted ml-1">
                {badge}
              </span>
            ) : null}
          </Link>

          {/* Desktop — MACAW-style: Developers first */}
          <div className="hidden lg:flex items-center gap-1">
            <div className="relative" ref={devRef}>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setDevOpen((o) => !o);
                }}
                className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-semibold text-marketing-heading hover:bg-marketing-surface transition-colors"
                aria-expanded={devOpen}
                aria-haspopup="true"
              >
                Developers
                <ChevronDown
                  className={`h-4 w-4 text-marketing-muted transition-transform ${devOpen ? "rotate-180" : ""}`}
                />
              </button>
              {devOpen ? (
                <div
                  className="absolute left-0 top-full mt-1 w-[min(100vw-2rem,22rem)] rounded-xl border border-marketing-border bg-marketing-elevated shadow-xl py-2 z-50"
                  role="menu"
                >
                  {devLinks.map((item) => {
                    const Icon = item.icon;
                    const inner = (
                      <>
                        <Icon className="h-4 w-4 text-marketing-accent mt-0.5 shrink-0" />
                        <span className="min-w-0">
                          <span className="flex items-center gap-1 font-medium text-marketing-heading">
                            {item.label}
                            {item.external ? (
                              <ExternalLink className="h-3 w-3 opacity-60" aria-hidden />
                            ) : null}
                          </span>
                          <span className="block text-xs text-marketing-muted leading-snug mt-0.5">
                            {item.description}
                          </span>
                        </span>
                      </>
                    );
                    const className =
                      "flex gap-3 px-3 py-2.5 hover:bg-marketing-surface transition-colors text-left w-full";
                    return item.external ? (
                      <a
                        key={item.label}
                        href={item.href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={className}
                        role="menuitem"
                      >
                        {inner}
                      </a>
                    ) : (
                      <Link
                        key={item.label}
                        href={item.href}
                        className={className}
                        role="menuitem"
                        onClick={() => setDevOpen(false)}
                      >
                        {inner}
                      </Link>
                    );
                  })}
                </div>
              ) : null}
            </div>

            <Link
              href="/try"
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-marketing-body hover:text-marketing-heading hover:bg-marketing-surface transition-colors"
            >
              <Zap className="h-4 w-4" />
              Try it
            </Link>
            <Link
              href="/#platform"
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-marketing-body hover:text-marketing-heading hover:bg-marketing-surface transition-colors"
            >
              <Layers className="h-4 w-4" />
              Platform
            </Link>
          </div>
        </div>

        <div className="flex items-center gap-2 sm:gap-3 shrink-0">
          <a
            href={githubUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="hidden sm:inline-flex items-center justify-center rounded-lg p-2 text-marketing-body hover:text-marketing-heading hover:bg-marketing-surface transition-colors"
            aria-label="GitHub"
          >
            <Github className="h-5 w-5" />
          </a>
          <Link href="/login" className="hidden sm:block">
            <Button className="marketing-btn-primary shadow-lg">
              Sign in
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </Link>

          <button
            type="button"
            onClick={() => setMobileOpen((o) => !o)}
            className="lg:hidden p-2 rounded-lg text-marketing-heading hover:bg-marketing-surface"
            aria-label="Toggle menu"
            aria-expanded={mobileOpen}
          >
            {mobileOpen ? (
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            ) : (
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            )}
          </button>
        </div>
      </div>

      {mobileOpen ? (
        <div className="lg:hidden border-t border-marketing-border bg-marketing-elevated">
          <div className="container mx-auto px-4 py-4 space-y-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-marketing-muted">Developers</p>
            <div className="space-y-1">
              {devLinks.map((item) => {
                const Icon = item.icon;
                const row = (
                  <span className="flex items-center gap-2">
                    <Icon className="h-4 w-4 text-marketing-accent" />
                    {item.label}
                    {item.external ? <ExternalLink className="h-3 w-3 opacity-60" /> : null}
                  </span>
                );
                return item.external ? (
                  <a
                    key={item.label}
                    href={item.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block py-2 text-marketing-body"
                    onClick={() => setMobileOpen(false)}
                  >
                    {row}
                  </a>
                ) : (
                  <Link
                    key={item.label}
                    href={item.href}
                    className="block py-2 text-marketing-body"
                    onClick={() => setMobileOpen(false)}
                  >
                    {row}
                  </Link>
                );
              })}
            </div>
            <Link
              href="/try"
              className="flex items-center gap-2 py-2 text-marketing-body"
              onClick={() => setMobileOpen(false)}
            >
              <Zap className="h-4 w-4 text-marketing-accent" />
              Try it
            </Link>
            <Link
              href="/#platform"
              className="flex items-center gap-2 py-2 text-marketing-body"
              onClick={() => setMobileOpen(false)}
            >
              <Layers className="h-4 w-4 text-marketing-accent" />
              Platform
            </Link>
            <a
              href={githubUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 py-2 text-marketing-body sm:hidden"
              onClick={() => setMobileOpen(false)}
            >
              <Github className="h-4 w-4 text-marketing-accent" />
              GitHub
            </a>
            <Link href="/login" className="block pt-2" onClick={() => setMobileOpen(false)}>
              <Button className="w-full marketing-btn-primary">
                Sign in
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </div>
        </div>
      ) : null}
    </nav>
  );
}
