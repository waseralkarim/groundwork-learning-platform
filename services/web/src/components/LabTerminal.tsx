"use client";

import "@xterm/xterm/css/xterm.css";

import { useCallback, useEffect, useRef, useState } from "react";
import { resolveTheme, TERMINAL_THEME, THEME_CHANGE_EVENT } from "@/lib/theme";

type Step = { id: string; instruction: string; hint: string | null };
type CheckResult = { passed: boolean; describe: string; detail: string };
type StepState = { passed: boolean; checks: CheckResult[] } | null;

/**
 * The lab: instructions on the left, a real shell on the right.
 *
 * The terminal talks to the broker over a WebSocket; the broker talks to the
 * container. There is no path from this component to a runtime, which is what
 * makes handing someone a root shell acceptable.
 *
 * xterm.js is imported lazily — it is large, and only this page needs it.
 */
export function LabTerminal({
  topicSlug,
  labSlug,
  title,
  intro,
  steps,
  durationMinutes,
}: {
  topicSlug: string;
  labSlug: string;
  title: string;
  intro: string;
  steps: Step[];
  durationMinutes: number;
}) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [remaining, setRemaining] = useState<number | null>(null);
  const [status, setStatus] = useState<"idle" | "starting" | "running" | "ended">("idle");
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, StepState>>({});
  const [checking, setChecking] = useState<string | null>(null);
  const [openHints, setOpenHints] = useState<Set<string>>(new Set());

  const mountRef = useRef<HTMLDivElement>(null);
  // biome-ignore lint/suspicious/noExplicitAny: xterm types are loaded lazily
  const termRef = useRef<any>(null);
  const socketRef = useRef<WebSocket | null>(null);

  const teardown = useCallback(() => {
    socketRef.current?.close();
    socketRef.current = null;
    termRef.current?.dispose?.();
    termRef.current = null;
  }, []);

  useEffect(() => teardown, [teardown]);

  // A live shell must follow a theme change too. xterm paints to a canvas, so
  // CSS variables never reach it — the palette has to be reassigned by hand.
  useEffect(() => {
    const onThemeChange = () => {
      if (termRef.current) {
        termRef.current.options.theme = { ...TERMINAL_THEME[resolveTheme()] };
      }
    };
    window.addEventListener(THEME_CHANGE_EVENT, onThemeChange);
    return () => window.removeEventListener(THEME_CHANGE_EVENT, onThemeChange);
  }, []);

  // Countdown. The TTL is enforced by the broker; this only shows it, because a
  // lab that vanishes without warning is a bad experience even when it is
  // correct behaviour.
  useEffect(() => {
    if (remaining === null || status !== "running") return;
    const timer = setInterval(() => {
      setRemaining((value) => {
        if (value === null) return null;
        if (value <= 1) {
          setStatus("ended");
          teardown();
          return 0;
        }
        return value - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [remaining, status, teardown]);

  async function startLab() {
    setStatus("starting");
    setError(null);

    try {
      const response = await fetch("/labs/sessions", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ topic_slug: topicSlug, lab_slug: labSlug }),
      });

      if (response.status === 401) {
        setError("Sign in to start a lab — sessions are tracked against your account.");
        setStatus("idle");
        return;
      }
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        setError(
          typeof body.detail === "string"
            ? body.detail
            : "Could not start a lab. The lab runtime may not be enabled.",
        );
        setStatus("idle");
        return;
      }

      const session = await response.json();
      setSessionId(session.session_id);
      setRemaining(session.expires_in_seconds);
      await attachTerminal(session.session_id);
      setStatus("running");
    } catch {
      setError("Could not reach the lab broker.");
      setStatus("idle");
    }
  }

  async function attachTerminal(id: string) {
    const [{ Terminal }, { FitAddon }] = await Promise.all([
      import("@xterm/xterm"),
      import("@xterm/addon-fit"),
    ]);

    const term = new Terminal({
      fontFamily: 'ui-monospace, "Cascadia Code", "SF Mono", Menlo, Consolas, monospace',
      fontSize: 13,
      cursorBlink: true,
      convertEol: true,
      theme: { ...TERMINAL_THEME[resolveTheme()] },
    });

    const fit = new FitAddon();
    term.loadAddon(fit);
    if (mountRef.current) {
      term.open(mountRef.current);
      fit.fit();
    }
    termRef.current = term;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const socket = new WebSocket(
      `${protocol}//${window.location.host}/labs/sessions/${id}/terminal`,
    );
    socketRef.current = socket;

    socket.onmessage = (event) => term.write(event.data);
    socket.onclose = () => term.write("\r\n\r\n*** Disconnected ***\r\n");
    term.onData((data: string) => {
      if (socket.readyState === WebSocket.OPEN) socket.send(data);
    });

    const onResize = () => fit.fit();
    window.addEventListener("resize", onResize);
  }

  async function endLab() {
    if (sessionId) {
      await fetch(`/labs/sessions/${sessionId}`, { method: "DELETE" }).catch(() => {});
    }
    teardown();
    setStatus("ended");
  }

  async function checkStep(stepId: string) {
    if (!sessionId) return;
    setChecking(stepId);
    try {
      const response = await fetch(`/labs/sessions/${sessionId}/steps/${stepId}/check`, {
        method: "POST",
      });
      if (!response.ok) {
        setResults((r) => ({
          ...r,
          [stepId]: {
            passed: false,
            checks: [{ passed: false, describe: "Check failed to run", detail: "" }],
          },
        }));
        return;
      }
      const body = await response.json();
      setResults((r) => ({ ...r, [stepId]: { passed: body.passed, checks: body.checks } }));
    } finally {
      setChecking(null);
    }
  }

  const completed = steps.filter((s) => results[s.id]?.passed).length;

  return (
    <div className="flex flex-col gap-5">
      <header className="flex flex-wrap items-baseline gap-x-5 gap-y-2">
        {/* h1, not h2: the lab screen suppresses the player's own header to
            give the terminal its vertical space, so this is the page's only
            top-level heading. Without it the document outline starts at h2 and
            a screen-reader user landing here has nothing to orient on. */}
        <h1 className="font-[family-name:var(--font-display)] text-2xl font-semibold tracking-tight">
          {title}
        </h1>
        <span className="font-[family-name:var(--font-mono)] text-[0.66rem] uppercase tracking-[0.12em] text-[var(--color-muted)]">
          {completed}/{steps.length} verified · ~{durationMinutes} min
        </span>
        {status === "running" && remaining !== null ? (
          <span
            className={`font-[family-name:var(--font-mono)] text-[0.66rem] tabular-nums ${
              remaining < 300 ? "text-[var(--color-accent)]" : "text-[var(--color-muted)]"
            }`}
          >
            {Math.floor(remaining / 60)}:{String(remaining % 60).padStart(2, "0")} left
          </span>
        ) : null}
        <div className="ml-auto flex gap-3">
          {status === "idle" || status === "ended" ? (
            <button
              type="button"
              onClick={startLab}
              className="rounded-sm border border-[var(--color-accent)] bg-[var(--color-accent)] px-4 py-1.5 text-sm font-semibold text-[var(--color-surface)]"
            >
              {status === "ended" ? "Start again" : "Start lab"}
            </button>
          ) : null}
          {status === "running" ? (
            <button
              type="button"
              onClick={endLab}
              className="rounded-sm border border-[var(--color-rule)] px-4 py-1.5 text-sm hover:border-[var(--color-accent)]"
            >
              End lab
            </button>
          ) : null}
        </div>
      </header>

      <p className="prose-measure whitespace-pre-wrap text-sm text-[var(--color-ink-soft)]">
        {intro}
      </p>

      {error ? (
        <p
          role="alert"
          className="rounded-sm border border-[var(--color-accent)] bg-[var(--color-surface)] px-4 py-3 text-sm"
        >
          {error}
        </p>
      ) : null}

      {status === "ended" ? (
        <p className="rounded-sm border border-[var(--color-rule)] bg-[var(--color-surface)] px-4 py-3 text-sm text-[var(--color-muted)]">
          This lab has ended and its container is gone. Nothing you wrote persists — that is the
          design, not a limitation.
        </p>
      ) : null}

      <div className="grid gap-5 lg:grid-cols-2">
        <ol className="flex flex-col gap-4">
          {steps.map((step, index) => {
            const result = results[step.id];
            return (
              <li
                key={step.id}
                className={`rounded-sm border p-4 ${
                  result?.passed
                    ? "border-[var(--color-signal)]"
                    : "border-[var(--color-rule)] bg-[var(--color-surface)]"
                }`}
              >
                <div className="flex items-baseline gap-3">
                  <span className="font-[family-name:var(--font-mono)] text-[0.66rem] tabular-nums text-[var(--color-muted)]">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  {result?.passed ? (
                    <span className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.12em] text-[var(--color-signal)]">
                      verified
                    </span>
                  ) : null}
                </div>

                <p className="mt-1.5 whitespace-pre-wrap text-sm">{step.instruction}</p>

                {step.hint ? (
                  <div className="mt-2">
                    {openHints.has(step.id) ? (
                      <p className="border-l-2 border-[var(--color-rule)] pl-3 text-xs text-[var(--color-muted)]">
                        {step.hint}
                      </p>
                    ) : (
                      <button
                        type="button"
                        onClick={() => setOpenHints((h) => new Set(h).add(step.id))}
                        className="font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.11em] text-[var(--color-muted)] hover:text-[var(--color-accent)]"
                      >
                        Hint
                      </button>
                    )}
                  </div>
                ) : null}

                {result && !result.passed ? (
                  <ul className="mt-2 flex flex-col gap-1">
                    {result.checks.map((check) => (
                      <li
                        key={check.describe}
                        className={`text-xs ${
                          check.passed ? "text-[var(--color-signal)]" : "text-[var(--color-accent)]"
                        }`}
                      >
                        {check.passed ? "✓" : "✗"} {check.describe}
                        {check.detail ? (
                          <span className="text-[var(--color-muted)]"> — {check.detail}</span>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                ) : null}

                <button
                  type="button"
                  disabled={status !== "running" || checking === step.id}
                  onClick={() => checkStep(step.id)}
                  className="mt-3 rounded-sm border border-[var(--color-rule)] px-3 py-1 font-[family-name:var(--font-mono)] text-[0.62rem] uppercase tracking-[0.11em] hover:border-[var(--color-accent)] disabled:opacity-40"
                >
                  {checking === step.id ? "checking…" : "Check"}
                </button>
              </li>
            );
          })}
        </ol>

        <div className="lg:sticky lg:top-6 lg:h-[70vh]">
          <div
            ref={mountRef}
            className="h-[60vh] overflow-hidden rounded-sm border border-[var(--color-rule)] bg-[var(--color-surface-2)] p-2 lg:h-full"
          >
            {status === "idle" ? (
              <p className="p-4 font-[family-name:var(--font-mono)] text-sm text-[var(--color-muted)]">
                Start the lab to get a shell.
              </p>
            ) : null}
            {status === "starting" ? (
              <p className="p-4 font-[family-name:var(--font-mono)] text-sm text-[var(--color-muted)]">
                Provisioning an isolated environment…
              </p>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
