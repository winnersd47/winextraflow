"use client";

import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  CartesianGrid,
} from "recharts";
import { useTheme } from "@/lib/theme";

interface EquityPoint {
  value: number;
  date?: string;
  trade?: number;
}

interface EquityChartProps {
  data: EquityPoint[] | number[];
  initialCapital: number;
}

export function EquityChart({ data, initialCapital }: EquityChartProps) {
  const { theme } = useTheme();
  const isDark = theme === "dark";

  // Support both old format (number[]) and new format ({value, date, trade}[])
  const chartData = data.map((item, index) => {
    if (typeof item === "number") {
      return { index, value: item, date: String(index), trade: index };
    }
    return { index, value: item.value, date: item.date || String(index), trade: item.trade ?? index };
  });

  // Show every Nth date label to avoid overlap
  const step = Math.max(1, Math.floor(chartData.length / 15));

  return (
    <ResponsiveContainer width="100%" height={280}>
      <AreaChart data={chartData} margin={{ top: 5, right: 10, bottom: 5, left: 10 }}>
        <defs>
          <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#14b8a6" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#14b8a6" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid
          strokeDasharray="3 3"
          stroke={isDark ? "#1f2937" : "#f3f4f6"}
          vertical={false}
        />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 10, fill: isDark ? "#6b7280" : "#9ca3af" }}
          axisLine={{ stroke: isDark ? "#374151" : "#e5e7eb" }}
          tickLine={false}
          interval={step - 1}
          angle={-30}
          textAnchor="end"
          height={40}
        />
        <YAxis
          tick={{ fontSize: 11, fill: isDark ? "#6b7280" : "#9ca3af" }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => v >= 1000 ? `$${(v / 1000).toFixed(0)}k` : `$${v}`}
          width={55}
        />
        <Tooltip
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const d = payload[0].payload;
            const val = d.value as number;
            const pct = ((val - initialCapital) / initialCapital * 100).toFixed(1);
            // Calculate trading day from first date
            const firstDate = chartData[0]?.date;
            const uniqueDates: string[] = [];
            for (const pt of chartData) {
              if (pt.index <= d.index && !uniqueDates.includes(pt.date)) uniqueDates.push(pt.date);
            }
            const tradingDay = uniqueDates.length;
            return (
              <div style={{
                backgroundColor: isDark ? "#1a1d27" : "#ffffff",
                border: `1px solid ${isDark ? "#374151" : "#e5e7eb"}`,
                borderRadius: 8, padding: "8px 12px", fontSize: 12,
                color: isDark ? "#f3f4f6" : "#111827",
              }}>
                <p style={{ fontWeight: 700, marginBottom: 4 }}>{d.date}</p>
                <p>Капитал: <span style={{ color: "#14b8a6", fontWeight: 700 }}>${val.toLocaleString("en-US", { maximumFractionDigits: 0 })}</span> ({Number(pct) >= 0 ? "+" : ""}{pct}%)</p>
                <p style={{ opacity: 0.7 }}>Сделка #{d.trade} | День {tradingDay}</p>
              </div>
            );
          }}
        />
        <ReferenceLine
          y={initialCapital}
          stroke={isDark ? "#6b7280" : "#9ca3af"}
          strokeDasharray="3 3"
          label={{ value: `$${(initialCapital/1000).toFixed(0)}k`, position: "left", fill: isDark ? "#6b7280" : "#9ca3af", fontSize: 10 }}
        />
        <Area
          type="monotone"
          dataKey="value"
          stroke="#14b8a6"
          strokeWidth={2}
          fill="url(#equityGradient)"
          dot={false}
          activeDot={{ r: 4, fill: "#14b8a6" }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
