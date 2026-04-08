import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatPrice(price: number): string {
  if (price >= 1000) return price.toLocaleString("en-US", { maximumFractionDigits: 2 });
  if (price >= 1) return price.toFixed(2);
  return price.toFixed(6);
}

export function formatPercent(pct: number | null): string {
  if (pct === null) return "—";
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

export function formatConfidence(confidence: number | null): string {
  if (confidence === null) return "N/A";
  return `${(confidence * 100).toFixed(0)}%`;
}

export function confidenceColor(confidence: number | null): string {
  if (confidence === null) return "text-gray-400";
  if (confidence >= 0.7) return "text-green-400";
  if (confidence >= 0.4) return "text-yellow-400";
  return "text-red-400";
}

export function confidenceBg(confidence: number | null): string {
  if (confidence === null) return "bg-gray-500/20";
  if (confidence >= 0.7) return "bg-green-500/20";
  if (confidence >= 0.4) return "bg-yellow-500/20";
  return "bg-red-500/20";
}

export function actionColor(action: string): string {
  switch (action) {
    case "buy":
      return "text-green-400";
    case "sell":
      return "text-red-400";
    default:
      return "text-gray-400";
  }
}

export function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    active: "Active",
    closed_tp: "TP Hit",
    closed_sl: "SL Hit",
    closed_manual: "Closed",
    expired: "Expired",
  };
  return labels[status] || status;
}

export function timeAgo(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}
