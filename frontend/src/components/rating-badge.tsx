import { cn, formatConfidence, confidenceColor, confidenceBg } from "@/lib/utils";

export function RatingBadge({
  confidence,
  size = "sm",
}: {
  confidence: number | null;
  size?: "sm" | "lg";
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full font-medium",
        confidenceColor(confidence),
        confidenceBg(confidence),
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-3 py-1 text-sm"
      )}
    >
      WEF {formatConfidence(confidence)}
    </span>
  );
}
