import { redirect } from "next/navigation";
import {
  DOCS_DEPLOYMENT_HREF,
  DOCS_QUICKSTART_HREF,
  DOCS_REST_API_HREF,
  DOCS_SECURITY_HREF,
} from "@/lib/site";

const TAB_REDIRECTS: Record<string, string> = {
  quickstart: DOCS_QUICKSTART_HREF,
  api: DOCS_REST_API_HREF,
  security: DOCS_SECURITY_HREF,
  deployment: DOCS_DEPLOYMENT_HREF,
};

type DocsIndexProps = {
  searchParams: Record<string, string | string[] | undefined>;
};

export default function DocsIndexPage({ searchParams }: DocsIndexProps) {
  const raw = searchParams.tab;
  const tab = typeof raw === "string" ? raw : undefined;
  if (tab && TAB_REDIRECTS[tab]) {
    redirect(TAB_REDIRECTS[tab]);
  }
  redirect(DOCS_QUICKSTART_HREF);
}
