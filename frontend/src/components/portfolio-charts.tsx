"use client";

import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip,
  CartesianGrid, PieChart, Pie, Cell, Legend,
  BarChart, Bar, ReferenceLine,
} from "recharts";
import { useTheme } from "@/lib/theme";

const COLORS = ["#10b981", "#3b82f6", "#8b5cf6", "#f59e0b", "#ef4444", "#06b6d4", "#ec4899", "#f97316"];

interface EquityPoint {
  date: string | null;
  pnl: number;
  ticker: string;
}

interface AllocationEntry {
  name: string;
  value: number;
}

/**
 * Portfolio Equity Curve — Recharts AreaChart replacing div-bars
 */
export function PortfolioEquityChart({ data }: { data: EquityPoint[] }) {
  const { theme } = useTheme();
  const isDark = theme === "dark";

  if (!data || data.length < 2) return null;

  const chartData = data.map((p, i) => ({
    index: i,
    date: p.date ? new Date(p.date).toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" }) : `#${i}`,
    pnl: p.pnl,
    ticker: p.ticker,
  }));

  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={chartData} margin={{ top: 5, right: 10, bottom: 5, left: 10 }}>
        <defs>
          <linearGradient id="pnlGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke={isDark ? "#1e3a5f" : "#f3f4f6"} vertical={false} />
        <XAxis dataKey="date" tick={{ fontSize: 10, fill: isDark ? "#64748b" : "#9ca3af" }} tickLine={false} />
        <YAxis tick={{ fontSize: 10, fill: isDark ? "#64748b" : "#9ca3af" }} tickLine={false} axisLine={false} width={50} />
        <Tooltip
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const d = payload[0].payload;
            return (
              <div style={{
                backgroundColor: isDark ? "#0f1d32" : "#fff",
                border: `1px solid ${isDark ? "#1e3a5f" : "#e5e7eb"}`,
                borderRadius: 8, padding: "6px 10px", fontSize: 11,
                color: isDark ? "#e2e8f0" : "#111",
              }}>
                <p style={{ fontWeight: 700 }}>{d.ticker} — {d.date}</p>
                <p>P&L: <span style={{ color: d.pnl >= 0 ? "#10b981" : "#ef4444", fontWeight: 700 }}>
                  {d.pnl >= 0 ? "+" : ""}{d.pnl.toFixed(0)}
                </span></p>
              </div>
            );
          }}
        />
        <ReferenceLine y={0} stroke={isDark ? "#64748b" : "#9ca3af"} strokeDasharray="3 3" />
        <Area type="monotone" dataKey="pnl" stroke="#10b981" strokeWidth={2} fill="url(#pnlGradient)" dot={false} activeDot={{ r: 3 }} />
      </AreaChart>
    </ResponsiveContainer>
  );
}


/**
 * Portfolio Allocation Pie Chart
 */
export function AllocationPieChart({ data }: { data: Record<string, number> }) {
  const { theme } = useTheme();
  const isDark = theme === "dark";

  const entries = Object.entries(data).map(([name, value]) => ({ name, value }));
  if (entries.length === 0) return null;

  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie
          data={entries}
          cx="50%"
          cy="50%"
          innerRadius={50}
          outerRadius={80}
          dataKey="value"
          stroke={isDark ? "#0f1d32" : "#fff"}
          strokeWidth={2}
          label={({ name, value }) => `${name} ${value}%`}
          labelLine={{ stroke: isDark ? "#64748b" : "#9ca3af" }}
        >
          {entries.map((_, i) => (
            <Cell key={i} fill={COLORS[i % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const d = payload[0];
            return (
              <div style={{
                backgroundColor: isDark ? "#0f1d32" : "#fff",
                border: `1px solid ${isDark ? "#1e3a5f" : "#e5e7eb"}`,
                borderRadius: 8, padding: "6px 10px", fontSize: 12,
                color: isDark ? "#e2e8f0" : "#111",
              }}>
                <p style={{ fontWeight: 700 }}>{d.name}: {d.value}%</p>
              </div>
            );
          }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}


/**
 * Monthly P&L Bar Chart (for backtest results)
 */
export function MonthlyPnlChart({ data }: { data: { month: string; pnl_pct: number; trades: number }[] }) {
  const { theme } = useTheme();
  const isDark = theme === "dark";

  if (!data || data.length === 0) return null;

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 5, right: 10, bottom: 5, left: 10 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={isDark ? "#1e3a5f" : "#f3f4f6"} vertical={false} />
        <XAxis dataKey="month" tick={{ fontSize: 10, fill: isDark ? "#64748b" : "#9ca3af" }} tickLine={false} />
        <YAxis tick={{ fontSize: 10, fill: isDark ? "#64748b" : "#9ca3af" }} tickLine={false} axisLine={false} width={40} />
        <Tooltip
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const d = payload[0].payload;
            return (
              <div style={{
                backgroundColor: isDark ? "#0f1d32" : "#fff",
                border: `1px solid ${isDark ? "#1e3a5f" : "#e5e7eb"}`,
                borderRadius: 8, padding: "6px 10px", fontSize: 11,
                color: isDark ? "#e2e8f0" : "#111",
              }}>
                <p style={{ fontWeight: 700 }}>{d.month}</p>
                <p>P&L: <span style={{ color: d.pnl_pct >= 0 ? "#10b981" : "#ef4444", fontWeight: 700 }}>{d.pnl_pct >= 0 ? "+" : ""}{d.pnl_pct}%</span></p>
                <p style={{ opacity: 0.7 }}>{d.trades} trades | WR {(d.win_rate * 100).toFixed(0)}%</p>
              </div>
            );
          }}
        />
        <ReferenceLine y={0} stroke={isDark ? "#64748b" : "#9ca3af"} />
        <Bar dataKey="pnl_pct" radius={[4, 4, 0, 0]}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.pnl_pct >= 0 ? "#10b981" : "#ef4444"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
