"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import Link from "next/link";

interface ComplianceState {
  loaded: boolean;
  pct: number;
  requiredCount: number;
  completedCount: number;
  warningCount: number;
}

// Cache compliance state globally to avoid refetching on every page
let _cache: ComplianceState | null = null;
let _cacheTime = 0;
const CACHE_TTL = 60_000; // 1 min

/**
 * Defines which compliance % is required for each feature tier.
 *
 * Tier 0 (0%):   Signal viewing, leaderboard, profile, backtest — always available (informational)
 * Tier 1 (30%):  Premium purchase, referrals — basic monetization
 * Tier 2 (60%):  Execution, copy trading, marketplace subscriptions — financial operations
 * Tier 3 (100%): Full commercial operation — all features
 */
const FEATURE_TIERS: Record<string, number> = {
  // Tier 0 — always available (informational, NOT investment advice)
  "/dashboard": 0,
  "/dashboard/leaderboard": 0,
  "/dashboard/backtest": 0,
  "/dashboard/profile": 0,
  "/dashboard/compliance": 0,
  "/dashboard/capacity": 0,
  "/dashboard/create-signal": 0,
  "/dashboard/kyc": 0,
  "/dashboard/telegram": 0,
  // Tier 1 — basic monetization (30%)
  "/dashboard/premium": 30,
  "/dashboard/referrals": 30,
  // Tier 2 — financial operations (60%)
  "/dashboard/execution": 60,
  "/dashboard/copy-trading": 60,
  "/dashboard/marketplace": 60,
};

function getRequiredPct(path: string): number {
  // Exact match first
  if (FEATURE_TIERS[path] !== undefined) return FEATURE_TIERS[path];
  // Prefix match (for /dashboard/marketplace/[id] etc.)
  for (const [prefix, pct] of Object.entries(FEATURE_TIERS)) {
    if (path.startsWith(prefix + "/")) return pct;
  }
  return 0; // Default: accessible
}

/**
 * Wraps a page and blocks access if compliance % is below required threshold.
 * Admin-only: regular users see content normally (with disclaimer).
 * Only blocks commercial features, not informational ones.
 */
export function ComplianceGate({ path, children }: { path: string; children: React.ReactNode }) {
  const { user } = useAuth();
  const { locale } = useI18n();
  const isRu = locale === "ru";
  const [state, setState] = useState<ComplianceState>(_cache || { loaded: false, pct: 100, requiredCount: 0, completedCount: 0, warningCount: 0 });

  useEffect(() => {
    // Only check for admin users
    if (!user || user.role !== "admin") {
      setState({ loaded: true, pct: 100, requiredCount: 0, completedCount: 0, warningCount: 0 });
      return;
    }

    // Use cache if fresh
    if (_cache && Date.now() - _cacheTime < CACHE_TTL) {
      setState(_cache);
      return;
    }

    const load = async () => {
      try {
        const token = localStorage.getItem("token");
        const resp = await fetch("/api/v1/compliance/warnings", {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (resp.ok) {
          const data = await resp.json();
          // Also fetch full status for pct
          const resp2 = await fetch("/api/v1/compliance/status", {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (resp2.ok) {
            const full = await resp2.json();
            const s: ComplianceState = {
              loaded: true,
              pct: full.compliance_pct,
              requiredCount: full.total_required,
              completedCount: full.total_completed,
              warningCount: data.count,
            };
            _cache = s;
            _cacheTime = Date.now();
            setState(s);
            return;
          }
        }
        setState(prev => ({ ...prev, loaded: true }));
      } catch {
        setState(prev => ({ ...prev, loaded: true }));
      }
    };

    load();
  }, [user]);

  // Non-admin users — always show content (with disclaimer from layout)
  if (!user || user.role !== "admin") return <>{children}</>;

  // Still loading
  if (!state.loaded) return <>{children}</>;

  const requiredPct = getRequiredPct(path);

  // Feature is available
  if (state.pct >= requiredPct) return <>{children}</>;

  // Feature is BLOCKED — show compliance warning
  return (
    <div className="mx-auto max-w-2xl py-12">
      <div className="rounded-2xl border-2 border-red-500/50 bg-red-500/5 p-8 text-center">
        <div className="mb-4 text-4xl font-bold text-red-400">
          {isRu ? "Функция заблокирована" : "Feature Locked"}
        </div>
        <p className="mb-4 text-text-secondary">
          {isRu
            ? `Этот раздел требует минимум ${requiredPct}% юридического соответствия для коммерческой эксплуатации. Текущий прогресс: ${state.pct}%.`
            : `This section requires at least ${requiredPct}% legal compliance for commercial operation. Current progress: ${state.pct}%.`}
        </p>

        {/* Progress bar */}
        <div className="mx-auto mb-6 max-w-xs">
          <div className="mb-1 flex justify-between text-xs text-text-muted">
            <span>{state.completedCount}/{state.requiredCount}</span>
            <span>{state.pct}% / {requiredPct}%</span>
          </div>
          <div className="h-3 overflow-hidden rounded-full bg-surface">
            <div className="h-full rounded-full bg-red-500 transition-all" style={{ width: `${state.pct}%` }} />
          </div>
        </div>

        <p className="mb-6 text-sm text-text-muted">
          {isRu
            ? "Загрузите необходимые документы в разделе Юридическое соответствие для разблокировки."
            : "Upload required documents in the Legal Compliance section to unlock."}
        </p>

        <div className="flex justify-center gap-3">
          <Link
            href="/dashboard/compliance"
            className="rounded-lg bg-brand-600 px-6 py-3 text-sm font-medium text-white hover:bg-brand-700"
          >
            {isRu ? "Перейти к юр. соответствию" : "Go to Compliance"}
          </Link>
          <Link
            href="/dashboard"
            className="rounded-lg border border-border px-6 py-3 text-sm text-text-secondary hover:bg-surface-hover"
          >
            {isRu ? "На главную" : "Back to Dashboard"}
          </Link>
        </div>

        <p className="mt-6 text-xs text-text-muted">
          {isRu
            ? "Информационные разделы (Сигналы, Лидерборд, Бэктест, Профиль) остаются доступными без ограничений. Данные на платформе НЕ являются индивидуальной инвестиционной рекомендацией."
            : "Informational sections (Signals, Leaderboard, Backtest, Profile) remain accessible without restrictions. Data on the platform is NOT an individual investment recommendation."}
        </p>
      </div>
    </div>
  );
}
