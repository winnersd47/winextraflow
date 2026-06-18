"use client";

import { useEffect, useState } from "react";
import { useI18n } from "@/lib/i18n";
import { useAuth } from "@/lib/auth";

interface FeedbackItem {
  id: string; type: string; username: string; title: string | null;
  text: string; rating: number | null; category: string | null;
  priority: string; status: string; upvotes: number; voted: boolean;
  is_mine: boolean; admin_reply: string | null; admin_reply_at: string | null;
  created_at: string | null;
}

const TYPE_ICON: Record<string, string> = { review: "⭐", feature_request: "💡", bug_report: "🐛", suggestion: "💬", nps: "📊" };
const TYPE_RU: Record<string, string> = { review: "Отзыв", feature_request: "Предложение", bug_report: "Ошибка", suggestion: "Идея", nps: "NPS" };
const STATUS_COLOR: Record<string, string> = {
  new: "bg-blue-500/20 text-blue-400", reviewed: "bg-yellow-500/20 text-yellow-400",
  in_progress: "bg-purple-500/20 text-purple-400", resolved: "bg-green-500/20 text-green-400",
  wont_fix: "bg-gray-500/20 text-gray-400",
};
const STATUS_RU: Record<string, string> = { new: "Новый", reviewed: "Рассмотрен", in_progress: "В работе", resolved: "Решён", wont_fix: "Отклонён" };

