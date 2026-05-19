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
          contentStyle={{
            backgroundColor: isDark ? "#1a1d27" : "#ffffff",
            border: `1px solid ${isDark ? "#374151" : "#e5e7eb"}`,
            borderRadius: "8px",
            color: isDark ? "#f3f4f6" : "#111827",
            fontSize: 13,
          }}
          formatter={(value: number) => {
            const pct = ((value - initialCapital) / initialCapital * 100).toFixed(1);
            return [`$${value.toLocaleString("en-US", { maximumFractionDigits: 0 })} (${Number(pct) >= 0 ? "+" : ""}${pct}%)`, "Капитал"];
          }}
          labelFormatter={(date) => `${date}`}
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
