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
  const [stats, setStats] = useState<any>(null);
  const [tgLink, setTgLink] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [category, setCategory] = useState("all");

  // Edit form
  const [editing, setEditing] = useState(false);
  const [editUsername, setEditUsername] = useState("");
  const [editEmail, setEditEmail] = useState("");
  const [currentPass, setCurrentPass] = useState("");
  const [newPass, setNewPass] = useState("");
  const [editMsg, setEditMsg] = useState("");
  const [editErr, setEditErr] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const [p, s, tg] = await Promise.all([
          api.getProfile(),
          fetch("/api/v1/auth/stats", { headers: { Authorization: `Bearer ${localStorage.getItem("token")}` } }).then(r => r.json()),
          api.getTelegramLink(),
        ]);
        setProfile(p);
        setStats(s);
        setTgLink(tg);
        setEditUsername(s.username);
        setEditEmail(s.email);
      } catch (err) { console.error(err); }
      finally { setLoading(false); }
    }
    load();
  }, []);

  const handleSaveProfile = async () => {
    setEditMsg(""); setEditErr("");
    try {
      const token = localStorage.getItem("token");
      const params = new URLSearchParams();
      if (editUsername !== stats?.username) params.set("username", editUsername);
      if (editEmail !== stats?.email) params.set("email", editEmail);
      if (newPass) { params.set("new_password", newPass); params.set("current_password", currentPass); }
      const res = await fetch(`/api/v1/auth/profile?${params}`, {
        method: "PATCH", headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) { setEditMsg(t("profile.saved")); setEditing(false); setNewPass(""); setCurrentPass(""); }
      else { const d = await res.json(); setEditErr(d.detail || "Failed"); }
    } catch { setEditErr("Network error"); }
  };

  if (loading) return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>;
  if (!profile || !stats) return null;

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
      {/* User Header */}
      <div className="mb-6 rounded-xl border border-border bg-surface-card p-6">
        <div className="flex items-center gap-4">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-brand-500/20 text-3xl">
            {profile.xp.level >= 10 ? "💎" : profile.xp.level >= 5 ? "🌟" : "🎮"}
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold text-text-primary">{stats.username}</h1>
              {stats.is_premium && <span className="rounded bg-brand-500/20 px-2 py-0.5 text-xs font-bold text-brand-500">PRO</span>}
              {stats.kyc_verified && <span className="rounded bg-green-500/20 px-2 py-0.5 text-xs font-bold text-green-400">KYC</span>}
              <span className="rounded bg-surface-hover px-2 py-0.5 text-xs text-text-muted">{stats.role}</span>
            </div>
            <p className="text-sm text-text-secondary">
              {t("profile.level")} {profile.xp.level} · {profile.xp.total_xp} XP · {profile.unlocked_count}/{profile.total_count} {t("profile.achievements")}
            </p>
          </div>
          <button onClick={() => setEditing(!editing)} className="rounded-lg border border-border px-3 py-1.5 text-sm text-text-secondary hover:bg-surface-hover">
            {editing ? t("telegram.cancel") : t("profile.edit")}
          </button>
        </div>

        {/* XP Progress */}
        <div className="mt-4">
          <div className="flex justify-between text-xs text-text-muted">
            <span>{t("profile.level")} {profile.xp.level}</span>
            <span>{t("profile.level")} {profile.xp.level + 1}</span>
          </div>
          <div className="mt-1 h-3 overflow-hidden rounded-full bg-surface">
            <div className="h-full rounded-full bg-brand-500 transition-all" style={{ width: `${Math.min(100, profile.xp.progress_pct)}%` }} />
          </div>
          <p className="mt-1 text-xs text-text-muted">{profile.xp.current_level_xp} / {profile.xp.next_level_xp} {t("profile.xpToNext")}</p>
        </div>
      </div>

      {/* Edit Profile Form */}
      {editing && (
        <div className="mb-6 rounded-xl border border-border bg-surface-card p-6 space-y-3">
          {editErr && <div className="rounded-lg bg-red-500/10 p-3 text-sm text-red-400">{editErr}</div>}
          {editMsg && <div className="rounded-lg bg-green-500/10 p-3 text-sm text-green-400">{editMsg}</div>}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs text-text-secondary">{t("auth.username")}</label>
              <input type="text" value={editUsername} onChange={e => setEditUsername(e.target.value)} className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-500" />
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-secondary">{t("auth.email")}</label>
              <input type="email" value={editEmail} onChange={e => setEditEmail(e.target.value)} className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-500" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs text-text-secondary">{t("profile.currentPassword")}</label>
              <input type="password" value={currentPass} onChange={e => setCurrentPass(e.target.value)} className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-500" />
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-secondary">{t("profile.newPassword")}</label>
              <input type="password" value={newPass} onChange={e => setNewPass(e.target.value)} className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-500" />
            </div>
          </div>
          <button onClick={handleSaveProfile} className="rounded-lg bg-brand-600 px-6 py-2 text-sm font-medium text-white hover:bg-brand-700">{t("profile.save")}</button>
        </div>
      )}

      {/* Stats Cards */}
      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <SC label={t("profile.orders")} value={String(stats.total_orders)} />
        <SC label={t("profile.filled")} value={String(stats.filled_orders)} />
        <SC label={t("profile.premiumDays")} value={String(stats.premium_days_left)} color={stats.is_premium ? "text-brand-500" : undefined} />
        <SC label={t("profile.memberSince")} value={stats.member_since ? new Date(stats.member_since).toLocaleDateString() : "—"} />
      </div>

      {/* Info Cards */}
      <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-2">
        {/* Referral Code */}
        <div className="rounded-xl border border-border bg-surface-card p-4">
          <p className="text-xs text-text-muted">{t("referrals.code")}</p>
          <p className="mt-1 font-mono text-lg font-bold text-brand-500">{stats.referral_code}</p>
        </div>
        {/* KYC Status */}
        <div className="rounded-xl border border-border bg-surface-card p-4">
          <p className="text-xs text-text-muted">KYC</p>
          <p className={`mt-1 font-semibold ${stats.kyc_verified ? "text-green-400" : stats.kyc_status === "pending" ? "text-yellow-400" : "text-red-400"}`}>
            {stats.kyc_verified ? t("kyc.approved") : stats.kyc_status === "pending" ? t("kyc.pending") : t("kyc.notSubmitted")}
          </p>
        </div>
      </div>

      {/* Telegram Bot */}
      {tgLink?.enabled && (
        <div className="mb-6 rounded-xl border border-border bg-surface-card p-6">
          <div className="flex items-center gap-3 mb-3">
            <span className="text-xl">✈️</span>
            <h2 className="font-bold text-text-primary">Telegram Bot</h2>
          </div>
          {tgLink.linked ? (
            <div>
              <p className="text-sm text-green-400 font-medium">{t("telegram.connected")}</p>
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

      {/* Achievements System Explanation */}
      <div className="mb-6 rounded-xl border border-brand-500/30 bg-brand-500/5 p-6">
        <h2 className="text-lg font-bold text-text-primary">{t("profile.achievementsTitle")}</h2>
        <p className="mt-2 text-sm text-text-secondary">{t("profile.achievementsDesc")}</p>
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-lg bg-surface-card p-3 text-center">
            <p className="text-2xl font-bold text-brand-500">{profile.unlocked_count}</p>
            <p className="text-xs text-text-muted">{t("profile.unlocked")}</p>
          </div>
          <div className="rounded-lg bg-surface-card p-3 text-center">
            <p className="text-2xl font-bold text-text-primary">{profile.total_count}</p>
            <p className="text-xs text-text-muted">{t("profile.totalAch")}</p>
          </div>
          <div className="rounded-lg bg-surface-card p-3 text-center">
            <p className="text-2xl font-bold text-yellow-400">{profile.xp.total_xp}</p>
            <p className="text-xs text-text-muted">XP</p>
          </div>
          <div className="rounded-lg bg-surface-card p-3 text-center">
            <p className="text-2xl font-bold text-brand-500">{profile.xp.level}</p>
            <p className="text-xs text-text-muted">{t("profile.level")}</p>
          </div>
        </div>
        <div className="mt-4 rounded-lg bg-surface-card p-3">
          <p className="text-xs font-medium text-text-secondary">{t("profile.achievementsBenefits")}</p>
          <ul className="mt-2 space-y-1 text-xs text-text-muted">
            <li>~ {t("profile.benefit1")}</li>
            <li>~ {t("profile.benefit2")}</li>
            <li>~ {t("profile.benefit3")}</li>
            <li>~ {t("profile.benefit4")}</li>
          </ul>
        </div>
      </div>

      <h2 className="mb-3 text-lg font-bold text-text-primary">{t("profile.achievementsList")}</h2>
      <div className="mb-4 flex gap-1">
        {CATEGORIES.map((c) => (
          <button key={c.value} onClick={() => setCategory(c.value)} className={`rounded-lg px-3 py-2 text-sm capitalize transition ${category === c.value ? "bg-brand-500/20 text-brand-500" : "text-text-secondary hover:bg-surface-hover hover:text-text-primary"}`}>{c.label}</button>
        ))}
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {filtered.map((ach) => <AchCard key={ach.id} a={ach} t={t} />)}
      </div>

      {/* Revenue — admin only */}
      {stats.role === "admin" && <RevenueBlock />}

      {/* Delete Account */}
      <div className="mt-8 rounded-xl border border-red-500/30 bg-red-500/5 p-4">
        <p className="text-sm text-red-400 font-medium">{t("profile.dangerZone")}</p>
        <button onClick={async () => {
          if (!confirm(t("profile.deleteConfirm"))) return;
          const token = localStorage.getItem("token");
          await fetch("/api/v1/auth/account", { method: "DELETE", headers: { Authorization: `Bearer ${token}` } });
          localStorage.removeItem("token");
          window.location.href = "/";
        }} className="mt-2 rounded-lg border border-red-500 px-4 py-2 text-sm text-red-400 hover:bg-red-500/10">
          {t("profile.deleteAccount")}
        </button>
      </div>
    </div>
  );
}

function SC({ label, value, color }: { label: string; value: string; color?: string }) {
  return <div className="rounded-xl border border-border bg-surface-card p-3"><p className="text-xs text-text-muted">{label}</p><p className={`mt-1 text-xl font-bold ${color || "text-text-primary"}`}>{value}</p></div>;
}

function AchCard({ a, t }: { a: AchievementResponse; t: (k: string) => string }) {
  const pct = a.requirement_value > 0 ? (a.progress / a.requirement_value) * 100 : 0;
  // Use i18n translation if available, fallback to backend value
  const achName = t(`ach.${a.code}.name`) !== `ach.${a.code}.name` ? t(`ach.${a.code}.name`) : a.name;
  const achDesc = t(`ach.${a.code}.desc`) !== `ach.${a.code}.desc` ? t(`ach.${a.code}.desc`) : a.description;
  return (
    <div className={`rounded-xl border p-4 transition ${a.is_unlocked ? "border-brand-500/50 bg-brand-500/5" : "border-border bg-surface-card opacity-70"}`}>
      <div className="flex items-start gap-3">
        <span className="text-2xl">{a.is_hidden && !a.is_unlocked ? "?" : a.icon}</span>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-text-primary">{a.is_hidden && !a.is_unlocked ? t("profile.hidden") : achName}</h3>
            {a.is_unlocked && <span className="rounded bg-brand-500/20 px-1.5 py-0.5 text-xs text-brand-500">{t("profile.unlocked")}</span>}
          </div>
          <p className="mt-0.5 text-xs text-text-secondary">{a.is_hidden && !a.is_unlocked ? "???" : achDesc}</p>
          {a.xp_reward > 0 && <p className="mt-1 text-xs text-yellow-400">+{a.xp_reward} XP</p>}
        </div>
      </div>
      {!a.is_unlocked && !a.is_hidden && (
        <div className="mt-3">
          <div className="flex justify-between text-xs text-text-muted"><span>{t("profile.progress")}</span><span>{a.progress}/{a.requirement_value}</span></div>
          <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-surface"><div className="h-full rounded-full bg-brand-500/60" style={{ width: `${Math.min(100, pct)}%` }} /></div>
        </div>
      )}
    </div>
  );
}

function RevenueBlock() {
  const [data, setData] = useState<any>(null);
  useEffect(() => {
    const load = async () => {
      try {
        const token = localStorage.getItem("token");
        const resp = await fetch("/api/v1/admin/revenue", { headers: { Authorization: `Bearer ${token}` } });
        if (resp.ok) setData(await resp.json());
      } catch {}
    };
    load();
  }, []);
  if (!data) return null;
  const { revenue, stage, alerts } = data;
  const pct = stage.usage_pct;
  return (
    <div className="mt-6 rounded-xl border border-border bg-surface-card p-6">
      <h2 className="mb-4 text-lg font-bold text-text-primary">Доходы и налоги ({revenue.year})</h2>
      {alerts.map((a: any, i: number) => (
        <div key={i} className={`mb-3 rounded-lg p-3 text-sm ${a.level === "critical" ? "bg-red-500/10 text-red-400" : a.level === "warning" ? "bg-yellow-500/10 text-yellow-400" : "bg-blue-500/10 text-blue-400"}`}>
          <strong>{a.title_ru}</strong>: {a.message_ru}
        </div>
      ))}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="rounded-lg bg-surface p-3 text-center">
          <p className="text-xs text-text-muted">Доход (USD)</p>
          <p className="text-xl font-bold text-text-primary">${revenue.total_usd.toLocaleString()}</p>
        </div>
        <div className="rounded-lg bg-surface p-3 text-center">
          <p className="text-xs text-text-muted">Доход (RUB)</p>
          <p className="text-xl font-bold text-text-primary">{revenue.total_rub.toLocaleString("ru-RU")} R</p>
        </div>
        <div className="rounded-lg bg-surface p-3 text-center">
          <p className="text-xs text-text-muted">Статус</p>
          <p className="text-sm font-bold text-brand-500">{stage.name_ru}</p>
        </div>
      </div>
      <div className="mb-2 flex justify-between text-xs text-text-muted">
        <span>{revenue.total_rub.toLocaleString("ru-RU")} руб</span>
        <span>{pct}% / {stage.max_revenue_rub.toLocaleString("ru-RU")} руб</span>
      </div>
      <div className="h-3 overflow-hidden rounded-full bg-surface">
        <div className={`h-full rounded-full transition-all ${pct >= 90 ? "bg-red-500" : pct >= 70 ? "bg-yellow-500" : "bg-green-500"}`} style={{ width: `${Math.min(100, pct)}%` }} />
      </div>
      <p className="mt-2 text-xs text-text-muted">Осталось до лимита: {stage.remaining_rub.toLocaleString("ru-RU")} руб (налог {stage.tax_rate})</p>
      <a href="/dashboard/revenue" className="mt-3 inline-block text-xs text-brand-500 hover:underline">Подробный отчёт →</a>
    </div>
  );
}
