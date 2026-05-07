"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";
import {
  IconWave, IconPlus, IconCompass, IconAnchor, IconShip,
  IconSail, IconHelm, IconBolt, IconNet, IconShield,
  IconPearl, IconRadar, IconDiver,
} from "@/components/sea-icons";

const navItems = [
  { href: "/dashboard", labelKey: "nav.signals", Icon: IconWave },
  { href: "/dashboard/create-signal", labelKey: "nav.createSignal", Icon: IconPlus },
  { href: "/dashboard/leaderboard", labelKey: "nav.leaderboard", Icon: IconCompass },
  { href: "/dashboard/backtest", labelKey: "nav.backtest", Icon: IconAnchor },
  { href: "/dashboard/marketplace", labelKey: "nav.marketplace", Icon: IconShip },
  { href: "/dashboard/telegram", labelKey: "nav.telegram", Icon: IconSail },
  { href: "/dashboard/copy-trading", labelKey: "nav.copyTrading", Icon: IconHelm },
  { href: "/dashboard/execution", labelKey: "nav.execution", Icon: IconBolt },
  { href: "/dashboard/referrals", labelKey: "nav.referrals", Icon: IconNet },
  { href: "/dashboard/kyc", labelKey: "nav.kyc", Icon: IconShield },
  { href: "/dashboard/premium", labelKey: "nav.premium", Icon: IconPearl },
  { href: "/dashboard/capacity", labelKey: "nav.capacity", Icon: IconRadar },
  { href: "/dashboard/profile", labelKey: "nav.profile", Icon: IconDiver },
];

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { t } = useI18n();

  return (
    <>
      <div className="flex h-16 items-center gap-2 border-b border-border px-6">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" className="text-brand-500">
          <path d="M2 12c2-3 4-3 6 0s4 3 6 0 4-3 6 0" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
          <path d="M2 17c2-3 4-3 6 0s4 3 6 0 4-3 6 0" stroke="currentColor" strokeWidth="2" strokeLinecap="round" opacity=".4"/>
          <path d="M2 7c2-3 4-3 6 0s4 3 6 0 4-3 6 0" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity=".2"/>
        </svg>
        <div>
          <span className="text-lg font-bold text-brand-500">WinExtra</span>
          <span className="text-lg font-bold text-text-primary">Flow</span>
        </div>
      </div>
      <nav className="flex-1 space-y-0.5 p-3 sidebar-wave">
        {navItems.map((item) => {
          const isActive = item.href === "/dashboard" ? pathname === "/dashboard" : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition",
                isActive ? "bg-brand-500/15 text-brand-500" : "text-text-secondary hover:bg-surface-hover hover:text-text-primary"
              )}
            >
              <item.Icon size={18} />
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
