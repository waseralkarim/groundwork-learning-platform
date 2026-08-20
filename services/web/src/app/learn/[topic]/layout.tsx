import { notFound } from "next/navigation";

import { CourseSidebar } from "@/components/player/CourseSidebar";
import { ApiError, getMyProgress, getOutline } from "@/lib/api";

export const dynamic = "force-dynamic";

/**
 * The course player shell.
 *
 * The sidebar lives in the layout rather than the page, so navigating between
 * steps does not re-render or re-fetch it — the outline stays put and the scroll
 * position with it. That is the difference between a player and a set of pages.
 */
export default async function LearnLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ topic: string }>;
}) {
  const { topic } = await params;

  let outline: Awaited<ReturnType<typeof getOutline>>;
  try {
    outline = await getOutline(topic);
  } catch (cause) {
    if (cause instanceof ApiError && cause.status === 404) notFound();
    throw cause;
  }

  const progress = await getMyProgress();
  const completed = (progress ?? [])
    .filter((row) => row.status === "completed")
    .map((row) => row.entity_id);

  return (
    <div className="flex min-h-dvh flex-col lg:flex-row">
      <CourseSidebar outline={outline} completed={completed} />
      {/* Not <main>: the root layout already provides the page's single main
          landmark, and a nested second one leaves assistive technology with two
          candidates for "the content" and no way to choose. */}
      <div className="min-w-0 flex-1 px-6 py-8 lg:px-12 lg:py-10">{children}</div>
    </div>
  );
}
