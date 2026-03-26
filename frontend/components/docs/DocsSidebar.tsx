"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Rocket, Terminal, Shield, Server, BookOpen, Code } from "lucide-react";
import {
  DOCS_API_REFERENCE_HREF,
  DOCS_DEPLOYMENT_HREF,
  DOCS_INTEGRATION_HREF,
  DOCS_QUICKSTART_HREF,
  DOCS_REST_API_HREF,
  DOCS_SECURITY_HREF,
} from "@/lib/site";

const GROUPS: {
  title: string;
  items: { href: string; label: string; icon: typeof Rocket }[];
}[] = [
  {
    title: "Get started",
    items: [{ href: DOCS_QUICKSTART_HREF, label: "Quick start", icon: Rocket }],
  },
  {
    title: "Platform",
    items: [
      { href: DOCS_REST_API_HREF, label: "REST API overview", icon: Terminal },
      { href: DOCS_SECURITY_HREF, label: "Security features", icon: Shield },
      { href: DOCS_DEPLOYMENT_HREF, label: "Deployment", icon: Server },
    ],
  },
  {
    title: "Reference",
    items: [
      { href: DOCS_INTEGRATION_HREF, label: "Developer integration", icon: BookOpen },
      { href: DOCS_API_REFERENCE_HREF, label: "API reference", icon: Code },
    ],
  },
];

type DocsSidebarProps = {
  onNavigate?: () => void;
};

export default function DocsSidebar({ onNavigate }: DocsSidebarProps) {
  const pathname = usePathname();

  return (
    <nav className="sticky top-28 lg:top-24 space-y-6 p-4 lg:p-0">
      {GROUPS.map((group) => (
        <div key={group.title}>
          <p className="px-4 pb-2 text-xs font-semibold uppercase tracking-wide text-marketing-muted">
            {group.title}
          </p>
          <ul className="space-y-1">
            {group.items.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    onClick={onNavigate}
                    className={`flex items-center gap-2 w-full px-4 py-2 rounded-lg text-sm transition-colors ${
                      isActive
                        ? "bg-marketing-badge-bg text-marketing-badge-fg font-semibold"
                        : "text-marketing-body hover:bg-marketing-surface"
                    }`}
                  >
                    <Icon className="h-4 w-4 text-marketing-accent shrink-0" aria-hidden />
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}
