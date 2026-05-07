"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";

const navItems = [
  { href: "/dashboard", labelKey: "nav.signals", icon: "📊" },
  { href: "/dashboard/leaderboard", labelKey: "nav.leaderboard", icon: "🏆" },
  { href: "/dashboard/backtest", labelKey: "nav.backtest", icon: "🧪" },
  { href: "/dashboard/marketplace", labelKey: "nav.marketplace", icon: "🛒" },
  { href: "/dashboard/telegram", labelKey: "nav.telegram", icon: "✈️" },
  { href: "/dashboard/copy-trading", labelKey: "nav.copyTrading", icon: "📋" },
  { href: "/dashboard/execution", labelKey: "nav.execution", icon: "⚡" },
  { href: "/dashboard/referrals", labelKey: "nav.referrals", icon: "🤝" },
  { href: "/dashboard/kyc", labelKey: "nav.kyc", icon: "🪪" },
  { href: "/dashboard/premium", labelKey: "nav.premium", icon: "💎" },
  { href: "/dashboard/capacity", labelKey: "nav.capacity", icon: "📡" },
  { href: "/dashboard/profile", labelKey: "nav.profile", icon: "👤" },
];

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { t } = useI18n();

  return (
    <>
      <div className="flex h-16 items-center gap-2 border-b border-border px-6">
        <span className="text-xl font-bold text-brand-500">WinExtra</span>
        <span className="text-xl font-bold text-text-primary">Flow</span>
      </div>
      <nav className="flex-1 space-y-1 p-3">
        {navItems.map((item) => {
          const isActive = item.href === "/dashboard" ? pathname === "/dashboard" : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition",
                isActive ? "bg-brand-500/10 text-brand-500" : "text-text-secondary hover:bg-surface-hover hover:text-text-primary"
              )}
            >
              <span>{item.icon}</span>
              {t(item.labelKey)}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-border p-4">
        <p className="text-xs text-text-muted">WinExtraFlow v0.1.0</p>
      </div>
    </>
  );
}

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <>
      {/* Mobile overlay */}
      <div className={cn("fixed inset-0 z-40 lg:hidden", open ? "block" : "hidden")}>
        <div className="fixed inset-0 bg-black/50" onClick={onClose} />
        <aside className="fixed left-0 top-0 flex h-full w-60 flex-col bg-surface-card shadow-xl">
          <SidebarContent onNavigate={onClose} />
        </aside>
      </div>

      {/* Desktop sidebar */}
      <aside className="hidden lg:flex w-60 flex-col border-r border-border bg-surface-card">
        <SidebarContent />
      </aside>
    </>
  );
}
