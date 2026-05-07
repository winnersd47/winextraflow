"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import type { ProfileResponse, AchievementResponse } from "@/types";

export default function ProfilePage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [category, setCategory] = useState("all");
  const [tgLink, setTgLink] = useState<{ enabled: boolean; link: string | null; linked: boolean; notifications: boolean } | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [p, tg] = await Promise.all([api.getProfile(), api.getTelegramLink()]);
        setProfile(p);
        setTgLink(tg);
      } catch (err) { console.error(err); }
      finally { setLoading(false); }
    }
    load();
  }, []);

  if (loading) return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>;
  if (!profile) return null;

  const CATEGORIES = [
    { value: "all", label: t("profile.all") },
    { value: "trading", label: t("profile.trading") },
    { value: "social", label: t("profile.social") },
    { value: "learning", label: t("profile.learning") },
    { value: "milestone", label: t("profile.milestone") },
  ];

  const filtered = category === "all" ? profile.achievements : profile.achievements.filter((a) => a.category === category);

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-6 rounded-xl border border-gray-800 bg-surface-card p-6">
        <div className="flex items-center gap-4">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-brand-500/20 text-3xl">
            {profile.xp.level >= 10 ? "💎" : profile.xp.level >= 5 ? "🌟" : "🎮"}
          </div>
          <div className="flex-1">
            <h1 className="text-2xl font-bold text-white">{user?.username}</h1>
            <p className="text-sm text-gray-400">
              {t("profile.level")} {profile.xp.level} &middot; {profile.xp.total_xp} XP &middot; {profile.unlocked_count}/{profile.total_count} {t("profile.achievements")}
            </p>
          </div>
        </div>
        <div className="mt-4">
          <div className="flex justify-between text-xs text-gray-500">
            <span>{t("profile.level")} {profile.xp.level}</span>
            <span>{t("profile.level")} {profile.xp.level + 1}</span>
          </div>
          <div className="mt-1 h-3 overflow-hidden rounded-full bg-gray-700">
            <div className="h-full rounded-full bg-brand-500 transition-all" style={{ width: `${Math.min(100, profile.xp.progress_pct)}%` }} />
          </div>
          <p className="mt-1 text-xs text-gray-500">{profile.xp.current_level_xp} / {profile.xp.next_level_xp} {t("profile.xpToNext")}</p>
        </div>
      </div>

      {/* Telegram Bot */}
      {tgLink?.enabled && (
        <div className="mb-6 rounded-xl border border-border bg-surface-card p-6">
          <div className="flex items-center gap-3 mb-3">
            <span className="text-2xl">✈️</span>
            <h2 className="text-lg font-bold text-text-primary">Telegram Bot</h2>
          </div>
          {tgLink.linked ? (
            <div>
              <p className="text-sm text-green-400 font-medium">✅ {t("telegram.connected")}</p>
              <label className="mt-3 flex items-center gap-2 text-sm text-text-secondary">
                <input type="checkbox" checked={tgLink.notifications} onChange={async (e) => {
                  await api.toggleTelegramNotifications(e.target.checked);
                  setTgLink({ ...tgLink, notifications: e.target.checked });
                }} className="rounded" />
                {t("profile.tgNotifications")}
              </label>
            </div>
          ) : (
            <div>
              <p className="text-sm text-text-secondary mb-3">{t("profile.tgLinkHint")}</p>
              <a href={tgLink.link || "#"} target="_blank" rel="noopener" className="inline-block rounded-lg bg-blue-500 px-4 py-2 text-sm font-medium text-white hover:bg-blue-600">
                {t("profile.tgLinkButton")}
              </a>
            </div>
          )}
        </div>
      )}

      <div className="mb-4 flex gap-1">
        {CATEGORIES.map((c) => (
          <button key={c.value} onClick={() => setCategory(c.value)} className={`rounded-lg px-3 py-2 text-sm capitalize transition ${category === c.value ? "bg-brand-500/20 text-brand-500" : "text-gray-400 hover:bg-surface-hover hover:text-white"}`}>{c.label}</button>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {filtered.map((ach) => <AchievementCard key={ach.id} achievement={ach} t={t} />)}
      </div>
    </div>
  );
}

function AchievementCard({ achievement: a, t }: { achievement: AchievementResponse; t: (k: string) => string }) {
  const pct = a.requirement_value > 0 ? (a.progress / a.requirement_value) * 100 : 0;
  return (
    <div className={`rounded-xl border p-4 transition ${a.is_unlocked ? "border-brand-500/50 bg-brand-500/5" : "border-gray-800 bg-surface-card opacity-70"}`}>
      <div className="flex items-start gap-3">
        <span className="text-2xl">{a.is_hidden && !a.is_unlocked ? "❓" : a.icon}</span>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-white">{a.is_hidden && !a.is_unlocked ? t("profile.hidden") : a.name}</h3>
            {a.is_unlocked && <span className="rounded bg-brand-500/20 px-1.5 py-0.5 text-xs text-brand-500">{t("profile.unlocked")}</span>}
          </div>
          <p className="mt-0.5 text-xs text-gray-400">{a.is_hidden && !a.is_unlocked ? "???" : a.description}</p>
          {a.xp_reward > 0 && <p className="mt-1 text-xs text-yellow-400">+{a.xp_reward} XP</p>}
        </div>
      </div>
      {!a.is_unlocked && !a.is_hidden && (
        <div className="mt-3">
          <div className="flex justify-between text-xs text-gray-500"><span>{t("profile.progress")}</span><span>{a.progress}/{a.requirement_value}</span></div>
          <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-gray-700"><div className="h-full rounded-full bg-brand-500/60" style={{ width: `${Math.min(100, pct)}%` }} /></div>
        </div>
      )}
    </div>
  );
}
