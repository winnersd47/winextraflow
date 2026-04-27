"use client";

import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
} from "recharts";
import { useTheme } from "@/lib/theme";

interface EquityChartProps {
  data: number[];
  initialCapital: number;
}

export function EquityChart({ data, initialCapital }: EquityChartProps) {
  const { theme } = useTheme();
  const isDark = theme === "dark";

  const chartData = data.map((value, index) => ({ index, value }));

  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: 10 }}>
        <defs>
          <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis
          dataKey="index"
          tick={{ fontSize: 11, fill: isDark ? "#6b7280" : "#9ca3af" }}
          axisLine={{ stroke: isDark ? "#374151" : "#e5e7eb" }}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 11, fill: isDark ? "#6b7280" : "#9ca3af" }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
          width={50}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: isDark ? "#1a1d27" : "#ffffff",
            border: `1px solid ${isDark ? "#374151" : "#e5e7eb"}`,
            borderRadius: "8px",
            color: isDark ? "#f3f4f6" : "#111827",
            fontSize: 13,
          }}
          formatter={(value: number) => [`$${value.toLocaleString("en-US", { maximumFractionDigits: 0 })}`, "Capital"]}
          labelFormatter={(index) => `Trade #${index}`}
        />
        <ReferenceLine
          y={initialCapital}
          stroke={isDark ? "#6b7280" : "#9ca3af"}
          strokeDasharray="3 3"
          label={{ value: "Start", position: "left", fill: isDark ? "#6b7280" : "#9ca3af", fontSize: 11 }}
        />
        <Area
          type="monotone"
          dataKey="value"
          stroke="#22c55e"
          strokeWidth={2}
          fill="url(#equityGradient)"
          dot={false}
          activeDot={{ r: 4, fill: "#22c55e" }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
