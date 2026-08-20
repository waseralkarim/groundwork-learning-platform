"use client";

import "@xterm/xterm/css/xterm.css";

import { useCallback, useEffect, useRef, useState } from "react";
import { resolveTheme, TERMINAL_THEME, THEME_CHANGE_EVENT } from "@/lib/theme";

export type ShellStatus = "idle" | "starting" | "running" | "ended";

/**
 * A real shell in a real container, for anything on the site that wants one.
 *
 * Both the lab screen and the inline `:::try` block in a lesson use this, so
 * there is exactly one implementation of the session lifecycle: create, attach
 * a socket, count the TTL down, tear down. Nothing here talks to a runtime —
 * it talks to the broker, which is the whole reason handing someone a shell is
 * acceptable.
 *
 * Sessions are always keyed to a lab, including from a lesson. That is not a
 * shortcut: the lab record is where the image, the seed script, the tier and
 * the quota come from, so a lesson terminal inherits the same isolation and the
 * same limits as the lab itself rather than inventing a second, weaker path.
 */
export function useLabShell({ topicSlug, labSlug }: { topicSlug: string; labSlug: string }) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<ShellStatus>("idle");
  const [remaining, setRemaining] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  // The broker enforces the TTL. This only displays it, because a shell that
  // vanishes without warning is a bad experience even when it is correct.
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

  const attach = useCallback(async (id: string) => {
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
  }, []);

  const start = useCallback(async () => {
    setStatus("starting");
    setError(null);

    try {
      const response = await fetch("/labs/sessions", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ topic_slug: topicSlug, lab_slug: labSlug }),
      });

      if (response.status === 401) {
        setError("Sign in to start a shell — sessions are tracked against your account.");
        setStatus("idle");
        return;
      }
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        setError(
          typeof body.detail === "string"
            ? body.detail
            : "Could not start a shell. The lab runtime may not be enabled.",
        );
        setStatus("idle");
        return;
      }

      const session = await response.json();
      setSessionId(session.session_id);
      setRemaining(session.expires_in_seconds);
      await attach(session.session_id);
      setStatus("running");
    } catch {
      setError("Could not reach the lab broker.");
      setStatus("idle");
    }
  }, [attach, labSlug, topicSlug]);

  const end = useCallback(async () => {
    if (sessionId) {
      await fetch(`/labs/sessions/${sessionId}`, { method: "DELETE" }).catch(() => {});
    }
    teardown();
    setStatus("ended");
  }, [sessionId, teardown]);

  /**
   * Type something into the shell on the learner's behalf.
   *
   * This goes through the same socket their keystrokes do, so the container
   * cannot tell the difference and no new server-side path exists. It is a
   * convenience for a lesson's "run this" button, not a way to execute
   * anything the learner could not have typed.
   */
  const send = useCallback((text: string) => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(text);
      termRef.current?.focus?.();
    }
  }, []);

  return { sessionId, status, remaining, error, mountRef, start, end, send };
}
