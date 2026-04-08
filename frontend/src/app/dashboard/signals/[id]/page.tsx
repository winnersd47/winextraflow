"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { RatingBadge } from "@/components/rating-badge";
import {
  actionColor,
  formatPrice,
  formatPercent,
  formatConfidence,
  confidenceColor,
  statusLabel,
  timeAgo,
} from "@/lib/utils";
import type { Signal, RatingDetail } from "@/types";

export default function SignalDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [signal, setSignal] = useState<Signal | null>(null);
  const [rating, setRating] = useState<RatingDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [s, r] = await Promise.all([
          api.getSignal(id),
          api.getSignalRating(id),
        ]);
        setSignal(s);
        setRating(r);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
      </div>
    );
  }

  if (!signal) {
    return (
      <div className="py-20 text-center text-gray-400">Signal not found</div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl">
      <button
        onClick={() => router.back()}
        className="mb-4 text-sm text-gray-400 hover:text-white"
      >
        &larr; Back
      </button>

      {/* Signal Header */}
      <div className="rounded-xl border border-gray-800 bg-surface-card p-6">
        <div className="flex items-center gap-3">
          <h1 className="text-3xl font-bold text-white">{signal.ticker}</h1>
          <span
            className={`rounded px-3 py-1 text-sm font-bold uppercase ${actionColor(signal.action)} ${
              signal.action === "buy" ? "bg-green-500/10" : "bg-red-500/10"
            }`}
          >
            {signal.action}
          </span>
          <RatingBadge confidence={signal.ai_confidence} size="lg" />
          <span className="ml-auto text-sm text-gray-500">
            {timeAgo(signal.created_at)}
          </span>
        </div>

        {signal.ai_reasoning && (
          <p className="mt-2 text-sm text-gray-400">{signal.ai_reasoning}</p>
        )}

        <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Stat label="Entry" value={formatPrice(signal.entry_price)} />
          <Stat
            label="Take Profit"
            value={signal.take_profit ? formatPrice(signal.take_profit) : "—"}
            color="text-green-400"
          />
          <Stat
            label="Stop Loss"
            value={signal.stop_loss ? formatPrice(signal.stop_loss) : "—"}
            color="text-red-400"
          />
          <Stat label="Status" value={statusLabel(signal.status)} />
        </div>

        {signal.profit_pct !== null && (
          <div className="mt-4 rounded-lg bg-surface p-4">
            <div className="flex items-center justify-between">
              <span className="text-gray-400">Result</span>
              <span
                className={`text-2xl font-bold ${
                  signal.profit_pct >= 0 ? "text-green-400" : "text-red-400"
                }`}
              >
                {formatPercent(signal.profit_pct)}
              </span>
            </div>
            {signal.close_price && (
              <p className="mt-1 text-sm text-gray-500">
                Closed at {formatPrice(signal.close_price)}
              </p>
            )}
          </div>
        )}
      </div>

      {/* AI Rating Breakdown */}
      {rating && (
        <div className="mt-6 rounded-xl border border-gray-800 bg-surface-card p-6">
          <h2 className="mb-4 text-lg font-bold text-white">
            AI Rating Breakdown
          </h2>
          <div className="mb-4 flex items-center gap-3">
            <span className="text-3xl font-bold text-white">
              {formatConfidence(rating.final_confidence)}
            </span>
            <span className={`text-sm ${confidenceColor(rating.final_confidence)}`}>
              confidence score
            </span>
          </div>
          <p className="mb-6 text-sm text-gray-400">{rating.reasoning}</p>

          <div className="space-y-3">
            {Object.entries(rating.factors).map(([key, factor]) => (
              <div key={key} className="rounded-lg bg-surface p-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium capitalize text-white">
                    {key.replace(/_/g, " ")}
                  </span>
                  <span className="text-sm text-gray-400">
                    weight: {(factor.weight * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-gray-700">
                  <div
                    className="h-full rounded-full bg-brand-500 transition-all"
                    style={{ width: `${factor.score * 100}%` }}
                  />
                </div>
                <p className="mt-1 text-xs text-gray-500">{factor.reason}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  color = "text-white",
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div>
      <span className="text-xs text-gray-500">{label}</span>
      <p className={`text-lg font-semibold ${color}`}>{value}</p>
    </div>
  );
}
