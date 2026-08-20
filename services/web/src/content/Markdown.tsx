import type { ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkDirective from "remark-directive";
import remarkGfm from "remark-gfm";

import { CodeBlock } from "./CodeBlock";
import { remarkDirectiveToElements } from "./directives";
import { Mermaid } from "./Mermaid";
import { Predict } from "./Predict";
import { TryIt } from "./TryIt";

function textOf(node: ReactNode): string {
  if (node === null || node === undefined || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(textOf).join("");
  // biome-ignore lint/suspicious/noExplicitAny: walking arbitrary React children
  const props = (node as any)?.props;
  return props ? textOf(props.children) : "";
}

/** Directive presentation. Each entry mirrors one name in ALLOWED_DIRECTIVES. */
function Directive({
  name,
  attrs,
  topicSlug,
  children,
}: {
  name: string;
  // biome-ignore lint/suspicious/noExplicitAny: attribute bag from remark-directive
  attrs: Record<string, any>;
  topicSlug?: string;
  children: ReactNode;
}) {
  switch (name) {
    case "objective":
      return (
        <div className="my-6 border-l-2 border-[var(--color-signal)] bg-[var(--color-surface)] py-2 pl-4">
          <span className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.14em] text-[var(--color-signal)]">
            Objective {attrs.id ? String(attrs.id) : ""}
          </span>
          <div className="text-sm text-[var(--color-ink-soft)]">{children}</div>
        </div>
      );

    case "terminal":
      return (
        <figure className="my-6">
          {attrs.title ? (
            <figcaption className="mb-1 font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.14em] text-[var(--color-muted)]">
              {String(attrs.title)}
            </figcaption>
          ) : null}
          <div className="rounded-sm border border-[var(--color-rule)] bg-[var(--color-surface-2)] p-4 font-[family-name:var(--font-mono)] text-[0.82rem] leading-relaxed [&_p]:m-0 [&_p]:whitespace-pre-wrap">
            {children}
          </div>
        </figure>
      );

    case "warning":
      return (
        <aside className="my-6 rounded-sm border border-[var(--color-accent)] bg-[var(--color-surface)] p-4">
          <span className="mb-1 block font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.14em] text-[var(--color-accent)]">
            {attrs.scope === "production" ? "In production" : "Careful"}
          </span>
          <div className="text-sm [&>p:last-child]:mb-0">{children}</div>
        </aside>
      );

    case "note":
    case "aside":
      return (
        <aside className="my-6 rounded-sm border border-[var(--color-rule)] bg-[var(--color-surface)] p-4 text-sm text-[var(--color-ink-soft)] [&>p:last-child]:mb-0">
          {children}
        </aside>
      );

    case "callback":
      return (
        <aside className="my-6 border-l-2 border-[var(--color-signal)] py-1 pl-4 text-sm text-[var(--color-muted)] [&>p:last-child]:mb-0">
          {children}
        </aside>
      );

    case "checkpoint":
      return (
        <section className="my-8 rounded-sm border border-dashed border-[var(--color-rule)] p-5">
          <span className="mb-2 block font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.14em] text-[var(--color-accent)]">
            Checkpoint
          </span>
          <div className="text-sm [&>p:last-child]:mb-0">{children}</div>
        </section>
      );

    case "predict":
      return (
        <Predict question={attrs.question ? String(attrs.question) : undefined}>{children}</Predict>
      );

    case "try":
      // A shell needs to know which lab's image and seed to use, and lessons
      // outside a topic have no lab to borrow. Fall back to the prose rather
      // than render a button that cannot work.
      if (!topicSlug || !attrs.lab) {
        return <div className="my-6">{children}</div>;
      }
      return (
        <TryIt
          topicSlug={topicSlug}
          labSlug={String(attrs.lab)}
          title={attrs.title ? String(attrs.title) : undefined}
          run={attrs.run ? String(attrs.run) : undefined}
        >
          {children}
        </TryIt>
      );

    case "caption":
      // A div rather than a <p>: the loader emits the caption text as a
      // container directive, so its children are already a paragraph, and
      // <p> inside <p> is invalid HTML that React reports as a hydration
      // mismatch. The inner paragraph carries the styling instead.
      return (
        <div className="-mt-4 mb-6 text-center font-[family-name:var(--font-mono)] text-[0.65rem] uppercase tracking-[0.1em] text-[var(--color-muted)] [&>p]:mb-0 [&>p]:leading-snug">
          {children}
        </div>
      );

    default:
      return <div className="my-6">{children}</div>;
  }
}

/**
 * Built per render rather than defined once, because `:::try` needs to know
 * which topic the lesson belongs to in order to open a shell for it.
 */
function componentsFor(topicSlug?: string): Components {
  return {
    h2: ({ children }) => (
      <h2 className="mb-3 mt-12 scroll-mt-24 font-[family-name:var(--font-display)] text-2xl font-semibold tracking-tight text-balance">
        {children}
      </h2>
    ),
    h3: ({ children }) => (
      <h3 className="mb-2 mt-8 scroll-mt-24 text-base font-semibold">{children}</h3>
    ),
    p: ({ children }) => <p className="mb-4 leading-[1.75]">{children}</p>,
    ul: ({ children }) => <ul className="mb-4 list-disc space-y-1.5 pl-5">{children}</ul>,
    ol: ({ children }) => <ol className="mb-4 list-decimal space-y-1.5 pl-5">{children}</ol>,
    a: ({ href, children }) => (
      <a href={href} className="text-[var(--color-accent)] underline underline-offset-[3px]">
        {children}
      </a>
    ),
    strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
    blockquote: ({ children }) => (
      <blockquote className="my-6 border-l-2 border-[var(--color-rule)] pl-4 text-[var(--color-ink-soft)]">
        {children}
      </blockquote>
    ),
    table: ({ children }) => (
      <div className="my-6 overflow-x-auto">
        <table className="w-full border-collapse text-[0.88rem]">{children}</table>
      </div>
    ),
    th: ({ children }) => (
      <th className="border-b border-[var(--color-rule)] pb-2 pr-4 text-left font-[family-name:var(--font-mono)] text-[0.62rem] font-medium uppercase tracking-[0.12em] text-[var(--color-muted)]">
        {children}
      </th>
    ),
    td: ({ children }) => (
      <td className="border-b border-[var(--color-rule-soft)] py-2 pr-4 align-top">{children}</td>
    ),
    code: ({ children, className }) => {
      // Fenced blocks are handled by `pre`; anything reaching here without a
      // language class is inline code.
      if (className?.startsWith("language-")) return <code className={className}>{children}</code>;
      return (
        <code className="rounded-[3px] border border-[var(--color-rule-soft)] bg-[var(--color-surface-2)] px-[0.34em] py-[0.08em] font-[family-name:var(--font-mono)] text-[0.86em]">
          {children}
        </code>
      );
    },
    pre: ({ children }) => {
      // biome-ignore lint/suspicious/noExplicitAny: reaching into the child <code>
      const codeProps = (children as any)?.props ?? {};
      const language = String(codeProps.className ?? "").replace("language-", "");
      const source = textOf(codeProps.children).replace(/\n$/, "");

      if (language === "mermaid") {
        return (
          <figure className="my-6">
            <Mermaid chart={source} />
          </figure>
        );
      }
      return (
        <figure className="my-6">
          <CodeBlock code={source} language={language || undefined} />
        </figure>
      );
    },
    // biome-ignore lint/suspicious/noExplicitAny: data-* attributes are not in the type
    div: ({ children, ...rest }: any) => {
      const name = rest["data-directive"];
      if (!name) return <div>{children}</div>;
      return (
        <Directive name={String(name)} attrs={rest} topicSlug={topicSlug}>
          {children}
        </Directive>
      );
    },
  };
}

export function Markdown({ body, topicSlug }: { body: string; topicSlug?: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkDirective, remarkDirectiveToElements]}
      components={componentsFor(topicSlug)}
    >
      {body}
    </ReactMarkdown>
  );
}
