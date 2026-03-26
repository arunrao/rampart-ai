import { readFile } from "fs/promises";
import path from "path";

const ALLOWED = new Set(["DEVELOPER_INTEGRATION.md", "API_REFERENCE.md"]);

/**
 * Load bundled technical docs from frontend/content/documentation.
 * (Copies of repo-root docs/ — keep in sync when publishing, or run `npm run sync-docs` from frontend.)
 */
export async function loadDocumentationMarkdown(filename: string): Promise<string> {
  if (!ALLOWED.has(filename)) {
    throw new Error(`Unsupported documentation file: ${filename}`);
  }
  const filePath = path.join(process.cwd(), "content", "documentation", filename);
  const raw = await readFile(filePath, "utf-8");
  return rewriteInternalMdLinks(raw);
}

/** Point cross-links at on-site routes instead of sibling .md files on GitHub. */
export function rewriteInternalMdLinks(markdown: string): string {
  return markdown
    .replace(/\]\(\.\/DEVELOPER_INTEGRATION\.md\)/g, "](/docs/integration)")
    .replace(/\]\(DEVELOPER_INTEGRATION\.md\)/g, "](/docs/integration)")
    .replace(/\]\(\.\/API_REFERENCE\.md\)/g, "](/docs/api-reference)")
    .replace(/\]\(API_REFERENCE\.md\)/g, "](/docs/api-reference)");
}
