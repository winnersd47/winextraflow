"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { timeAgo } from "@/lib/utils";
import type { PremiumStatus } from "@/types";

export default function PremiumPage() {
  const [status, setStatus] = useState<PremiumStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [promo, setPromo] = useState("");
  const [activating, setActivating] = useState(false);
  const [buying, setBuying] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [payments, setPayments] = useState<any[]>([]);
  const { t } = useI18n();

  const load = async () => {
    try {
      const [s, h] = await Promise.all([api.getPremiumStatus(), api.getPaymentHistory()]);
      setStatus(s);
      setPayments(h.items);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const handleBuy = async (plan: string) => {
    setError("");
    setBuying(plan);
    try {
      const result = await api.createCheckout(plan);
      if (result.demo) {
        // Demo mode: complete immediately
        await api.completeDemoPayment(result.session_id);
        setSuccess(t("premium.activated"));
        load();
      } else {
        // Real Stripe: redirect
        window.location.href = result.checkout_url;
      }
    } catch (err: any) { setError(err.message); }
    finally { setBuying(""); }
  };

  const handlePromo = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    setActivating(true);
    try {
      const s = await api.activatePremium(promo);
      setStatus(s);
      setSuccess(t("premium.activated"));
      setPromo("");
      load();
    } catch (err: any) { setError(err.message); }
    finally { setActivating(false); }
  };

  if (loading) return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>;

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-2 text-2xl font-bold text-text-primary">{t("premium.title")}</h1>
      <p className="mb-6 text-sm text-text-secondary">{t("premium.subtitle")}</p>

      {/* Status */}
      {status && (
        <div className={`mb-6 rounded-xl border p-6 ${status.is_premium ? "border-yellow-500/50 bg-yellow-500/5" : "border-border bg-surface-card"}`}>
          <div className="flex items-center gap-3">
            <span className="text-3xl">{status.is_premium ? "💎" : "🔒"}</span>
            <div>
              <h2 className="text-xl font-bold text-text-primary">{status.is_premium ? t("premium.active") : t("premium.inactive")}</h2>
              <p className="text-sm text-text-secondary">{status.is_premium ? `${status.days_left} ${t("premium.daysLeft")}` : t("premium.upgradeHint")}</p>
            </div>
          </div>
        </div>
      )}

      {error && <div className="mb-4 rounded-lg bg-red-500/10 p-3 text-sm text-red-400">{error}</div>}
      {success && <div className="mb-4 rounded-lg bg-green-500/10 p-3 text-sm text-green-400">{success}</div>}

      {/* Pricing Cards */}
      {!status?.is_premium && (
        <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
          {/* Monthly */}
          <div className="rounded-xl border border-border bg-surface-card p-6">
            <h3 className="text-lg font-bold text-text-primary">Monthly</h3>
            <p className="mt-1 text-3xl font-extrabold text-text-primary">$29<span className="text-base font-normal text-text-muted">/mo</span></p>
            <p className="mt-1 text-xs text-text-muted">30 {t("premium.daysLeft")}</p>
            <button onClick={() => handleBuy("monthly")} disabled={!!buying} className="mt-4 w-full rounded-lg bg-brand-600 py-3 font-medium text-white transition hover:bg-brand-700 disabled:opacity-50">
              {buying === "monthly" ? "..." : t("premium.buyMonthly")}
            </button>
          </div>
          {/* Yearly */}
          <div className="rounded-xl border-2 border-brand-500 bg-surface-card p-6 shadow-lg shadow-brand-500/10">
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-bold text-text-primary">Yearly</h3>
              <span className="rounded bg-brand-500/20 px-2 py-0.5 text-xs font-bold text-brand-500">{t("premium.yearSave")}</span>
            </div>
            <p className="mt-1 text-3xl font-extrabold text-brand-500">$249<span className="text-base font-normal text-text-muted">/yr</span></p>
            <p className="mt-1 text-xs text-text-muted">365 {t("premium.daysLeft")}</p>
            <button onClick={() => handleBuy("yearly")} disabled={!!buying} className="mt-4 w-full rounded-lg bg-brand-600 py-3 font-medium text-white transition hover:bg-brand-700 disabled:opacity-50">
              {buying === "yearly" ? "..." : t("premium.buyYearly")}
            </button>
          </div>
        </div>
      )}

      {/* Features */}
      <div className="mb-6 rounded-xl border border-border bg-surface-card p-6">
        <h3 className="mb-4 font-semibold text-text-primary">{t("premium.features")}</h3>
        <div className="space-y-3">
          <Feature icon="📊" label={t("premium.featureSignals")} free={t("premium.last10")} premium={t("premium.unlimited")} />
          <Feature icon="🧪" label={t("premium.featureBacktest")} free={t("premium.onePerDay")} premium={t("premium.unlimited")} />
          <Feature icon="⚡" label={t("premium.featureExecution")} free="—" premium="✓" />
          <Feature icon="📋" label={t("premium.featureCopyTrading")} free="—" premium="✓" />
          <Feature icon="🛒" label={t("premium.featurePremiumStrategies")} free="—" premium="✓" />
        </div>
      </div>

      {/* Promo Code */}
      <div className="mb-6 rounded-xl border border-border bg-surface-card p-6">
        <h3 className="mb-3 font-semibold text-text-primary">{t("premium.orPromo")}</h3>
        <form onSubmit={handlePromo} className="flex gap-2">
          <input type="text" value={promo} onChange={(e) => setPromo(e.target.value)} placeholder={t("premium.promoPlaceholder")} className="flex-1 rounded-lg border border-border bg-surface px-4 py-2.5 text-text-primary outline-none focus:border-brand-500" />
          <button type="submit" disabled={activating || !promo} className="rounded-lg bg-brand-600 px-6 py-2.5 font-medium text-white transition hover:bg-brand-700 disabled:opacity-50">
            {activating ? "..." : t("premium.activate")}
          </button>
        </form>
        <p className="mt-2 text-xs text-text-muted">{t("premium.promoCodes")}: WELCOME7, TRIAL3</p>
      </div>

      {/* Payment History */}
      <div className="rounded-xl border border-border bg-surface-card p-6">
        <h3 className="mb-3 font-semibold text-text-primary">{t("premium.history")}</h3>
        {payments.length === 0 ? (
          <p className="text-sm text-text-muted">{t("premium.noPayments")}</p>
        ) : (
          <div className="space-y-2">
            {payments.map((p: any) => (
              <div key={p.id} className="flex items-center justify-between rounded-lg bg-surface p-3">
                <div className="flex items-center gap-3">
                  <span className={`rounded px-2 py-0.5 text-xs font-bold ${p.status === "completed" ? "bg-green-500/20 text-green-400" : "bg-yellow-500/20 text-yellow-400"}`}>{p.status}</span>
                  <span className="text-sm text-text-primary">{p.plan} — ${p.amount}</span>
                </div>
                <span className="text-xs text-text-muted">{p.created_at ? timeAgo(p.created_at) : ""}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Feature({ icon, label, free, premium }: { icon: string; label: string; free: string; premium: string }) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2"><span>{icon}</span><span className="text-sm text-text-primary">{label}</span></div>
      <div className="flex gap-6 text-sm"><span className="w-20 text-center text-text-muted">{free}</span><span className="w-20 text-center text-brand-500">{premium}</span></div>
    </div>
  );
}
