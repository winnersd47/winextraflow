"use client";

import { useState, useRef, useEffect } from "react";
import { useI18n } from "@/lib/i18n";

interface Message {
  role: "user" | "assistant";
  text: string;
  signals?: number;
  time: string;
}

const SUGGESTIONS_RU = [
  "Анализ SBER", "Анализ BTCUSDT", "Режим рынка",
  "Топ сигналы", "Лучшие провайдеры", "Анализ GAZP",
];
const SUGGESTIONS_EN = [
  "Analyze SBER", "Analyze BTCUSDT", "Market regime",
  "Top signals", "Best providers", "Analyze AAPL",
];

export default function AIChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const { locale } = useI18n();
  const isRu = locale === "ru";
  const suggestions = isRu ? SUGGESTIONS_RU : SUGGESTIONS_EN;

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async (text?: string) => {
    const msg = (text || input).trim();
    if (!msg || loading) return;
    setInput("");

    const now = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    setMessages(prev => [...prev, { role: "user", text: msg, time: now }]);
    setLoading(true);

    try {
      const token = localStorage.getItem("token");
      const resp = await fetch("/api/v1/ai-chat/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ message: msg }),
      });
      if (resp.ok) {
        const data = await resp.json();
        setMessages(prev => [...prev, {
          role: "assistant",
          text: data.answer,
          signals: data.signals_referenced,
          time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        }]);
      } else {
        const err = await resp.json().catch(() => ({ detail: "Error" }));
        setMessages(prev => [...prev, {
          role: "assistant",
          text: `Error: ${err.detail || resp.statusText}`,
          time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        }]);
      }
    } catch {
      setMessages(prev => [...prev, {
        role: "assistant",
        text: isRu ? "Ошибка соединения с сервером" : "Connection error",
        time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      }]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col">
      {/* Header */}
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-text-primary">
          {isRu ? "AI Ассистент" : "AI Assistant"}
        </h1>
        <p className="text-sm text-text-secondary">
          {isRu
            ? "Анализ тикеров, сигналов и рынка на основе данных платформы"
            : "Ticker, signal, and market analysis based on platform data"}
        </p>
      </div>

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto rounded-xl border border-border bg-surface-card p-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="text-4xl mb-4">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" className="text-brand-500 mx-auto">
                <path d="M2 12c2-3 4-3 6 0s4 3 6 0 4-3 6 0" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
                <path d="M2 17c2-3 4-3 6 0s4 3 6 0 4-3 6 0" stroke="currentColor" strokeWidth="2" strokeLinecap="round" opacity=".4"/>
              </svg>
            </div>
            <h2 className="text-lg font-bold text-text-primary mb-2">
              {isRu ? "Спросите что-нибудь о рынке" : "Ask anything about the market"}
            </h2>
            <p className="text-sm text-text-muted mb-6 max-w-md">
              {isRu
                ? "Я анализирую сигналы, провайдеров и режим рынка на основе данных WinExtraFlow"
                : "I analyze signals, providers, and market regime using WinExtraFlow data"}
            </p>
            {/* Quick suggestions */}
            <div className="flex flex-wrap justify-center gap-2">
              {suggestions.map(s => (
                <button key={s} onClick={() => send(s)}
                  className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-secondary hover:border-brand-500 hover:text-brand-500 transition">
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[80%] rounded-2xl px-4 py-3 ${
              m.role === "user"
                ? "bg-brand-600 text-white"
                : "bg-surface border border-border text-text-primary"
            }`}>
              {m.role === "assistant" ? (
                <div className="whitespace-pre-wrap text-sm leading-relaxed">
                  {m.text.split(/(\*\*[^*]+\*\*)/).map((part, j) =>
                    part.startsWith("**") && part.endsWith("**")
                      ? <strong key={j} className="text-text-primary font-bold">{part.slice(2, -2)}</strong>
                      : <span key={j}>{part}</span>
                  )}
                </div>
              ) : (
                <p className="text-sm">{m.text}</p>
              )}
              <div className={`mt-1 flex items-center gap-2 text-xs ${m.role === "user" ? "text-white/60" : "text-text-muted"}`}>
                <span>{m.time}</span>
                {m.signals !== undefined && m.signals > 0 && (
                  <span className="rounded bg-brand-500/20 px-1.5 py-0.5 text-brand-400">
                    {m.signals} {isRu ? "сигналов" : "signals"}
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="rounded-2xl bg-surface border border-border px-4 py-3">
              <div className="flex gap-1">
                <div className="h-2 w-2 rounded-full bg-brand-500 animate-bounce" style={{ animationDelay: "0ms" }} />
                <div className="h-2 w-2 rounded-full bg-brand-500 animate-bounce" style={{ animationDelay: "150ms" }} />
                <div className="h-2 w-2 rounded-full bg-brand-500 animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
            </div>
          </div>
        )}

        <div ref={endRef} />
      </div>

      {/* Input */}
      <div className="mt-3 flex gap-2">
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && send()}
          placeholder={isRu ? "Спросите про тикер, сигнал или рынок..." : "Ask about a ticker, signal, or market..."}
          className="flex-1 rounded-xl border border-border bg-surface px-4 py-3 text-sm text-text-primary outline-none focus:border-brand-500"
          disabled={loading}
        />
        <button onClick={() => send()} disabled={loading || !input.trim()}
          className="rounded-xl bg-brand-600 px-6 py-3 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50 transition">
          {isRu ? "Отправить" : "Send"}
        </button>
      </div>

      {/* Disclaimer */}
      <p className="mt-2 text-center text-xs text-text-muted">
        {isRu
          ? "Ответы формируются на основе данных платформы. Не является инвестиционной рекомендацией."
          : "Responses are based on platform data. Not investment advice."}
      </p>
    </div>
  );
}
