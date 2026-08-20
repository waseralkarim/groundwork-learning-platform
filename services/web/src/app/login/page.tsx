import Link from "next/link";
import { AuthForm } from "@/components/AuthForm";

export const metadata = { title: "Sign in" };

export default function LoginPage() {
  return (
    <div className="mx-auto w-full max-w-5xl px-6 py-12 flex max-w-sm flex-col gap-6">
      <h1 className="font-[family-name:var(--font-display)] text-3xl font-semibold tracking-tight">
        Sign in
      </h1>
      <AuthForm mode="login" />
      <p className="text-sm text-[var(--color-muted)]">
        No account?{" "}
        <Link
          href="/register"
          className="text-[var(--color-accent)] underline underline-offset-[3px]"
        >
          Create one
        </Link>
        .
      </p>
    </div>
  );
}
