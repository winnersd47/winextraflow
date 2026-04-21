"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { timeAgo } from "@/lib/utils";
import type { ReferralStats, ReferralTree, ReferralTreeItem } from "@/types";

export default function ReferralsPage() {
  const [stats, setStats] = useState<ReferralStats | null>(null);
  const [tree, setTree] = useState<ReferralTree | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const { t } = useI18n();

  useEffect(() => {
    async function load() {
      try {
        const [s, tr] = await Promise.all([api.getReferralStats(), api.getReferralTree()]);
        setStats(s);
        setTree(tr);
      } catch (err) { console.error(err); }
      finally { setLoading(false); }
    }
    load();
  }, []);

  const copyLink = () => {
    if (stats?.share_link) { navigator.clipboard.writeText(stats.share_link); setCopied(true); setTimeout(() => setCopied(false), 2000); }
  };

  if (loading) return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>;

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-2 text-2xl font-bold text-white">{t("referrals.title")}</h1>
      <p className="mb-6 text-sm text-gray-400">{t("referrals.subtitle")}</p>

      {stats && (
        <>
          <div className="mb-6 rounded-xl border border-gray-800 bg-surface-card p-6">
            <h2 className="mb-3 text-lg font-bold text-white">{t("referrals.yourLink")}</h2>
            <div className="flex gap-2">
              <input type="text" readOnly value={stats.share_link} className="flex-1 rounded-lg border border-gray-700 bg-surface px-4 py-2.5 text-sm text-gray-300" />
              <button onClick={copyLink} className="rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-brand-700">
                {copied ? t("referrals.copied") : t("referrals.copy")}
              </button>
            </div>
            <p className="mt-2 text-xs text-gray-500">{t("referrals.code")}: <span className="font-mono text-brand-500">{stats.referral_code}</span></p>
          </div>

          <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <SC label={t("referrals.total")} value={String(stats.total_referrals)} />
            <SC label={t("referrals.direct")} value={String(stats.level1_count)} />
            <SC label={t("referrals.indirect")} value={String(stats.level2_count)} />
            <SC label={t("referrals.rewards")} value={`${stats.total_rewards} ${t("referrals.days")}`} color="text-brand-500" />
          </div>

          <div className="mb-6 rounded-xl border border-gray-800 bg-surface-card p-4">
            <h3 className="mb-2 font-semibold text-white">{t("referrals.howTitle")}</h3>
            <ul className="space-y-1 text-sm text-gray-400">
              <li><span className="text-green-400">{t("referrals.direct")}</span> — {t("referrals.level1")}</li>
              <li><span className="text-blue-400">{t("referrals.indirect")}</span> — {t("referrals.level2")}</li>
            </ul>
          </div>
        </>
      )}

      {tree && tree.referrals.length > 0 && (
        <div className="rounded-xl border border-gray-800 bg-surface-card p-6">
          <h2 className="mb-4 text-lg font-bold text-white">{t("referrals.yourReferrals")} ({tree.total})</h2>
          <div className="space-y-2">
            {tree.referrals.map((item) => (
              <div key={`${item.user.id}-${item.level}`} className="flex items-center justify-between rounded-lg bg-surface p-3">
                <div className="flex items-center gap-3">
                  <span className={`rounded px-2 py-0.5 text-xs font-bold ${item.level === 1 ? "bg-green-500/20 text-green-400" : "bg-blue-500/20 text-blue-400"}`}>L{item.level}</span>
                  <div><p className="text-sm font-medium text-white">{item.user.username}</p><p className="text-xs text-gray-500">{item.user.email}</p></div>
                </div>
                <div className="text-right">
                  <p className="text-sm text-brand-500">+{item.reward_amount} {t("referrals.days")}</p>
                  <p className="text-xs text-gray-500">{timeAgo(item.created_at)}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {tree && tree.referrals.length === 0 && (
        <div className="rounded-xl border border-gray-800 bg-surface-card p-12 text-center">
          <p className="text-gray-400">{t("referrals.empty")}</p>
          <p className="mt-1 text-sm text-gray-500">{t("referrals.emptyHint")}</p>
        </div>
      )}
    </div>
  );
}

function SC({ label, value, color = "text-white" }: { label: string; value: string; color?: string }) {
  return <div className="rounded-xl border border-gray-800 bg-surface-card p-4"><p className="text-xs text-gray-500">{label}</p><p className={`mt-1 text-2xl font-bold ${color}`}>{value}</p></div>;
}
