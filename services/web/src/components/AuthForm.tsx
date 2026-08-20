"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

/**
 * Sign in / register.
 *
 * Posts to the API through the same origin, so the browser stores the httpOnly
 * session cookie. This component never sees the token — that is the point of
 * httpOnly, and it means an XSS bug here cannot exfiltrate a session.
 */
export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const isRegister = mode === "register";

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);

    try {
      const response = await fetch(`/api/v1/auth/${mode}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(
          isRegister ? { email, password, display_name: displayName } : { email, password },
        ),
      });

      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        setError(
          typeof body.detail === "string"
            ? body.detail
            : response.status === 429
              ? "Too many attempts. Wait a few minutes."
              : "Something went wrong. Try again.",
        );
        return;
      }

      router.push("/dashboard");
      router.refresh();
    } catch {
      setError("Could not reach the server.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex max-w-sm flex-col gap-4">
      {isRegister ? (
        <Field
          label="Display name"
          value={displayName}
          onChange={setDisplayName}
          type="text"
          autoComplete="name"
        />
      ) : null}

      <Field
        label="Email"
        value={email}
        onChange={setEmail}
        type="email"
        autoComplete="email"
        required
      />

      <Field
        label="Password"
        value={password}
        onChange={setPassword}
        type="password"
        autoComplete={isRegister ? "new-password" : "current-password"}
        required
        hint={isRegister ? "At least 12 characters. Length beats complexity." : undefined}
      />

      {error ? (
        <p
          role="alert"
          className="rounded-sm border border-[var(--color-accent)] bg-[var(--color-surface)] px-3 py-2 text-sm"
        >
          {error}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={busy}
        className="rounded-sm border border-[var(--color-accent)] bg-[var(--color-accent)] px-4 py-2 text-sm font-semibold text-[var(--color-surface)] disabled:opacity-50"
      >
        {busy ? "Working…" : isRegister ? "Create account" : "Sign in"}
      </button>
    </form>
  );
}

function Field({
  label,
  value,
  onChange,
  type,
  autoComplete,
  required,
  hint,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type: string;
  autoComplete?: string;
  required?: boolean;
  hint?: string;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="font-[family-name:var(--font-mono)] text-[0.66rem] uppercase tracking-[0.13em] text-[var(--color-muted)]">
        {label}
      </span>
      <input
        type={type}
        value={value}
        required={required}
        autoComplete={autoComplete}
        onChange={(event) => onChange(event.target.value)}
        className="rounded-sm border border-[var(--color-rule)] bg-[var(--color-surface)] px-3 py-2 text-sm"
      />
      {hint ? <span className="text-xs text-[var(--color-muted)]">{hint}</span> : null}
    </label>
  );
}
