"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useTheme } from "@/lib/theme";
import { api } from "@/lib/api";
import { timeAgo } from "@/lib/utils";
import type { NotificationResponse } from "@/types";

export function Header({ onMenuClick }: { onMenuClick?: () => void }) {
  const { user, logout } = useAuth();
  const { locale, setLocale, t } = useI18n();
  const { theme, toggleTheme } = useTheme();
  const [unread, setUnread] = useState(0);
  const [showDropdown, setShowDropdown] = useState(false);
  const [notifications, setNotifications] = useState<NotificationResponse[]>([]);
  const [isPremium, setIsPremium] = useState(false);

  useEffect(() => {
    if (!user) return;
    const load = async () => {
      try {
        const [uc, ps] = await Promise.all([api.getUnreadCount(), api.getPremiumStatus()]);
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
      try { setNotifications((await api.getNotifications(0, 10)).items); } catch {}
    }
    setShowDropdown(!showDropdown);
  };

  const markAllRead = async () => {
    try { await api.markAllRead(); setUnread(0); setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true }))); } catch {}
  };

  return (
    <header className="flex h-16 items-center justify-between border-b border-border bg-surface-card px-4 lg:px-6">
      <div className="flex items-center gap-3">
        {/* Hamburger — mobile only */}
        {onMenuClick && (
          <button onClick={onMenuClick} className="lg:hidden text-text-secondary hover:text-text-primary">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
          </button>
        )}

        {/* Language */}
        <div className="flex gap-1">
          <button onClick={() => setLocale("ru")} className={`rounded px-2 py-1 text-xs font-bold transition ${locale === "ru" ? "bg-brand-500 text-white" : "bg-surface-hover text-text-muted hover:text-text-primary"}`}>RUS</button>
          <button onClick={() => setLocale("en")} className={`rounded px-2 py-1 text-xs font-bold transition ${locale === "en" ? "bg-brand-500 text-white" : "bg-surface-hover text-text-muted hover:text-text-primary"}`}>ENG</button>
        </div>

        {/* Theme toggle */}
        <button onClick={toggleTheme} className="rounded p-1.5 text-text-secondary transition hover:bg-surface-hover hover:text-text-primary" title={theme === "dark" ? "Light mode" : "Dark mode"}>
          {theme === "dark" ? (
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
          ) : (
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
          )}
        </button>
      </div>

      <div className="flex items-center gap-3">
        {user && (
          <>
            {/* Notifications */}
            <div className="relative">
              <button onClick={toggleDropdown} className="relative text-text-secondary transition hover:text-text-primary">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
                {unread > 0 && <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">{unread > 9 ? "9+" : unread}</span>}
              </button>
              {showDropdown && (
                <div className="absolute right-0 top-10 z-50 w-80 rounded-xl border border-border bg-surface-card shadow-xl">
                  <div className="flex items-center justify-between border-b border-border p-3">
                    <span className="text-sm font-semibold text-text-primary">{t("nav.notifications") || "Notifications"}</span>
                    {unread > 0 && <button onClick={markAllRead} className="text-xs text-brand-500 hover:underline">{t("notifications.readAll") || "Read all"}</button>}
                  </div>
                  <div className="max-h-72 overflow-y-auto">
                    {notifications.length === 0 ? (
                      <p className="p-4 text-center text-sm text-text-muted">{t("notifications.empty") || "No notifications"}</p>
                    ) : notifications.map((n) => (
                      <div key={n.id} className={`border-b border-border p-3 ${n.is_read ? "opacity-60" : ""}`}>
                        <p className="text-sm font-medium text-text-primary">{n.title}</p>
                        <p className="text-xs text-text-secondary">{n.message}</p>
                        <p className="mt-1 text-xs text-text-muted">{timeAgo(n.created_at)}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <span className="hidden text-sm text-text-secondary sm:inline">{user.username}</span>
            {isPremium && <span className="rounded bg-yellow-500/20 px-2 py-0.5 text-xs font-bold text-yellow-400">PRO</span>}
            <button onClick={logout} className="text-sm text-text-secondary transition hover:text-text-primary">{t("auth.logout")}</button>
          </>
        )}
      </div>
    </header>
  );
}
