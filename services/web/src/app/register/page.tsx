import Link from "next/link";
import { AuthForm } from "@/components/AuthForm";

export const metadata = { title: "Create an account" };

export default function RegisterPage() {
  return (
    <div className="mx-auto w-full max-w-5xl px-6 py-12 flex max-w-sm flex-col gap-6">
      <h1 className="font-[family-name:var(--font-display)] text-3xl font-semibold tracking-tight">
        Create an account
      </h1>
      <p className="text-sm text-[var(--color-ink-soft)]">
        Progress, quiz attempts and diagnoses are recorded against your account so the platform can
        tell you what you actually got wrong.
      </p>
      <AuthForm mode="register" />
      <p className="text-sm text-[var(--color-muted)]">
        Already have one?{" "}
        <Link href="/login" className="text-[var(--color-accent)] underline underline-offset-[3px]">
          Sign in
        </Link>
        .
      </p>
    </div>
  );
}
