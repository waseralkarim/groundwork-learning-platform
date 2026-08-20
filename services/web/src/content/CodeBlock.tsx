"use client";

import { useState } from "react";

/**
 * A code block with a copy button.
 *
 * Copying commands is the single most frequent interaction on a page like this,
 * so it gets a real affordance rather than leaving the reader to select text.
 */
export function CodeBlock({ code, language }: { code: string; language?: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      // Clipboard access can be denied. Silently leaving the button alone is
      // better than an error the reader cannot act on.
    }
  }

  return (
    <div className="group relative">
      {language ? (
        <span className="absolute left-3 top-2 font-[family-name:var(--font-mono)] text-[0.6rem] uppercase tracking-[0.12em] text-[var(--color-muted)]">
          {language}
        </span>
      ) : null}
      <button
        type="button"
        onClick={copy}
        className="absolute right-2 top-2 rounded-sm border border-[var(--color-rule)] bg-[var(--color-surface)] px-2 py-1 font-[family-name:var(--font-mono)] text-[0.65rem] uppercase tracking-[0.1em] text-[var(--color-muted)] opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100 hover:text-[var(--color-accent)]"
        aria-label={copied ? "Copied" : "Copy code"}
      >
        {copied ? "copied" : "copy"}
      </button>
      <pre className="overflow-x-auto rounded-sm border border-[var(--color-rule)] bg-[var(--color-surface-2)] px-4 pb-4 pt-7 text-[0.84rem] leading-relaxed">
        <code className="font-[family-name:var(--font-mono)]">{code}</code>
      </pre>
    </div>
  );
}
