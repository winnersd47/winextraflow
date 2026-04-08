"use client";

import Link from "next/link";
import type { Signal } from "@/types";
import { RatingBadge } from "./rating-badge";
import {
  actionColor,
  formatPrice,
  formatPercent,
  statusLabel,
  timeAgo,
} from "@/lib/utils";

export function SignalCard({ signal }: { signal: Signal }) {
  const isActive = signal.status === "active";
  const isProfitable = signal.profit_pct !== null && signal.profit_pct > 0;

  return (
    <Link
      href={`/dashboard/signals/${signal.id}`}
      className="block rounded-xl border border-gray-800 bg-surface-card p-4 transition hover:border-gray-700 hover:bg-surface-hover"
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <span className="text-lg font-bold text-white">{signal.ticker}</span>
          <span
            className={`rounded px-2 py-0.5 text-xs font-bold uppercase ${actionColor(signal.action)} ${
              signal.action === "buy" ? "bg-green-500/10" : "bg-red-500/10"
            }`}
          >
            {signal.action}
          </span>
          <RatingBadge confidence={signal.ai_confidence} />
        </div>
        <span className="text-xs text-gray-500">{timeAgo(signal.created_at)}</span>
      </div>

      <div className="mt-3 grid grid-cols-4 gap-3 text-sm">
        <div>
          <span className="text-gray-500">Entry</span>
          <p className="font-medium text-white">{formatPrice(signal.entry_price)}</p>
        </div>
        <div>
          <span className="text-gray-500">TP</span>
          <p className="font-medium text-green-400">
            {signal.take_profit ? formatPrice(signal.take_profit) : "—"}
          </p>
        </div>
        <div>
          <span className="text-gray-500">SL</span>
          <p className="font-medium text-red-400">
            {signal.stop_loss ? formatPrice(signal.stop_loss) : "—"}
          </p>
        </div>
        <div>
          <span className="text-gray-500">Status</span>
          <p
            className={`font-medium ${
              isActive
                ? "text-blue-400"
                : isProfitable
                  ? "text-green-400"
                  : "text-red-400"
            }`}
          >
            {isActive ? statusLabel(signal.status) : formatPercent(signal.profit_pct)}
          </p>
        </div>
      </div>
    </Link>
  );
}
