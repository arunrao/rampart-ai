import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        /* Public marketing pages — tokens defined in app/globals.css */
        marketing: {
          accent: "hsl(var(--marketing-accent) / <alpha-value>)",
          "accent-fg": "hsl(var(--marketing-accent-fg) / <alpha-value>)",
          muted: "hsl(var(--marketing-muted) / <alpha-value>)",
          subtle: "hsl(var(--marketing-subtle) / <alpha-value>)",
          heading: "hsl(var(--marketing-heading) / <alpha-value>)",
          body: "hsl(var(--marketing-body) / <alpha-value>)",
          surface: "hsl(var(--marketing-surface) / <alpha-value>)",
          elevated: "hsl(var(--marketing-elevated) / <alpha-value>)",
          border: "hsl(var(--marketing-border) / <alpha-value>)",
          "badge-bg": "hsl(var(--marketing-badge-bg) / <alpha-value>)",
          "badge-fg": "hsl(var(--marketing-badge-fg) / <alpha-value>)",
          "code-bg": "hsl(var(--marketing-code-bg) / <alpha-value>)",
          "code-fg": "hsl(var(--marketing-code-fg) / <alpha-value>)",
          "footer-fg": "hsl(var(--marketing-footer-fg) / <alpha-value>)",
          "footer-muted": "hsl(var(--marketing-footer-muted) / <alpha-value>)",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
    },
  },
  plugins: [],
};
export default config;
