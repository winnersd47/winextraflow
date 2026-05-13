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
      console.log("[WS] Connected");
    };

    ws.onmessage = (event) => {
      try {
        const data: WSMessage = JSON.parse(event.data);
        if (data.type === "new_signal" && onSignalRef.current) {
          onSignalRef.current(data as WSNewSignal);
        }
      } catch (e) {
        console.error("[WS] Parse error:", e);
      }
    };

    ws.onclose = () => {
      setConnected(false);
      console.log("[WS] Disconnected, reconnecting in 3s...");
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
