"use client";

import { useEffect, useState } from "react";

/**
 * Live scrolling prices, served by our own /api/v1/public/ticker-tape.
 *
 * Replaces the TradingView ticker-tape widget. Their free widget injects an
 * attribution badge that their terms require you to keep visible, and it sat on top
 * of the prices; hiding it with CSS would have breached those terms. The platform
 * already fetches these quotes itself (MOEX ISS, Binance, Yahoo), so the third-party
 * script bought nothing — and it is one less external asset to load on a network
 * where s3.tradingview.com is not reliably reachable.
 *
 * A quote that fails to fetch is omitted rather than shown as zero.
 */

type Item = {
  ticker: string;
  title: string;
  currency: string;
  price: number;
  change_pct: number | null;
  change_window: string | null;
};

const REFRESH_MS = 60_000;

export function TickerTape() {
  const [items, setItems] = useState<Item[]>([]);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const r = await fetch("/api/v1/public/ticker-tape");
        if (!r.ok) return;
        const d = await r.json();
        if (alive) setItems(d.items || []);
      } catch {
        // Keep the previous prices on a failed refresh — a blank tape reads as
        // "market closed", which is a different claim than "fetch failed".
      }
    };
    load();
    const t = setInterval(load, REFRESH_MS);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  if (!items.length) return null;

  // Duplicated once so the marquee can loop without a visible seam.
  const row = [...items, ...items];

  return (
    <div className="w-full overflow-hidden border-b border-border/30 bg-surface/40">
      <div className="flex w-max animate-ticker gap-6 py-1.5">
        {row.map((it, i) => {
          const up = (it.change_pct ?? 0) >= 0;
          return (
            <span key={`${it.ticker}-${i}`} className="flex shrink-0 items-baseline gap-1.5 text-xs">
              <span className="font-medium text-text-secondary">{it.title}</span>
              <span className="font-semibold text-text-primary">
                {it.price.toLocaleString("ru-RU", { maximumFractionDigits: 2 })}
                {it.currency}
              </span>
              {it.change_pct !== null && (
                <span
                  className={up ? "text-green-400" : "text-red-400"}
                  title={
                    it.change_window === "session"
                      ? "с открытия сессии"
                      : it.change_window === "prev_close"
                        ? "к закрытию прошлого дня"
                        : "за 24 часа"
                  }
                >
                  {up ? "+" : ""}
                  {it.change_pct.toFixed(2)}%
                </span>
              )}
            </span>
          );
        })}
      </div>
    </div>
  );
}
