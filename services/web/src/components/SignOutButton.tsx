"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function SignOutButton() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function signOut() {
    setBusy(true);
    // The API revokes the session row as well as clearing the cookie, so the
    // token is dead even if a copy of it exists somewhere.
    await fetch("/api/v1/auth/logout", { method: "POST" }).catch(() => {});
    router.push("/");
    router.refresh();
  }

  return (
    <button
      type="button"
      onClick={signOut}
      disabled={busy}
      className="font-[family-name:var(--font-mono)] text-[0.66rem] uppercase tracking-[0.12em] text-[var(--color-muted)] hover:text-[var(--color-accent)] disabled:opacity-50"
    >
      {busy ? "…" : "Sign out"}
    </button>
  );
}
