"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Sidebar } from "@/components/sidebar";
import { Header } from "@/components/header";
import { ErrorBoundary } from "@/components/error-boundary";
import { CapacityWarning } from "@/components/capacity-warning";
import { Disclaimer } from "@/components/disclaimer";
import { ComplianceGate } from "@/components/compliance-gate";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [user, loading, router]);

  if (loading) return <div className="flex h-screen items-center justify-center"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>;
  if (!user) return null;

  return (
    <div className="flex h-screen">
      <CapacityWarning />
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header onMenuClick={() => setSidebarOpen(true)} />
        <main className="flex-1 overflow-y-auto p-4 lg:p-6">
          <ErrorBoundary>
            <ComplianceGate path={pathname}>
              {children}
            </ComplianceGate>
          </ErrorBoundary>
          <Disclaimer />
        </main>
      </div>
    </div>
  );
}
