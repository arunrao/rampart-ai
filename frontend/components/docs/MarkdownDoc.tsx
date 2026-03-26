import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

const components: Components = {
  h1: ({ children }) => (
    <h1 className="text-3xl sm:text-4xl font-bold text-marketing-heading mt-10 mb-4 scroll-mt-28 first:mt-0">
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-2xl sm:text-3xl font-bold text-marketing-heading mt-10 mb-3 scroll-mt-28 border-b border-marketing-border pb-2">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-xl font-semibold text-marketing-heading mt-8 mb-2 scroll-mt-28">{children}</h3>
  ),
  h4: ({ children }) => (
    <h4 className="text-lg font-semibold text-marketing-heading mt-6 mb-2">{children}</h4>
  ),
  p: ({ children }) => (
    <p className="text-marketing-body leading-relaxed my-4">{children}</p>
  ),
  ul: ({ children }) => <ul className="my-4 list-disc pl-6 space-y-2 text-marketing-body">{children}</ul>,
  ol: ({ children }) => <ol className="my-4 list-decimal pl-6 space-y-2 text-marketing-body">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  blockquote: ({ children }) => (
    <blockquote className="border-l-4 border-marketing-accent pl-4 my-4 italic text-marketing-muted">
      {children}
    </blockquote>
  ),
  a: ({ href, children }) => (
    <a
      href={href}
      className="text-marketing-accent font-medium hover:underline underline-offset-4"
      target={href?.startsWith("http") ? "_blank" : undefined}
      rel={href?.startsWith("http") ? "noopener noreferrer" : undefined}
    >
      {children}
    </a>
  ),
  hr: () => <hr className="my-10 border-marketing-border" />,
  strong: ({ children }) => <strong className="font-semibold text-marketing-heading">{children}</strong>,
  table: ({ children }) => (
    <div className="my-6 overflow-x-auto rounded-lg border border-marketing-border">
      <table className="min-w-full divide-y divide-marketing-border text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-marketing-surface">{children}</thead>,
  th: ({ children }) => (
    <th className="px-3 py-2 text-left font-semibold text-marketing-heading">{children}</th>
  ),
  td: ({ children }) => (
    <td className="px-3 py-2 border-t border-marketing-border text-marketing-body">{children}</td>
  ),
  pre: ({ children }) => (
    <pre className="my-4 overflow-x-auto rounded-lg border border-marketing-border bg-marketing-code-bg p-4 text-sm text-marketing-code-fg">
      {children}
    </pre>
  ),
  code: ({ className, children, ...props }) => {
    const isBlock = Boolean(className?.startsWith("language-"));
    if (isBlock) {
      return (
        <code className={`font-mono text-[0.9em] ${className ?? ""}`} {...props}>
          {children}
        </code>
      );
    }
    return (
      <code className="rounded bg-marketing-surface px-1.5 py-0.5 font-mono text-[0.9em] text-marketing-code-fg">
        {children}
      </code>
    );
  },
};

type MarkdownDocProps = {
  content: string;
};

export function MarkdownDoc({ content }: MarkdownDocProps) {
  return (
    <article className="max-w-4xl pb-16">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </article>
  );
}
