import MarketingNav from "@/components/marketing/MarketingNav";
import DocsChrome from "@/components/docs/DocsChrome";

export default function DocsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-marketing-page text-marketing-heading">
      <MarketingNav />
      <DocsChrome>{children}</DocsChrome>
    </div>
  );
}
