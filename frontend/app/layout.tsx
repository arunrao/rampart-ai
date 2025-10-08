import type { Metadata } from "next";
import { Inter } from "next/font/google";
import Script from "next/script";
import "./globals.css";
import { Providers } from "./providers";
import AppLayout from "@/components/AppLayout";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Project Rampart - AI Security & Observability",
  description: "Comprehensive security and observability platform for AI applications",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <Script id="theme-init" strategy="beforeInteractive">
          {`(function(){
            try {
              var stored = localStorage.getItem('theme');
              var preferSystem = !stored || stored === 'system';
              var isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
              var useDark = stored === 'dark' || (preferSystem && isDark);
              var useLight = stored === 'light' || (preferSystem && !isDark);
              var root = document.documentElement;
              root.classList.remove('light','dark');
              if (useDark) root.classList.add('dark');
              else if (useLight) root.classList.add('light');
            } catch (e) {}
          })();`}
        </Script>
      </head>
      <body className={inter.className}>
        <Providers>
          <AppLayout>
            {children}
          </AppLayout>
        </Providers>
      </body>
    </html>
  );
}
