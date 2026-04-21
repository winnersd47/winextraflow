"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { PremiumStatus } from "@/types";

export default function PremiumPage() {
  const [status, setStatus] = useState<PremiumStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [promo, setPromo] = useState("");
  const [activating, setActivating] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const { t } = useI18n();

  useEffect(() => {
    async function load() {
      try { setStatus(await api.getPremiumStatus()); } catch (err) { console.error(err); }
      finally { setLoading(false); }
    }
    load();
  }, []);

  const handleActivate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    setActivating(true);
    try {
      const s = await api.activatePremium(promo);
      setStatus(s);
      setSuccess(t("premium.activated"));
      setPromo("");
    } catch (err: any) { setError(err.message); }
    finally { setActivating(false); }
  };

  if (loading) return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>;

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-2 text-2xl font-bold text-white">{t("premium.title")}</h1>
      <p className="mb-6 text-sm text-gray-400">{t("premium.subtitle")}</p>

      {/* Status Card */}
      {status && (
        <div className={`mb-6 rounded-xl border p-6 ${status.is_premium ? "border-yellow-500/50 bg-yellow-500/5" : "border-gray-800 bg-surface-card"}`}>
          <div className="flex items-center gap-3">
            <span className="text-3xl">{status.is_premium ? "💎" : "🔒"}</span>
            <div>
              <h2 className="text-xl font-bold text-white">
                {status.is_premium ? t("premium.active") : t("premium.inactive")}
              </h2>
              <p className="text-sm text-gray-400">
                {status.is_premium
                  ? `${status.days_left} ${t("premium.daysLeft")}`
                  : t("premium.upgradeHint")}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Features */}
      <div className="mb-6 rounded-xl border border-gray-800 bg-surface-card p-6">
        <h3 className="mb-4 font-semibold text-white">{t("premium.features")}</h3>
        <div className="space-y-3">
          <Feature icon="📊" label={t("premium.featureSignals")} free={t("premium.last10")} premium={t("premium.unlimited")} />
          <Feature icon="🧪" label={t("premium.featureBacktest")} free={t("premium.onePerDay")} premium={t("premium.unlimited")} />
          <Feature icon="⚡" label={t("premium.featureExecution")} free="—" premium="✓" />
          <Feature icon="📋" label={t("premium.featureCopyTrading")} free="—" premium="✓" />
          <Feature icon="🛒" label={t("premium.featurePremiumStrategies")} free="—" premium="✓" />
        </div>
      </div>

      {/* Promo Code */}
      <div className="rounded-xl border border-gray-800 bg-surface-card p-6">
        <h3 className="mb-3 font-semibold text-white">{t("premium.promoTitle")}</h3>
        {error && <div className="mb-3 rounded-lg bg-red-500/10 p-3 text-sm text-red-400">{error}</div>}
        {success && <div className="mb-3 rounded-lg bg-green-500/10 p-3 text-sm text-green-400">{success}</div>}
        <form onSubmit={handleActivate} className="flex gap-2">
          <input type="text" value={promo} onChange={(e) => setPromo(e.target.value)} placeholder={t("premium.promoPlaceholder")} className="flex-1 rounded-lg border border-gray-700 bg-surface px-4 py-2.5 text-white outline-none focus:border-brand-500" />
          <button type="submit" disabled={activating || !promo} className="rounded-lg bg-brand-600 px-6 py-2.5 font-medium text-white transition hover:bg-brand-700 disabled:opacity-50">
            {activating ? "..." : t("premium.activate")}
          </button>
        </form>
        <p className="mt-2 text-xs text-gray-500">{t("premium.promoCodes")}: WELCOME7, TRIAL3</p>
      </div>
    </div>
  );
}

function Feature({ icon, label, free, premium }: { icon: string; label: string; free: string; premium: string }) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2">
        <span>{icon}</span>
        <span className="text-sm text-white">{label}</span>
      </div>
      <div className="flex gap-6 text-sm">
        <span className="w-20 text-center text-gray-500">{free}</span>
        <span className="w-20 text-center text-brand-500">{premium}</span>
      </div>
    </div>
  );
}
