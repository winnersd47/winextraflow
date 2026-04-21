"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { api } from "@/lib/api";
import { timeAgo } from "@/lib/utils";
import type { NotificationResponse } from "@/types";

export function Header() {
  const { user, logout } = useAuth();
  const { locale, setLocale, t } = useI18n();
  const [unread, setUnread] = useState(0);
  const [showDropdown, setShowDropdown] = useState(false);
  const [notifications, setNotifications] = useState<NotificationResponse[]>([]);
  const [isPremium, setIsPremium] = useState(false);

  useEffect(() => {
    if (!user) return;
    const load = async () => {
      try {
        const [uc, ps] = await Promise.all([
          api.getUnreadCount(),
          api.getPremiumStatus(),
        ]);
        setUnread(uc.count);
        setIsPremium(ps.is_premium);
      } catch {}
    };
    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, [user]);

  const toggleDropdown = async () => {
    if (!showDropdown) {
      try {
        const data = await api.getNotifications(0, 10);
        setNotifications(data.items);
      } catch {}
    }
    setShowDropdown(!showDropdown);
  };

  const markAllRead = async () => {
    try {
      await api.markAllRead();
      setUnread(0);
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
    } catch {}
  };

  return (
    <header className="flex h-16 items-center justify-between border-b border-gray-800 bg-surface-card px-6">
      <div className="flex gap-1">
        <button onClick={() => setLocale("ru")} className={`rounded px-3 py-1 text-xs font-bold transition ${locale === "ru" ? "bg-brand-500 text-white" : "bg-gray-700 text-gray-400 hover:text-white"}`}>RUS</button>
        <button onClick={() => setLocale("en")} className={`rounded px-3 py-1 text-xs font-bold transition ${locale === "en" ? "bg-brand-500 text-white" : "bg-gray-700 text-gray-400 hover:text-white"}`}>ENG</button>
      </div>

      <div className="flex items-center gap-4">
        {user && (
          <>
            {/* Notification Bell */}
            <div className="relative">
              <button onClick={toggleDropdown} className="relative text-gray-400 transition hover:text-white">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
                {unread > 0 && (
                  <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">{unread > 9 ? "9+" : unread}</span>
                )}
              </button>

              {showDropdown && (
                <div className="absolute right-0 top-10 z-50 w-80 rounded-xl border border-gray-700 bg-surface-card shadow-xl">
                  <div className="flex items-center justify-between border-b border-gray-700 p-3">
                    <span className="text-sm font-semibold text-white">{t("nav.notifications") || "Notifications"}</span>
                    {unread > 0 && (
                      <button onClick={markAllRead} className="text-xs text-brand-500 hover:underline">{t("notifications.readAll") || "Read all"}</button>
                    )}
                  </div>
                  <div className="max-h-72 overflow-y-auto">
                    {notifications.length === 0 ? (
                      <p className="p-4 text-center text-sm text-gray-500">{t("notifications.empty") || "No notifications"}</p>
                    ) : (
                      notifications.map((n) => (
                        <div key={n.id} className={`border-b border-gray-800 p-3 ${n.is_read ? "opacity-60" : ""}`}>
                          <p className="text-sm font-medium text-white">{n.title}</p>
                          <p className="text-xs text-gray-400">{n.message}</p>
                          <p className="mt-1 text-xs text-gray-500">{timeAgo(n.created_at)}</p>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>

            <span className="text-sm text-gray-400">{user.username}</span>
            {isPremium && (
              <span className="rounded bg-yellow-500/20 px-2 py-0.5 text-xs font-bold text-yellow-400">PRO</span>
            )}
            <span className="rounded bg-brand-500/20 px-2 py-0.5 text-xs text-brand-500">{user.role}</span>
            <button onClick={logout} className="text-sm text-gray-400 transition hover:text-white">{t("auth.logout")}</button>
          </>
        )}
      </div>
    </header>
  );
}
