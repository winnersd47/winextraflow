"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";
import { useAuth } from "@/lib/auth";
import { useCompliance, isFeatureAccessible } from "@/components/compliance-gate";
import {
  IconWave, IconPlus, IconCompass, IconAnchor, IconShip,
  IconSail, IconHelm, IconBolt, IconNet, IconShield,
  IconPearl, IconRadar, IconDiver,
} from "@/components/sea-icons";

const navItems = [
  { href: "/dashboard", labelKey: "nav.signals", Icon: IconWave, adminOnly: false },
  { href: "/dashboard/create-signal", labelKey: "nav.createSignal", Icon: IconPlus, adminOnly: false },
  { href: "/dashboard/leaderboard", labelKey: "nav.leaderboard", Icon: IconCompass, adminOnly: false },
  { href: "/dashboard/backtest", labelKey: "nav.backtest", Icon: IconAnchor, adminOnly: false },
  { href: "/dashboard/marketplace", labelKey: "nav.marketplace", Icon: IconShip, adminOnly: false },
  { href: "/dashboard/telegram", labelKey: "nav.telegram", Icon: IconSail, adminOnly: false },
  { href: "/dashboard/copy-trading", labelKey: "nav.copyTrading", Icon: IconHelm, adminOnly: false },
  { href: "/dashboard/execution", labelKey: "nav.execution", Icon: IconBolt, adminOnly: false },
  { href: "/dashboard/referrals", labelKey: "nav.referrals", Icon: IconNet, adminOnly: false },
  { href: "/dashboard/kyc", labelKey: "nav.kyc", Icon: IconShield, adminOnly: false },
  { href: "/dashboard/premium", labelKey: "nav.premium", Icon: IconPearl, adminOnly: false },
  { href: "/dashboard/capacity", labelKey: "nav.capacity", Icon: IconRadar, adminOnly: true },
  { href: "/dashboard/compliance", labelKey: "nav.compliance", Icon: IconShield, adminOnly: true },
  { href: "/dashboard/profile", labelKey: "nav.profile", Icon: IconDiver, adminOnly: false },
];

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { t } = useI18n();
  const { user } = useAuth();
  const compliance = useCompliance();
  const isAdmin = user?.role === "admin";

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
          // Admin-only items (capacity, compliance) hidden for regular users
          if (item.adminOnly && !isAdmin) return null;

          // Check if feature is accessible based on compliance level
          const accessible = compliance.loaded
            ? isFeatureAccessible(item.href, compliance.pct)
            : true;

          // Hide inaccessible commercial features from non-admin users completely
          if (!accessible && !isAdmin) return null;

          const isActive = item.href === "/dashboard" ? pathname === "/dashboard" : pathname.startsWith(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition",
                isActive
                  ? "bg-brand-500/15 text-brand-500"
                  : !accessible
                    ? "text-text-muted/40 cursor-not-allowed"
                    : "text-text-secondary hover:bg-surface-hover hover:text-text-primary"
              )}
            >
              <item.Icon size={18} />
              <span className="flex-1">{t(item.labelKey)}</span>
              {/* Lock icon for admin on inaccessible features */}
              {!accessible && isAdmin && (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-red-400/60">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                  <path d="M7 11V7a5 5 0 0110 0v4"/>
                </svg>
              )}
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
