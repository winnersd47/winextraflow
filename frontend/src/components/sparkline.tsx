"use client";

/**
 * Sparkline — tiny inline SVG chart for cards and tables.
 * Shows trend at a glance without labels or axes.
 */

interface Props {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
  fillOpacity?: number;
  strokeWidth?: number;
}

export function Sparkline({
  data,
  width = 80,
  height = 24,
  color = "#10b981",
  fillOpacity = 0.1,
  strokeWidth = 1.5,
}: Props) {
  if (!data || data.length < 2) return null;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((v - min) / range) * (height - 4) - 2;
    return `${x},${y}`;
  });

  const polyline = points.join(" ");
  const fillPoints = `0,${height} ${polyline} ${width},${height}`;

  // Determine color: green if last > first, red if last < first
  const trend = data[data.length - 1] >= data[0];
  const autoColor = color || (trend ? "#10b981" : "#ef4444");

  return (
    <svg width={width} height={height} className="sparkline" viewBox={`0 0 ${width} ${height}`}>
      <polygon points={fillPoints} fill={autoColor} fillOpacity={fillOpacity} />
      <polyline
        points={polyline}
        fill="none"
        stroke={autoColor}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Last point dot */}
      <circle
        cx={width}
        cy={height - ((data[data.length - 1] - min) / range) * (height - 4) - 2}
        r={2}
        fill={autoColor}
      />
    </svg>
  );
}

/**
 * SparkBar — tiny bar chart variant.
 */
export function SparkBar({
  data,
  width = 60,
  height = 20,
  color = "#10b981",
}: {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
}) {
  if (!data || data.length < 2) return null;

  const max = Math.max(...data) || 1;
  const barWidth = width / data.length - 1;

  return (
    <svg width={width} height={height} className="sparkline" viewBox={`0 0 ${width} ${height}`}>
      {data.map((v, i) => {
        const barHeight = (v / max) * (height - 2);
        const x = i * (barWidth + 1);
        const isPositive = v >= 0;
        return (
          <rect
            key={i}
            x={x}
            y={height - barHeight - 1}
            width={barWidth}
            height={Math.max(barHeight, 1)}
            fill={isPositive ? color : "#ef4444"}
            rx={1}
            opacity={0.7 + (i / data.length) * 0.3}
          />
        );
      })}
    </svg>
  );
}
