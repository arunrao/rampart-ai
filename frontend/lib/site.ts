/** Public URLs for marketing and docs — single place to adjust links. */

export function getGithubRepoUrl(): string {
  return process.env.NEXT_PUBLIC_GITHUB_URL ?? "https://github.com/arunrao/rampart-ai";
}

export function getApiDocsUrl(): string {
  const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
  return `${base.replace(/\/$/, "")}/docs`;
}

/** On-site technical documentation routes */
export const DOCS_QUICKSTART_HREF = "/docs/quickstart";
export const DOCS_REST_API_HREF = "/docs/rest-api";
export const DOCS_SECURITY_HREF = "/docs/security";
export const DOCS_DEPLOYMENT_HREF = "/docs/deployment";
export const DOCS_INTEGRATION_HREF = "/docs/integration";
export const DOCS_API_REFERENCE_HREF = "/docs/api-reference";
