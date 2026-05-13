"use client";

import { useEffect, useState, createContext, useContext } from "react";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import Link from "next/link";

interface ComplianceState {
  loaded: boolean;
  pct: number;
  requiredCount: number;
  completedCount: number;
}

// Global cache
let _cache: ComplianceState | null = null;
let _cacheTime = 0;
const CACHE_TTL = 120_000; // 2 min

/**
 * Feature tiers based on compliance progress:
 * 0%  — informational only (signals view, leaderboard, backtest, profile)
 * 30% — basic monetization (premium, referrals)
 * 60% — financial operations (execution, copy trading, marketplace)
 */
const FEATURE_TIERS: Record<string, number> = {
  "/dashboard": 0,
  "/dashboard/leaderboard": 0,
  "/dashboard/backtest": 0,
  "/dashboard/profile": 0,
  "/dashboard/compliance": 0,
  "/dashboard/capacity": 0,
  "/dashboard/create-signal": 0,
  "/dashboard/kyc": 0,
  "/dashboard/telegram": 0,
  "/dashboard/store": 30,
  "/dashboard/premium": 30,
  "/dashboard/referrals": 30,
  "/dashboard/revenue": 0,
  "/dashboard/execution": 60,
  "/dashboard/copy-trading": 60,
  "/dashboard/marketplace": 60,
};

function getRequiredPct(path: string): number {
  if (FEATURE_TIERS[path] !== undefined) return FEATURE_TIERS[path];
  for (const [prefix, pct] of Object.entries(FEATURE_TIERS)) {
    if (path.startsWith(prefix + "/")) return pct;
  }
  return 0;
}

// ─── Context for sidebar to read compliance state ────────
const ComplianceContext = createContext<ComplianceState>({ loaded: false, pct: 100, requiredCount: 0, completedCount: 0 });

export function useCompliance() {
  return useContext(ComplianceContext);
}

/**
 * Checks if a given path is accessible at the current compliance level.
 */
export function isFeatureAccessible(path: string, pct: number): boolean {
  return pct >= getRequiredPct(path);
}

export { FEATURE_TIERS };

/**
 * Wraps dashboard content. Fetches compliance level for ALL users
 * and blocks commercial features until platform has required documents.
 */
export function ComplianceGate({ path, children }: { path: string; children: React.ReactNode }) {
  const { user } = useAuth();
  const { locale } = useI18n();
  const isRu = locale === "ru";
  const isAdmin = user?.role === "admin";
  const [devMode, setDevMode] = useState(false);
  const [state, setState] = useState<ComplianceState>(
    _cache || { loaded: false, pct: 100, requiredCount: 0, completedCount: 0 }
  );

  useEffect(() => {
    if (!user) return;

    if (_cache && Date.now() - _cacheTime < CACHE_TTL) {
      setState(_cache);
      return;
    }

    const load = async () => {
      try {
        const token = localStorage.getItem("token");
        const resp = await fetch("/api/v1/compliance/level", {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (resp.ok) {
          const data = await resp.json();
          const s: ComplianceState = {
            loaded: true,
            pct: data.compliance_pct,
            requiredCount: data.total_required,
            completedCount: data.total_completed,
          };
          _cache = s;
          _cacheTime = Date.now();
          setState(s);
        } else {
          setState(prev => ({ ...prev, loaded: true }));
        }
      } catch {
        setState(prev => ({ ...prev, loaded: true }));
      }
    };
    load();
  }, [user]);

  if (!state.loaded) {
    return (
      <ComplianceContext.Provider value={state}>
        {children}
      </ComplianceContext.Provider>
    );
  }

  const requiredPct = getRequiredPct(path);
  const accessible = state.pct >= requiredPct;

  // Feature is available — render normally
  if (accessible) {
    return (
      <ComplianceContext.Provider value={state}>
        {children}
      </ComplianceContext.Provider>
    );
  }

  // Admin dev mode — show content with warning banner
  if (isAdmin && devMode) {
    return (
      <ComplianceContext.Provider value={state}>
        <div className="mb-4 rounded-xl border-2 border-yellow-500/50 bg-yellow-500/5 px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-yellow-400">
                {isRu ? "Режим разработки" : "Dev Mode"}
              </span>
              <span className="text-xs text-yellow-400/60">
                {isRu
                  ? `Юр. соответствие: ${state.pct}% (требуется ${requiredPct}%). Раздел заблокирован для пользователей.`
                  : `Compliance: ${state.pct}% (required ${requiredPct}%). Section is locked for users.`}
              </span>
            </div>
            <button
              onClick={() => setDevMode(false)}
              className="rounded-lg border border-yellow-500/30 px-3 py-1 text-xs text-yellow-400 hover:bg-yellow-500/10"
            >
              {isRu ? "Закрыть" : "Close"}
            </button>
          </div>
        </div>
        {children}
      </ComplianceContext.Provider>
    );
  }

  // Feature is BLOCKED
  return (
    <ComplianceContext.Provider value={state}>
      <div className="mx-auto max-w-2xl py-12">
        <div className="rounded-2xl border-2 border-red-500/50 bg-red-500/5 p-8 text-center">
          <div className="mb-4 text-4xl font-bold text-red-400">
            {isRu ? "Раздел временно недоступен" : "Section Temporarily Unavailable"}
          </div>
          <p className="mb-4 text-text-secondary">
            {isRu
              ? "Этот функционал будет доступен после завершения регистрации платформы и загрузки необходимых юридических документов оператором."
              : "This feature will be available after the platform completes registration and the operator uploads the required legal documents."}
          </p>

          {/* Progress — only show details to admin */}
          {isAdmin && (
            <div className="mx-auto mb-6 max-w-xs">
              <div className="mb-1 flex justify-between text-xs text-text-muted">
                <span>{state.completedCount}/{state.requiredCount}</span>
                <span>{state.pct}% / {requiredPct}%</span>
              </div>
              <div className="h-3 overflow-hidden rounded-full bg-surface">
                <div className="h-full rounded-full bg-red-500 transition-all" style={{ width: `${state.pct}%` }} />
              </div>
            </div>
          )}

          <div className="flex justify-center gap-3">
            {isAdmin && (
              <Link
                href="/dashboard/compliance"
                className="rounded-lg bg-brand-600 px-6 py-3 text-sm font-medium text-white hover:bg-brand-700"
              >
                {isRu ? "Загрузить документы" : "Upload Documents"}
              </Link>
            )}
            {isAdmin && (
              <button
                onClick={() => setDevMode(true)}
                className="rounded-lg border border-yellow-500/30 bg-yellow-500/10 px-6 py-3 text-sm font-medium text-yellow-400 hover:bg-yellow-500/20"
              >
                {isRu ? "К разработке" : "Dev Preview"}
              </button>
            )}
            <Link
              href="/dashboard"
              className="rounded-lg border border-border px-6 py-3 text-sm text-text-secondary hover:bg-surface-hover"
            >
              {isRu ? "К сигналам" : "Back to Signals"}
            </Link>
          </div>

          <p className="mt-6 text-xs text-text-muted">
            {isRu
              ? "Информационные разделы (Сигналы, Лидерборд, Бэктест, Профиль) доступны без ограничений. Данные на платформе НЕ являются индивидуальной инвестиционной рекомендацией."
              : "Informational sections (Signals, Leaderboard, Backtest, Profile) remain accessible. Data on the platform is NOT an individual investment recommendation."}
          </p>
        </div>
      </div>
    </ComplianceContext.Provider>
  );
}
