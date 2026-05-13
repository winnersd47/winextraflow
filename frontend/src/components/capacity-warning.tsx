"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

interface CapacityAlert {
  level: string;
  title: string;
  title_ru?: string;
  message: string;
  message_ru?: string;
  current_tier: string;
  next_tier: string | null;
  action_required: string;
  action_required_ru?: string;
}

export function CapacityWarning() {
  const { user } = useAuth();
  const [alert, setAlert] = useState<CapacityAlert | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const { t, locale } = useI18n();
  const isRu = locale === "ru";

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
    const interval = setInterval(check, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [user]);

  if (!alert || dismissed) return null;

  const isCritical = alert.level === "critical";

  return (
    <>
      {isCritical && (
        <div className="fixed inset-0 z-[99] bg-black/60" onClick={() => setDismissed(true)} />
      )}

      <div className={`fixed z-[100] ${isCritical ? "inset-0 flex items-center justify-center p-4" : "bottom-4 right-4 max-w-md"}`}>
        <div className={`rounded-2xl border-2 p-6 shadow-2xl ${
          isCritical
            ? "border-red-500 bg-surface-card w-full max-w-lg"
            : "border-yellow-500 bg-surface-card"
        }`}>
          <div className="flex items-start gap-3">
            <span className={`text-3xl ${isCritical ? "animate-pulse" : ""}`}>
              {isCritical ? "!!" : "!"}
            </span>
            <div className="flex-1">
              <h2 className={`text-lg font-bold ${isCritical ? "text-red-400" : "text-yellow-400"}`}>
                {isRu && alert.title_ru ? alert.title_ru : alert.title}
              </h2>
              <p className="mt-1 text-sm text-text-secondary">{isRu && alert.message_ru ? alert.message_ru : alert.message}</p>
            </div>
            <button onClick={() => setDismissed(true)} className="text-text-muted hover:text-text-primary text-xl">&times;</button>
          </div>

          <div className={`mt-4 rounded-lg p-4 ${isCritical ? "bg-red-500/10" : "bg-yellow-500/10"}`}>
            <p className="text-xs font-bold uppercase text-text-muted">{t("capacity.actionRequired")}</p>
            <p className={`mt-1 text-sm font-semibold ${isCritical ? "text-red-400" : "text-yellow-400"}`}>
              {isRu && alert.action_required_ru ? alert.action_required_ru : alert.action_required}
            </p>
          </div>

          <div className="mt-4 flex items-center gap-4 text-sm">
            <div>
              <span className="text-text-muted">{t("capacity.current")}: </span>
              <span className="font-semibold text-text-primary uppercase">{alert.current_tier}</span>
            </div>
            {alert.next_tier && (
              <>
                <span className="text-text-muted">→</span>
                <div>
                  <span className="text-text-muted">{t("capacity.upgradeTo")}: </span>
                  <span className="font-semibold text-brand-500 uppercase">{alert.next_tier}</span>
                </div>
              </>
            )}
          </div>

          <div className="mt-4 flex gap-3">
            <a href="/dashboard/capacity" className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
              {t("capacity.viewDetails")}
            </a>
            <button onClick={() => setDismissed(true)} className="rounded-lg border border-border px-4 py-2 text-sm text-text-secondary hover:bg-surface-hover">
              {t("capacity.dismiss")}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
