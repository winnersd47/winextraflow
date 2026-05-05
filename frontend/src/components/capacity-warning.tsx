"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface CapacityAlert {
  level: string;
  title: string;
  message: string;
  current_tier: string;
  next_tier: string | null;
  action_required: string;
}

export function CapacityWarning() {
  const { user } = useAuth();
  const [alert, setAlert] = useState<CapacityAlert | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (!user || user.role !== "admin") return;

    const check = async () => {
      try {
        const data = await api.getCapacityAlert();
        if (data.alert && (data.alert.level === "warning" || data.alert.level === "critical")) {
          setAlert(data.alert);
        }
      } catch {}
    };

    check();
    const interval = setInterval(check, 5 * 60 * 1000); // Check every 5 min
    return () => clearInterval(interval);
  }, [user]);

  if (!alert || dismissed) return null;

  const isCritical = alert.level === "critical";

  return (
    <>
      {/* Overlay backdrop for critical */}
      {isCritical && (
        <div className="fixed inset-0 z-[99] bg-black/60" onClick={() => setDismissed(true)} />
      )}

      {/* Warning modal */}
      <div className={`fixed z-[100] ${isCritical ? "inset-0 flex items-center justify-center p-4" : "bottom-4 right-4 max-w-md"}`}>
        <div className={`rounded-2xl border-2 p-6 shadow-2xl ${
          isCritical
            ? "border-red-500 bg-surface-card w-full max-w-lg"
            : "border-yellow-500 bg-surface-card"
        }`}>
          {/* Header */}
          <div className="flex items-start gap-3">
            <span className={`text-3xl ${isCritical ? "animate-pulse" : ""}`}>
              {isCritical ? "🚨" : "⚠️"}
            </span>
            <div className="flex-1">
              <h2 className={`text-lg font-bold ${isCritical ? "text-red-400" : "text-yellow-400"}`}>
                {alert.title}
              </h2>
              <p className="mt-1 text-sm text-text-secondary">{alert.message}</p>
            </div>
            <button onClick={() => setDismissed(true)} className="text-text-muted hover:text-text-primary text-xl">&times;</button>
          </div>

          {/* Action required */}
          <div className={`mt-4 rounded-lg p-4 ${isCritical ? "bg-red-500/10" : "bg-yellow-500/10"}`}>
            <p className="text-xs font-bold uppercase text-text-muted">Required action:</p>
            <p className={`mt-1 text-sm font-semibold ${isCritical ? "text-red-400" : "text-yellow-400"}`}>
              {alert.action_required}
            </p>
          </div>

          {/* Tier info */}
          <div className="mt-4 flex items-center gap-4 text-sm">
            <div>
              <span className="text-text-muted">Current: </span>
              <span className="font-semibold text-text-primary uppercase">{alert.current_tier}</span>
            </div>
            {alert.next_tier && (
              <>
                <span className="text-text-muted">→</span>
                <div>
                  <span className="text-text-muted">Upgrade to: </span>
                  <span className="font-semibold text-brand-500 uppercase">{alert.next_tier}</span>
                </div>
              </>
            )}
          </div>

          {/* Buttons */}
          <div className="mt-4 flex gap-3">
            <a href="/dashboard/capacity" className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
              View Details
            </a>
            <button onClick={() => setDismissed(true)} className="rounded-lg border border-border px-4 py-2 text-sm text-text-secondary hover:bg-surface-hover">
              Dismiss
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
