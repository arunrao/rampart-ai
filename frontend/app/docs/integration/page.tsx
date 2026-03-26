import { loadDocumentationMarkdown } from "@/lib/docs-source";
import { MarkdownDoc } from "@/components/docs/MarkdownDoc";
import { getApiDocsUrl } from "@/lib/site";

export const metadata = {
  title: "Developer integration | Rampart docs",
  description: "Integrate Rampart security APIs into your application.",
};

export default async function IntegrationDocPage() {
  const content = await loadDocumentationMarkdown("DEVELOPER_INTEGRATION.md");
  const apiDocsUrl = getApiDocsUrl();

  return (
    <div>
      <p className="text-marketing-body mb-8 max-w-2xl leading-relaxed">
        Patterns for securing LLM inputs and outputs with Rampart. For interactive &quot;Try it out&quot; requests
        and schemas, use the{" "}
        <a href={apiDocsUrl} className="text-marketing-accent font-medium hover:underline underline-offset-4">
          OpenAPI docs
        </a>
        .
      </p>
      <MarkdownDoc content={content} />
    </div>
  );
}