export default function FeedbackPage() {
  const [items, setItems] = useState<FeedbackItem[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");
  const [sort, setSort] = useState("newest");
  const [replyId, setReplyId] = useState<string | null>(null);
  const [replyText, setReplyText] = useState("");
  const [replyStatus, setReplyStatus] = useState("reviewed");
  const { locale } = useI18n();
  const { user } = useAuth();
  const isRu = locale === "ru";
  const isAdmin = user?.role === "admin";

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const load = async () => {
    try {
      const params = new URLSearchParams({ sort, limit: "50" });
      if (filter !== "all") params.set("type", filter);
      const [fbResp, stResp] = await Promise.all([
        fetch(`/api/v1/feedback?${params}`, { headers }),
        fetch("/api/v1/feedback/stats", { headers }),
      ]);
      if (fbResp.ok) setItems((await fbResp.json()).items || []);
      if (stResp.ok) setStats(await stResp.json());
    } catch {}
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [filter, sort]);

  const handleUpvote = async (id: string) => {
    await fetch(`/api/v1/feedback/${id}/upvote`, { method: "POST", headers });
    load();
  };

  const handleReply = async (id: string) => {
    await fetch(`/api/v1/feedback/${id}/reply`, {
      method: "POST", headers,
      body: JSON.stringify({ reply: replyText, status: replyStatus }),
    });
    setReplyId(null); setReplyText("");
    load();
  };

  const handleDelete = async (id: string) => {
    await fetch(`/api/v1/feedback/${id}`, { method: "DELETE", headers });
    load();
  };

  if (loading) return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>;

  return (
    <div>
      <h1 className="mb-2 text-2xl font-bold text-text-primary">{isRu ? "Обратная связь" : "Feedback"}</h1>

      {/* Stats cards */}
      {stats && (
        <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-5">
          <div className="rounded-xl border border-border bg-surface-card p-3 text-center">
            <div className="text-xs text-text-muted">{isRu ? "Всего" : "Total"}</div>
            <div className="text-xl font-bold text-text-primary">{stats.total}</div>
          </div>
          <div className="rounded-xl border border-border bg-surface-card p-3 text-center">
            <div className="text-xs text-text-muted">{isRu ? "Средняя оценка" : "Avg Rating"}</div>
            <div className="text-xl font-bold text-yellow-400">{stats.avg_rating ? `${stats.avg_rating}/5` : "—"}</div>
          </div>
          <div className="rounded-xl border border-border bg-surface-card p-3 text-center">
            <div className="text-xs text-text-muted">NPS</div>
            <div className={`text-xl font-bold ${(stats.nps_score || 0) >= 0 ? "text-green-400" : "text-red-400"}`}>
              {stats.nps_score !== null ? stats.nps_score : "—"}
            </div>
          </div>
          <div className="rounded-xl border border-border bg-surface-card p-3 text-center">
            <div className="text-xs text-text-muted">{isRu ? "Предложений" : "Requests"}</div>
            <div className="text-xl font-bold text-brand-500">{stats.by_type?.feature_request || 0}</div>
          </div>
          <div className="rounded-xl border border-border bg-surface-card p-3 text-center">
            <div className="text-xs text-text-muted">{isRu ? "Ошибок" : "Bugs"}</div>
            <div className="text-xl font-bold text-red-400">{stats.by_type?.bug_report || 0}</div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex gap-1">
          {[
            { key: "all", label: isRu ? "Все" : "All" },
            { key: "review", label: "⭐" },
            { key: "feature_request", label: "💡" },
            { key: "bug_report", label: "🐛" },
            { key: "suggestion", label: "💬" },
          ].map(f => (
            <button key={f.key} onClick={() => setFilter(f.key)}
              className={`rounded-lg px-3 py-2 text-xs font-medium transition ${filter === f.key ? "bg-brand-500 text-white" : "text-text-secondary hover:bg-surface-hover"}`}>
              {f.label}
            </button>
          ))}
        </div>
        <select value={sort} onChange={e => setSort(e.target.value)}
          className="rounded-lg border border-border bg-surface px-3 py-2 text-xs text-text-primary">
          <option value="newest">{isRu ? "Новые" : "Newest"}</option>
          <option value="top_voted">{isRu ? "Популярные" : "Top Voted"}</option>
          <option value="highest_rated">{isRu ? "По оценке" : "Highest Rated"}</option>
        </select>
      </div>

      {/* Feedback list */}
      <div className="space-y-3">
        {items.map(fb => (
          <div key={fb.id} className="rounded-xl border border-border bg-surface-card p-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-lg">{TYPE_ICON[fb.type] || "📝"}</span>
                <span className="text-sm font-medium text-brand-500">{fb.username}</span>
                <span className={`rounded px-2 py-0.5 text-xs ${STATUS_COLOR[fb.status] || ""}`}>
                  {isRu ? (STATUS_RU[fb.status] || fb.status) : fb.status}
                </span>
                {fb.category && <span className="rounded bg-surface-hover px-1.5 py-0.5 text-xs text-text-muted">{fb.category}</span>}
                {fb.rating && <span className="text-xs text-yellow-400">{"★".repeat(fb.rating)}{"☆".repeat(5 - fb.rating)}</span>}
              </div>
              <div className="flex items-center gap-2">
                <button onClick={() => handleUpvote(fb.id)}
                  className={`flex items-center gap-1 rounded px-2 py-1 text-xs transition ${fb.voted ? "bg-brand-500/20 text-brand-500" : "text-text-muted hover:bg-surface-hover"}`}>
                  ▲ {fb.upvotes}
                </button>
                {fb.is_mine && <button onClick={() => handleDelete(fb.id)} className="text-xs text-text-muted hover:text-red-400">✕</button>}
              </div>
            </div>

            {fb.title && <h4 className="font-bold text-text-primary mb-1">{fb.title}</h4>}
            <p className="text-sm text-text-secondary">{fb.text}</p>

            {/* Admin reply */}
            {fb.admin_reply && (
              <div className="mt-3 rounded-lg bg-brand-500/5 border border-brand-500/20 p-3">
                <div className="text-xs text-brand-500 font-medium mb-1">{isRu ? "Ответ команды" : "Team Reply"}</div>
                <p className="text-sm text-text-secondary">{fb.admin_reply}</p>
              </div>
            )}

            {/* Admin reply form */}
            {isAdmin && !fb.admin_reply && replyId === fb.id && (
              <div className="mt-3 space-y-2">
                <textarea value={replyText} onChange={e => setReplyText(e.target.value)}
                  placeholder={isRu ? "Ответ пользователю..." : "Reply to user..."}
                  rows={2}
                  className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none" />
                <div className="flex gap-2">
                  <select value={replyStatus} onChange={e => setReplyStatus(e.target.value)}
                    className="rounded-lg border border-border bg-surface px-2 py-1 text-xs text-text-primary">
                    <option value="reviewed">{isRu ? "Рассмотрен" : "Reviewed"}</option>
                    <option value="in_progress">{isRu ? "В работе" : "In Progress"}</option>
                    <option value="resolved">{isRu ? "Решён" : "Resolved"}</option>
                    <option value="wont_fix">{isRu ? "Отклонён" : "Won't Fix"}</option>
                  </select>
                  <button onClick={() => handleReply(fb.id)} className="rounded-lg bg-brand-600 px-3 py-1 text-xs text-white hover:bg-brand-700">
                    {isRu ? "Ответить" : "Reply"}
                  </button>
                  <button onClick={() => setReplyId(null)} className="text-xs text-text-muted">{isRu ? "Отмена" : "Cancel"}</button>
                </div>
              </div>
            )}
            {isAdmin && !fb.admin_reply && replyId !== fb.id && (
              <button onClick={() => setReplyId(fb.id)} className="mt-2 text-xs text-brand-500 hover:underline">
                {isRu ? "Ответить" : "Reply"}
              </button>
            )}

            <div className="mt-2 text-xs text-text-muted">
              {fb.created_at ? new Date(fb.created_at).toLocaleDateString() : ""}
            </div>
          </div>
        ))}
      </div>

      {items.length === 0 && (
        <div className="rounded-xl border border-border bg-surface-card p-8 text-center">
          <p className="text-text-muted">{isRu ? "Пока нет отзывов. Нажмите 💬 в правом нижнем углу!" : "No feedback yet. Click 💬 in the bottom right!"}</p>
        </div>
      )}
    </div>
  );
}
