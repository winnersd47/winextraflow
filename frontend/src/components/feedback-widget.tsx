"use client";

import { useState } from "react";
import { useI18n } from "@/lib/i18n";

/**
 * Floating feedback button + modal.
 * Appears on every dashboard page in bottom-right corner.
 */

const TYPES = [
  { key: "review", ru: "Отзыв", en: "Review", icon: "⭐" },
  { key: "feature_request", ru: "Предложение", en: "Feature Request", icon: "💡" },
  { key: "bug_report", ru: "Ошибка", en: "Bug Report", icon: "🐛" },
  { key: "suggestion", ru: "Идея", en: "Suggestion", icon: "💬" },
];

const CATEGORIES = [
  { key: "signals", ru: "Сигналы", en: "Signals" },
  { key: "backtest", ru: "Бэктест", en: "Backtest" },
  { key: "portfolio", ru: "Портфель", en: "Portfolio" },
  { key: "ai", ru: "AI / Аналитика", en: "AI / Analytics" },
  { key: "payments", ru: "Оплата", en: "Payments" },
  { key: "ui", ru: "Интерфейс", en: "UI/UX" },
  { key: "other", ru: "Другое", en: "Other" },
];

export function FeedbackButton() {
  const [open, setOpen] = useState(false);
  const [type, setType] = useState("review");
  const [text, setText] = useState("");
  const [title, setTitle] = useState("");
  const [rating, setRating] = useState(0);
  const [category, setCategory] = useState("");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const { locale } = useI18n();
  const isRu = locale === "ru";

  const handleSubmit = async () => {
    if (!text.trim()) return;
    setSending(true);
    try {
      const token = localStorage.getItem("token");
      const body: any = {
        type,
        text: text.trim(),
        title: title.trim() || null,
        category: category || null,
        page: window.location.pathname,
        browser_info: navigator.userAgent.substring(0, 100),
      };
      if (type === "review" && rating > 0) body.rating = rating;

      const resp = await fetch("/api/v1/feedback", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (resp.ok) {
        setSent(true);
        setText(""); setTitle(""); setRating(0); setCategory("");
        setTimeout(() => { setSent(false); setOpen(false); }, 2000);
      }
    } catch {}
    finally { setSending(false); }
  };

  return (
    <>
      {/* Floating button */}
      <button
        onClick={() => setOpen(!open)}
        className="fixed bottom-6 right-6 z-50 flex h-12 w-12 items-center justify-center rounded-full bg-brand-600 text-white shadow-lg hover:bg-brand-700 transition sm:bottom-8 sm:right-8"
        title={isRu ? "Обратная связь" : "Feedback"}
      >
        {open ? "✕" : "💬"}
      </button>

      {/* Modal */}
      {open && (
        <div className="fixed bottom-20 right-6 z-50 w-80 rounded-2xl border border-border bg-surface-card shadow-2xl sm:right-8 sm:w-96">
          {sent ? (
            <div className="p-8 text-center">
              <div className="text-4xl mb-2">✅</div>
              <p className="font-bold text-text-primary">{isRu ? "Спасибо за отзыв!" : "Thank you!"}</p>
              <p className="text-sm text-text-muted">{isRu ? "Мы прочитаем и ответим" : "We'll read and respond"}</p>
            </div>
          ) : (
            <div className="p-4">
              <h3 className="mb-3 font-bold text-text-primary">{isRu ? "Обратная связь" : "Feedback"}</h3>

              {/* Type selector */}
              <div className="mb-3 flex flex-wrap gap-1.5">
                {TYPES.map(t => (
                  <button key={t.key} onClick={() => setType(t.key)}
                    className={`rounded-lg px-2.5 py-1.5 text-xs font-medium transition ${type === t.key ? "bg-brand-500 text-white" : "bg-surface text-text-secondary hover:bg-surface-hover"}`}>
                    {t.icon} {isRu ? t.ru : t.en}
                  </button>
                ))}
              </div>

              {/* Star rating (for reviews) */}
              {type === "review" && (
                <div className="mb-3 flex items-center gap-1">
                  <span className="text-xs text-text-muted mr-2">{isRu ? "Оценка:" : "Rating:"}</span>
                  {[1, 2, 3, 4, 5].map(s => (
                    <button key={s} onClick={() => setRating(s)}
                      className={`text-xl transition ${s <= rating ? "text-yellow-400" : "text-gray-600"}`}>
                      ★
                    </button>
                  ))}
                </div>
              )}

              {/* Category */}
              <select value={category} onChange={e => setCategory(e.target.value)}
                className="mb-3 w-full rounded-lg border border-border bg-surface px-3 py-2 text-xs text-text-primary">
                <option value="">{isRu ? "Категория (опционально)" : "Category (optional)"}</option>
                {CATEGORIES.map(c => (
                  <option key={c.key} value={c.key}>{isRu ? c.ru : c.en}</option>
                ))}
              </select>

              {/* Title (for feature requests) */}
              {(type === "feature_request" || type === "bug_report") && (
                <input value={title} onChange={e => setTitle(e.target.value)}
                  placeholder={isRu ? "Заголовок (кратко)" : "Title (brief)"}
                  className="mb-3 w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-500" />
              )}

              {/* Text */}
              <textarea value={text} onChange={e => setText(e.target.value)}
                placeholder={
                  type === "review" ? (isRu ? "Расскажите о вашем опыте..." : "Tell us about your experience...") :
                  type === "bug_report" ? (isRu ? "Опишите ошибку: что делали, что ожидали, что произошло" : "Describe the bug: what you did, expected, got") :
                  type === "feature_request" ? (isRu ? "Какую функцию хотите видеть?" : "What feature would you like?") :
                  (isRu ? "Ваше сообщение..." : "Your message...")
                }
                rows={4}
                className="mb-3 w-full resize-none rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-500"
                maxLength={2000} />

              <div className="flex items-center justify-between">
                <span className="text-xs text-text-muted">{text.length}/2000</span>
                <button onClick={handleSubmit} disabled={sending || text.trim().length < 3}
                  className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50 transition">
                  {sending ? "..." : (isRu ? "Отправить" : "Send")}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </>
  );
}
