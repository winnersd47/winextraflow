"use client";

import { useEffect, useState } from "react";

/**
 * Economic calendar from primary sources, served by /api/v1/public/econ-calendar.
 *
 * Replaces the TradingView calendar widget. The aggregators that could have taken
 * its place are all worse here: Trading Economics, EODHD, FMP and OHLC.dev are paid
 * or key-gated with attribution in their terms, and the open-source option scrapes
 * investing.com against that site's terms. So the data comes from the institutions
 * that publish it: Банк России, MOEX ISS and FRED.
 *
 * Each row names its source, and the component says out loud when a source is
 * missing — an empty calendar and a broken calendar look identical otherwise.
 */

type Event = {
  date: string;
  country: string;
  title: string;
  importance: "high" | "medium" | "low" | string;
  source: string;
  source_url: string;
  actual: number | null;
};

const IMPORTANCE: Record<string, string> = {
  high: "border-l-red-400",
  medium: "border-l-yellow-400",
  low: "border-l-border",
};

const FLAG: Record<string, string> = { RU: "🇷🇺", US: "🇺🇸", EU: "🇪🇺" };

export function EconCalendar({ isRu = true }: { isRu?: boolean }) {
  const [events, setEvents] = useState<Event[]>([]);
  const [notes, setNotes] = useState<string[]>([]);
  const [sources, setSources] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    fetch("/api/v1/public/econ-calendar")
      .then(r => (r.ok ? r.json() : null))
      .then(d => {
        if (!alive || !d) return;
        setEvents(d.events || []);
        setNotes(d.notes || []);
        setSources(d.sources || {});
      })
      .catch(() => {})
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center py-10">
        <div className="h-7 w-7 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
      </div>
    );
  }

  const failed = Object.entries(sources).filter(([, v]) => v === "error").map(([k]) => k);

  return (
    <div>
      {events.length === 0 ? (
        <p className="py-8 text-center text-sm text-text-muted">
          {isRu ? "Событий в окне нет." : "No events in the window."}
        </p>
      ) : (
        <div className="space-y-2">
          {events.map((e, i) => (
            <div
              key={`${e.date}-${i}`}
              className={`rounded-lg border border-border border-l-2 bg-surface p-3 ${IMPORTANCE[e.importance] || IMPORTANCE.low}`}
            >
              <div className="flex flex-wrap items-baseline gap-2">
                <span className="text-xs font-medium text-text-muted">{e.date}</span>
                <span>{FLAG[e.country] || e.country}</span>
                <span className="text-sm text-text-primary">{e.title}</span>
              </div>
              <a
                href={e.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-text-muted underline decoration-dotted hover:text-brand-500"
              >
                {e.source}
              </a>
            </div>
          ))}
        </div>
      )}

      {/* Gaps are stated, not hidden: a missing source is not an empty calendar. */}
      {notes.map((n, i) => (
        <p key={i} className="mt-3 rounded-lg border border-yellow-500/20 bg-yellow-500/5 px-3 py-2 text-xs text-yellow-400/80">
          {n}
        </p>
      ))}
      {failed.length > 0 && (
        <p className="mt-2 text-xs text-red-400/80">
          {isRu ? "Источники не ответили: " : "Sources failed: "}{failed.join(", ")}
        </p>
      )}
      <p className="mt-3 text-xs text-text-muted">
        {isRu
          ? "Данные первоисточников: Банк России, MOEX ISS, FRED. Сторонние агрегаторы не используются."
          : "Primary sources: Bank of Russia, MOEX ISS, FRED. No third-party aggregators."}
      </p>
    </div>
  );
}
