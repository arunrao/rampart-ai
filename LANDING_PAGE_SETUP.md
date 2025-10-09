# Landing Page Setup Guide

## Overview

A beautiful, professional 1-page informational website has been created as the homepage for Project Rampart. The landing page automatically shows for non-authenticated visitors and the dashboard shows for logged-in users.

## What Was Created

### 1. Landing Page (`/frontend/app/landing/page.tsx`)
A modern, conversion-focused landing page featuring:

**Navigation Bar:**
- Logo and version badge
- Links to GitHub, Docs, and API documentation
- "Sign In" button (top-right)

**Hero Section:**
- Clear value proposition
- Live code examples (Python, cURL, LangChain) with tabbed interface
- Call-to-action buttons (Get Started, View API Docs)
- Trust badges (Open Source, Self-Hosted, No Vendor Lock-in)

**Stats Section:**
- 95% Detection Accuracy
- <50ms Average Latency
- 50+ Attack Patterns
- 100% Open Source

**Features Section:**
Six feature cards highlighting:
- Prompt Injection Detection (DeBERTa ML + Regex)
- Data Exfiltration Monitoring
- PII Detection (GLiNER ML)
- Observability & Tracing
- Policy Management
- Developer-First Integration

**Use Cases Section:**
- Customer Support Bots
- RAG Applications
- Code Generation Tools

**Integration Example:**
Step-by-step guide showing how to integrate Rampart in minutes

**Call-to-Action:**
Prominent CTA with gradient background and dual buttons

**Footer:**
- Product links
- Resources
- Company information
- Social media links

### 2. Documentation Page (`/frontend/app/docs/page.tsx`)
Comprehensive developer documentation with sidebar navigation:

**Sections:**
1. **Quick Start** - Get started in 5 minutes
2. **Python SDK** - Complete SDK reference with code examples
3. **REST API** - HTTP API endpoints with cURL examples
4. **LangChain Integration** - Framework integration guide
5. **Security Features** - Detailed feature breakdown
6. **Deployment** - Docker and cloud deployment guides

**Features:**
- Tabbed navigation
- Syntax-highlighted code blocks
- Interactive examples
- Link to Swagger docs
- Progress indicators

### 3. Smart Homepage (`/frontend/app/page.tsx`)
Updated to show:
- Landing page for non-authenticated users
- Dashboard for authenticated users
- Loading state during auth check

## Configuration

### Environment Variables

Add to `/frontend/.env.local`:

```bash
# GitHub Repository URL
NEXT_PUBLIC_GITHUB_URL=https://github.com/yourusername/project-rampart

# API Base URL (already exists)
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

### Update GitHub URL

Replace `yourusername` with your actual GitHub username in:
- `.env.local` (recommended)
- Or directly in the landing page footer links

## Design Inspiration

The landing page design is inspired by:
- **Stripe** - Clean, minimal design with inline code examples
- **Twilio** - Developer-friendly documentation approach
- **Modern SaaS platforms** - Conversion-focused layout with trust signals

## Key Features

### 🎨 Design
- Beautiful gradient backgrounds
- Dark mode support (via existing theme system)
- Responsive design (mobile, tablet, desktop)
- Smooth transitions and hover effects
- Professional color scheme (blue/indigo gradient)

### 💻 Code Examples
- Syntax-highlighted code blocks
- Multiple language examples (Python, cURL, LangChain)
- Real, working examples from your codebase
- Copy-paste ready snippets

### 🔗 Navigation
- Sticky header with navigation
- Links to GitHub (configurable)
- Links to API docs (Swagger at `/docs`)
- Links to developer documentation
- Sign-in button (top-right)

### 📱 Responsive
- Mobile-first design
- Hamburger menu (can be added if needed)
- Touch-friendly buttons
- Readable on all screen sizes

## Testing

### Local Development

1. Start the backend:
```bash
cd backend
source venv/bin/activate
uvicorn api.main:app --reload
```

2. Start the frontend:
```bash
cd frontend
npm install
npm run dev
```

3. Visit:
- Landing page: http://localhost:3000
- Documentation: http://localhost:3000/docs
- API docs: http://localhost:8000/docs

### Test Scenarios

1. **Non-authenticated user:**
   - Should see landing page
   - Can click "Sign In" to go to login
   - Can navigate to docs

2. **Authenticated user:**
   - Should see dashboard on homepage
   - Can access all protected routes

3. **Navigation:**
   - All links work correctly
   - GitHub link opens in new tab
   - API docs link opens backend Swagger docs

## Customization

### Update Content

**Hero Section:**
Edit the main headline and description in `/frontend/app/landing/page.tsx`:
```typescript
<h1 className="text-5xl lg:text-6xl font-bold...">
  Your New Headline
</h1>
```

**Features:**
Modify the feature cards array to add/remove/update features

**Code Examples:**
Update the `codeExamples` object with your own examples

### Update Colors

The design uses Tailwind CSS with a blue/indigo gradient theme. To change:
```typescript
// Blue to Purple gradient
className="bg-gradient-to-r from-purple-600 to-pink-600"
```

### Update Logo

Replace the `Shield` icon with your own logo:
```typescript
import YourLogo from "@/components/YourLogo";
<YourLogo className="h-8 w-8" />
```

## SEO Optimization (Future)

To add SEO metadata, update the page metadata:

```typescript
// Add to page.tsx
export const metadata = {
  title: "Rampart - AI Security for Developers",
  description: "Production-ready security gateway for LLM applications...",
  openGraph: {
    title: "Rampart",
    description: "...",
    images: ["/og-image.png"],
  },
};
```

## Analytics (Future)

Add Google Analytics or Plausible:

```typescript
// Add to layout.tsx
<Script src="https://www.googletagmanager.com/gtag/js?id=GA_MEASUREMENT_ID" />
```

## Screenshots

The landing page includes:
- Hero with code examples (interactive tabs)
- Feature grid (6 cards with icons)
- Stats bar (4 key metrics)
- Use cases (3 example applications)
- Integration guide (3-step process)
- CTA section (gradient background)
- Footer (4-column layout)

## Next Steps

1. **Update GitHub URL** in `.env.local`
2. **Customize content** to match your branding
3. **Add real screenshots** (optional)
4. **Test on mobile devices**
5. **Deploy to production**

## File Structure

```
frontend/
├── app/
│   ├── landing/
│   │   └── page.tsx          # Landing page component
│   ├── docs/
│   │   └── page.tsx          # Documentation page
│   ├── page.tsx              # Smart homepage router
│   └── ...
└── .env.local                # Environment variables
```

## Links Reference

| Component | URL | Description |
|-----------|-----|-------------|
| Landing Page | `/` | Public homepage (non-auth) |
| Dashboard | `/` | Dashboard (authenticated) |
| Documentation | `/docs` | Developer docs |
| API Reference | `http://localhost:8000/docs` | Swagger/OpenAPI docs |
| Login | `/login` | Sign in page |
| GitHub | Configurable | Repository link |

## Support

For issues or questions:
1. Check the main README.md
2. Review the .cursorrules file
3. Check DEVELOPER_INTEGRATION.md

## License

Same as Project Rampart - MIT License

