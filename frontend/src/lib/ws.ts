"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import type { WSMessage, WSNewSignal } from "@/types";

function getWsUrl(): string {
  if (typeof window === "undefined") return "ws://localhost:8000/api/v1/ws/signals";
  // Next.js rewrites don't proxy WebSocket — connect directly to backend
  const backendHost = process.env.NEXT_PUBLIC_WS_URL
    || (window.location.hostname === "localhost"
      ? "ws://localhost:8000"
      : `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}`);
  return `${backendHost}/api/v1/ws/signals`;
}
const WS_URL = getWsUrl();

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
  const onSignalRef = useRef(onSignal);
  onSignalRef.current = onSignal;

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
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
      reconnectTimeout.current = setTimeout(connect, 3000);
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
