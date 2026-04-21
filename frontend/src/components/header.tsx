"use client";

import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

export function Header() {
  const { user, logout } = useAuth();
  const { locale, setLocale, t } = useI18n();

  return (
    <header className="flex h-16 items-center justify-between border-b border-gray-800 bg-surface-card px-6">
      {/* Language Toggle */}
      <div className="flex gap-1">
        <button
          onClick={() => setLocale("ru")}
          className={`rounded px-3 py-1 text-xs font-bold transition ${
            locale === "ru"
              ? "bg-brand-500 text-white"
              : "bg-gray-700 text-gray-400 hover:text-white"
          }`}
        >
          RUS
        </button>
        <button
          onClick={() => setLocale("en")}
          className={`rounded px-3 py-1 text-xs font-bold transition ${
            locale === "en"
              ? "bg-brand-500 text-white"
              : "bg-gray-700 text-gray-400 hover:text-white"
          }`}
        >
          ENG
        </button>
      </div>

      <div className="flex items-center gap-4">
        {user && (
          <>
            <span className="text-sm text-gray-400">{user.username}</span>
            <span className="rounded bg-brand-500/20 px-2 py-0.5 text-xs text-brand-500">
              {user.role}
            </span>
            <button
              onClick={logout}
              className="text-sm text-gray-400 transition hover:text-white"
            >
              {t("auth.logout")}
            </button>
          </>
        )}
      </div>
    </header>
  );
}
