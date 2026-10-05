"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import type { WSMessage, WSNewSignal } from "@/types";
import { API_ORIGIN } from "@/lib/api-origin";

/**
 * WebSocket origin.
 *
 * Next.js rewrites don't proxy WebSocket, so this always points straight at the
 * backend. On a static export (Cloudflare Pages) window.location is the CDN, not
 * the API — falling back to it produced wss://<site>/api/v1/ws/signals, which can
 * never connect and left the client reconnecting forever. NEXT_PUBLIC_API_URL is
 * the same variable api-origin.ts uses for fetch, so both stay in sync.
 */
function getWsUrl(): string {
  if (typeof window === "undefined") return "ws://localhost:8000/api/v1/ws/signals";

  const explicit = process.env.NEXT_PUBLIC_WS_URL;
  let origin: string;

  if (explicit) {
    origin = explicit;
  } else if (API_ORIGIN) {
    origin = API_ORIGIN.replace(/^http/, "ws");
  } else if (window.location.hostname === "localhost") {
    origin = "ws://localhost:8000";
  } else {
    // Same-origin backend (nginx in front of both) — the only case where the
    // page host is also the API host.
    origin = `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}`;
  }
  return `${origin.replace(/\/$/, "")}/api/v1/ws/signals`;
}
const WS_URL = getWsUrl();

const RECONNECT_BASE_MS = 3000;
const RECONNECT_MAX_MS = 60000;

// ─── Sound + Badge notifications ───
let _unreadCount = 0;
const _originalTitle = typeof document !== "undefined" ? document.title : "WinExtraFlow";

function playNotificationSound() {
  try {
    const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.frequency.value = 880;
    osc.type = "sine";
    gain.gain.value = 0.15;
    osc.start();
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
    osc.stop(ctx.currentTime + 0.3);
  } catch {}
}

function updateTabBadge(count: number) {
  if (typeof document === "undefined") return;
  _unreadCount = count;
  document.title = count > 0 ? `(${count}) ${_originalTitle}` : _originalTitle;
}

function showBrowserNotification(ticker: string, action: string, confidence: number) {
  if (typeof window === "undefined" || !("Notification" in window)) return;
  if (Notification.permission === "granted") {
    new Notification(`WEF Signal: ${action.toUpperCase()} ${ticker}`, {
      body: `WEF Score: ${(confidence * 100).toFixed(0)}%`,
      icon: "/icon-192.png",
      tag: `signal-${ticker}`,
    });
  }
}

// Request notification permission on first interaction
export function requestNotificationPermission() {
  if (typeof window !== "undefined" && "Notification" in window && Notification.permission === "default") {
    Notification.requestPermission();
  }
}

// Reset badge when user views signals
export function resetBadge() {
  updateTabBadge(0);
}

export function useWebSocket(onSignal?: (msg: WSNewSignal) => void) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const reconnectTimeout = useRef<NodeJS.Timeout>();
  const attempts = useRef(0);
  const onSignalRef = useRef(onSignal);
  onSignalRef.current = onSignal;

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      attempts.current = 0;
      setConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const data: WSMessage = JSON.parse(event.data);
        if (data.type === "new_signal") {
          // Sound + badge + browser notification
          playNotificationSound();
          updateTabBadge(_unreadCount + 1);
          const sig = (data as WSNewSignal).signal;
          if (sig) {
            showBrowserNotification(sig.ticker || "New", sig.action || "signal", sig.ai_confidence || 0);
          }
          if (onSignalRef.current) {
            onSignalRef.current(data as WSNewSignal);
          }
        }
      } catch {
      }
    };

    ws.onclose = () => {
      setConnected(false);
      // Backoff, so an unreachable backend doesn't turn into a reconnect storm.
      const delay = Math.min(RECONNECT_BASE_MS * 2 ** attempts.current, RECONNECT_MAX_MS);
      attempts.current += 1;
      reconnectTimeout.current = setTimeout(connect, delay);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimeout.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { connected };
}
