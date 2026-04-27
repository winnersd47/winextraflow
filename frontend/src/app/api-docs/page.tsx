"use client";

import Link from "next/link";
import { useI18n } from "@/lib/i18n";

const API_GROUPS = [
  { title: "Authentication", prefix: "/api/v1/auth", endpoints: [
    { method: "POST", path: "/register", desc: "Register a new user" },
    { method: "POST", path: "/login", desc: "Login and get JWT token" },
    { method: "GET", path: "/me", desc: "Get current user info" },
  ]},
  { title: "Signals", prefix: "/api/v1/signals", endpoints: [
    { method: "GET", path: "/", desc: "List signals with filters" },
    { method: "GET", path: "/{id}", desc: "Get signal details" },
    { method: "GET", path: "/{id}/rating", desc: "Get AI rating breakdown" },
    { method: "POST", path: "/webhook/tradingview", desc: "TradingView webhook" },
    { method: "PATCH", path: "/{id}/close", desc: "Close a signal" },
  ]},
  { title: "Providers", prefix: "/api/v1/providers", endpoints: [
    { method: "GET", path: "/", desc: "List providers" },
    { method: "GET", path: "/leaderboard", desc: "Provider leaderboard" },
    { method: "POST", path: "/", desc: "Create provider" },
  ]},
  { title: "Backtesting", prefix: "/api/v1/backtest", endpoints: [
    { method: "POST", path: "/", desc: "Run backtest on signals" },
  ]},
  { title: "Strategies", prefix: "/api/v1/strategies", endpoints: [
    { method: "GET", path: "/", desc: "Browse marketplace" },
    { method: "GET", path: "/{id}", desc: "Strategy details" },
    { method: "POST", path: "/", desc: "Publish strategy" },
    { method: "POST", path: "/{id}/subscribe", desc: "Subscribe" },
    { method: "DELETE", path: "/{id}/subscribe", desc: "Unsubscribe" },
  ]},
  { title: "Execution", prefix: "/api/v1/execution", endpoints: [
    { method: "POST", path: "/accounts", desc: "Add exchange account" },
    { method: "GET", path: "/accounts", desc: "List accounts" },
    { method: "POST", path: "/execute/{signal_id}", desc: "Execute signal" },
    { method: "GET", path: "/orders", desc: "Order history" },
  ]},
  { title: "Copy Trading", prefix: "/api/v1/copy-trading", endpoints: [
    { method: "GET", path: "/status", desc: "Copy trading status" },
    { method: "GET", path: "/history", desc: "Copy trade history" },
  ]},
  { title: "Referrals", prefix: "/api/v1/referrals", endpoints: [
    { method: "GET", path: "/stats", desc: "Referral statistics" },
    { method: "GET", path: "/my-code", desc: "Get referral code" },
    { method: "GET", path: "/tree", desc: "Referral tree" },
  ]},
  { title: "Premium", prefix: "/api/v1/premium", endpoints: [
    { method: "GET", path: "/status", desc: "Premium status" },
    { method: "POST", path: "/activate", desc: "Activate promo code" },
  ]},
  { title: "Notifications", prefix: "/api/v1/notifications", endpoints: [
    { method: "GET", path: "/", desc: "List notifications" },
    { method: "GET", path: "/unread-count", desc: "Unread count" },
    { method: "PATCH", path: "/{id}/read", desc: "Mark as read" },
  ]},
  { title: "Achievements", prefix: "/api/v1/achievements", endpoints: [
    { method: "GET", path: "/profile", desc: "Profile with XP & achievements" },
  ]},
  { title: "WebSocket", prefix: "ws://", endpoints: [
    { method: "WS", path: "/api/v1/ws/signals", desc: "Real-time signal feed" },
  ]},
];

const METHOD_COLORS: Record<string, string> = {
  GET: "bg-blue-500/20 text-blue-400",
  POST: "bg-green-500/20 text-green-400",
  PATCH: "bg-yellow-500/20 text-yellow-400",
  DELETE: "bg-red-500/20 text-red-400",
  WS: "bg-purple-500/20 text-purple-400",
};

export default function ApiDocsPage() {
  const { t, locale, setLocale } = useI18n();

  return (
    <div className="min-h-screen bg-surface">
      <nav className="flex items-center justify-between border-b border-border px-6 py-4 lg:px-16">
        <Link href="/" className="flex items-center gap-2">
          <span className="text-xl font-bold text-brand-500">WinExtra</span>
          <span className="text-xl font-bold text-text-primary">Flow</span>
        </Link>
        <div className="flex items-center gap-3">
          <div className="flex gap-1">
            <button onClick={() => setLocale("ru")} className={`rounded px-2 py-1 text-xs font-bold ${locale === "ru" ? "bg-brand-500 text-white" : "bg-surface-hover text-text-muted"}`}>RUS</button>
            <button onClick={() => setLocale("en")} className={`rounded px-2 py-1 text-xs font-bold ${locale === "en" ? "bg-brand-500 text-white" : "bg-surface-hover text-text-muted"}`}>ENG</button>
          </div>
          <a href="/api/docs" target="_blank" rel="noopener" className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
            Swagger UI
          </a>
        </div>
      </nav>

      <div className="mx-auto max-w-4xl px-6 py-12">
        <h1 className="text-3xl font-bold text-text-primary">{t("landing.footerApi")}</h1>
        <p className="mt-2 text-text-secondary">Base URL: <code className="rounded bg-surface-card px-2 py-0.5 text-brand-500">http://localhost:8000/api/v1</code></p>
        <p className="mt-1 text-sm text-text-muted">Interactive docs: <a href="/api/docs" target="_blank" className="text-brand-500 hover:underline">/api/docs</a> (Swagger) &middot; <a href="/api/redoc" target="_blank" className="text-brand-500 hover:underline">/api/redoc</a> (ReDoc)</p>

        <div className="mt-10 space-y-8">
          {API_GROUPS.map((group) => (
            <div key={group.title} className="rounded-xl border border-border bg-surface-card p-6">
              <h2 className="text-lg font-bold text-text-primary">{group.title}</h2>
              <p className="mb-4 text-xs text-text-muted">{group.prefix}</p>
              <div className="space-y-2">
                {group.endpoints.map((ep) => (
                  <div key={`${ep.method}-${ep.path}`} className="flex items-center gap-3 rounded-lg bg-surface p-3">
                    <span className={`rounded px-2 py-0.5 text-xs font-bold ${METHOD_COLORS[ep.method] || "bg-gray-500/20 text-gray-400"}`}>{ep.method}</span>
                    <code className="text-sm text-text-primary">{ep.path}</code>
                    <span className="ml-auto text-sm text-text-muted">{ep.desc}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
