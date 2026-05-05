"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function CapacityPage() {
  const { user } = useAuth();
  const [report, setReport] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      try {
        setReport(await api.getCapacityReport());
      } catch (err: any) {
        setError(err.message || "Access denied");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>;
  if (error) return <div className="py-20 text-center text-red-400">{error}</div>;
  if (!report) return null;

  const { metrics, current_tier, next_tier, usage_percent, alert, tiers } = report;

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="mb-2 text-2xl font-bold text-text-primary">System Capacity</h1>
      <p className="mb-6 text-sm text-text-secondary">Infrastructure monitoring and scaling recommendations</p>

      {/* Alert Banner */}
      {alert && (
        <div className={`mb-6 rounded-xl border-2 p-4 ${alert.level === "critical" ? "border-red-500 bg-red-500/5" : alert.level === "warning" ? "border-yellow-500 bg-yellow-500/5" : "border-blue-500 bg-blue-500/5"}`}>
          <div className="flex items-center gap-2">
            <span className="text-xl">{alert.level === "critical" ? "🚨" : alert.level === "warning" ? "⚠️" : "ℹ️"}</span>
            <h3 className={`font-bold ${alert.level === "critical" ? "text-red-400" : alert.level === "warning" ? "text-yellow-400" : "text-blue-400"}`}>{alert.title}</h3>
          </div>
          <p className="mt-1 text-sm text-text-secondary">{alert.message}</p>
          <p className="mt-2 text-sm font-semibold text-text-primary">{alert.action_required}</p>
        </div>
      )}

      {/* Usage Bar */}
      <div className="mb-6 rounded-xl border border-border bg-surface-card p-6">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-text-secondary">Capacity Usage</span>
          <span className={`text-2xl font-bold ${usage_percent > 90 ? "text-red-400" : usage_percent > 70 ? "text-yellow-400" : "text-green-400"}`}>{usage_percent}%</span>
        </div>
        <div className="h-4 overflow-hidden rounded-full bg-surface">
          <div className={`h-full rounded-full transition-all ${usage_percent > 90 ? "bg-red-500" : usage_percent > 70 ? "bg-yellow-500" : "bg-green-500"}`} style={{ width: `${Math.min(100, usage_percent)}%` }} />
        </div>
        <p className="mt-2 text-xs text-text-muted">
          {metrics.users.total.toLocaleString()} users / {current_tier.max_users.toLocaleString()} max (tier: {current_tier.name})
        </p>
      </div>

      {/* Metrics Grid */}
      <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <MC label="Users" value={metrics.users.total.toLocaleString()} />
        <MC label="Signals Today" value={metrics.signals.today.toLocaleString()} />
        <MC label="CPU" value={`${metrics.system.cpu_percent}%`} color={metrics.system.cpu_percent > 80 ? "text-red-400" : undefined} />
        <MC label="RAM" value={`${metrics.system.ram_used_gb}/${metrics.system.ram_total_gb} GB`} color={metrics.system.ram_percent > 80 ? "text-red-400" : undefined} />
      </div>

      {/* System Details */}
      <div className="mb-6 rounded-xl border border-border bg-surface-card p-6">
        <h2 className="mb-4 text-lg font-bold text-text-primary">System Resources</h2>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-text-muted">Total Signals: </span>
            <span className="font-semibold text-text-primary">{metrics.signals.total.toLocaleString()}</span>
          </div>
          <div>
            <span className="text-text-muted">Orders Today: </span>
            <span className="font-semibold text-text-primary">{metrics.orders.today}</span>
          </div>
          <div>
            <span className="text-text-muted">Disk: </span>
            <span className="font-semibold text-text-primary">{metrics.system.disk_used_gb}/{metrics.system.disk_total_gb} GB ({metrics.system.disk_percent}%)</span>
          </div>
          <div>
            <span className="text-text-muted">RAM: </span>
            <span className="font-semibold text-text-primary">{metrics.system.ram_percent}%</span>
          </div>
        </div>
      </div>

      {/* Scaling Tiers */}
      <div className="rounded-xl border border-border bg-surface-card p-6">
        <h2 className="mb-4 text-lg font-bold text-text-primary">Scaling Tiers</h2>
        <div className="space-y-3">
          {tiers.map((tier: any) => (
            <div key={tier.name} className={`flex items-center justify-between rounded-lg p-4 ${tier.is_current ? "border-2 border-brand-500 bg-brand-500/5" : "bg-surface"}`}>
              <div className="flex items-center gap-3">
                {tier.is_current && <span className="rounded bg-brand-500/20 px-2 py-0.5 text-xs font-bold text-brand-500">CURRENT</span>}
                <div>
                  <h3 className="font-semibold text-text-primary uppercase">{tier.name}</h3>
                  <p className="text-xs text-text-muted">up to {tier.max_users.toLocaleString()} users</p>
                </div>
              </div>
              <div className="flex gap-6 text-sm text-right">
                <div><p className="text-text-muted">CPU</p><p className="font-semibold text-text-primary">{tier.cpu} vCPU</p></div>
                <div><p className="text-text-muted">RAM</p><p className="font-semibold text-text-primary">{tier.ram_gb} GB</p></div>
                <div><p className="text-text-muted">Cost</p><p className="font-semibold text-brand-500">${tier.cost_usd}/mo</p></div>
              </div>
            </div>
          ))}
        </div>

        {next_tier && (
          <div className="mt-4 rounded-lg bg-yellow-500/10 border border-yellow-500/30 p-4">
            <p className="text-sm font-semibold text-yellow-400">Next upgrade: {next_tier.name}</p>
            <p className="text-sm text-text-secondary">{next_tier.action}</p>
            <p className="mt-1 text-xs text-text-muted">{next_tier.recommended_cpu} vCPU, {next_tier.recommended_ram_gb} GB RAM — ${next_tier.monthly_cost_usd}/mo</p>
          </div>
        )}
      </div>
    </div>
  );
}

function MC({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="rounded-xl border border-border bg-surface-card p-4">
      <p className="text-xs text-text-muted">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${color || "text-text-primary"}`}>{value}</p>
    </div>
  );
}
