import type { Metadata } from "next";
import Link from "next/link";
import { SearchBox } from "@/components/SearchBox";
import { SignOutButton } from "@/components/SignOutButton";
import { ThemeToggle } from "@/components/ThemeToggle";
import { getCurrentUser } from "@/lib/api";
import { themeInitScript } from "@/lib/theme";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Groundwork",
    template: "%s · Groundwork",
  },
  description:
    "Build DevOps from the ground up — foundations, hands-on labs, and production reality.",
};

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const user = await getCurrentUser();

  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Runs before first paint so a reader who chose dark never sees a
            frame of light. The preference is in localStorage, which the server
            cannot read, so this cannot be done in the rendered markup. */}
        {/* biome-ignore lint/security/noDangerouslySetInnerHtml: fixed literal, no interpolation of user input */}
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className="min-h-dvh antialiased">
        {/* Visually hidden until focused. The player's outline is fifteen
            links, so without this every keyboard user tabs through the whole
            table of contents before reaching the lesson — on every screen. */}
        <a
          href="#content"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-sm focus:border focus:border-[var(--color-accent)] focus:bg-[var(--color-surface)] focus:px-4 focus:py-2 focus:text-sm"
        >
          Skip to content
        </a>
        <div className="flex min-h-dvh flex-col">
          <header className="border-b border-[var(--color-rule)] bg-[var(--color-surface)]">
            <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-6 gap-y-3 px-6 py-4">
              <div className="flex items-baseline gap-4">
                <Link
                  href="/"
                  className="font-[family-name:var(--font-display)] text-xl font-semibold tracking-tight"
                >
                  Groundwork
                </Link>
                <span className="hidden font-[family-name:var(--font-mono)] text-[0.68rem] uppercase tracking-[0.14em] text-[var(--color-muted)] lg:inline">
                  Build DevOps from the ground up
                </span>
              </div>
              <nav className="flex flex-1 flex-wrap items-center justify-end gap-x-5 gap-y-2">
                <SearchBox />
                <Link
                  href="/projects"
                  className="font-[family-name:var(--font-mono)] text-[0.66rem] uppercase tracking-[0.12em] text-[var(--color-muted)] hover:text-[var(--color-accent)]"
                >
                  Projects
                </Link>
                {user ? (
                  <>
                    <Link
                      href="/dashboard"
                      className="font-[family-name:var(--font-mono)] text-[0.66rem] uppercase tracking-[0.12em] text-[var(--color-muted)] hover:text-[var(--color-accent)]"
                    >
                      Dashboard
                    </Link>
                    {/* Shown only to admins. The page enforces the same rule
                        server-side — this is so nobody is offered a link to a
                        refusal, not a security control. */}
                    {user.role === "admin" ? (
                      <Link
                        href="/authoring"
                        className="font-[family-name:var(--font-mono)] text-[0.66rem] uppercase tracking-[0.12em] text-[var(--color-muted)] hover:text-[var(--color-accent)]"
                      >
                        Authoring
                      </Link>
                    ) : null}
                    <span className="font-[family-name:var(--font-mono)] text-[0.66rem] text-[var(--color-accent)]">
                      {user.display_name}
                    </span>
                    <SignOutButton />
                  </>
                ) : (
                  <Link
                    href="/login"
                    className="font-[family-name:var(--font-mono)] text-[0.66rem] uppercase tracking-[0.12em] text-[var(--color-muted)] hover:text-[var(--color-accent)]"
                  >
                    Sign in
                  </Link>
                )}
                <ThemeToggle />
              </nav>
            </div>
          </header>

          <main id="content" className="w-full flex-1">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
