"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/dashboard", label: "Signals", icon: "📊" },
  { href: "/dashboard/leaderboard", label: "Leaderboard", icon: "🏆" },
  { href: "/dashboard/backtest", label: "Backtest", icon: "🧪" },
  { href: "/dashboard/marketplace", label: "Marketplace", icon: "🛒" },
  { href: "/dashboard/copy-trading", label: "Copy Trading", icon: "📋" },
  { href: "/dashboard/execution", label: "Execution", icon: "⚡" },
  { href: "/dashboard/referrals", label: "Referrals", icon: "🤝" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex w-60 flex-col border-r border-gray-800 bg-surface-card">
      <div className="flex h-16 items-center gap-2 border-b border-gray-800 px-6">
        <span className="text-xl font-bold text-brand-500">WinExtra</span>
        <span className="text-xl font-bold text-white">Flow</span>
      </div>

      <nav className="flex-1 space-y-1 p-3">
        {navItems.map((item) => {
          const isActive =
            item.href === "/dashboard"
              ? pathname === "/dashboard"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition",
                isActive
                  ? "bg-brand-500/10 text-brand-500"
                  : "text-gray-400 hover:bg-surface-hover hover:text-white"
              )}
            >
              <span>{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-gray-800 p-4">
        <p className="text-xs text-gray-500">WinExtraFlow v0.1.0</p>
      </div>
    </aside>
  );
}
