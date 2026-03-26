import { loadDocumentationMarkdown } from "@/lib/docs-source";
import { MarkdownDoc } from "@/components/docs/MarkdownDoc";
import { getApiDocsUrl } from "@/lib/site";

export const metadata = {
  title: "API reference | Rampart docs",
  description: "Rampart REST API endpoints, authentication, and responses.",
};

export default async function ApiReferenceDocPage() {
  const content = await loadDocumentationMarkdown("API_REFERENCE.md");
  const apiDocsUrl = getApiDocsUrl();

  return (
    <div>
      <p className="text-marketing-body mb-8 max-w-2xl leading-relaxed">
        Human-readable reference for routes and payloads. Executable &quot;Try it out&quot; requests live in{" "}
        <a href={apiDocsUrl} className="text-marketing-accent font-medium hover:underline underline-offset-4">
          Swagger / OpenAPI
        </a>
        .
      </p>
      <MarkdownDoc content={content} />
    </div>
  );
}
