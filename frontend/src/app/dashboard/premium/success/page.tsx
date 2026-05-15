"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export default function PaymentSuccessPage() {
  const searchParams = useSearchParams();
  const sessionId = searchParams.get("session_id");
  const [completed, setCompleted] = useState(false);
  const { t } = useI18n();

  useEffect(() => {
    if (sessionId && sessionId.startsWith("demo_")) {
      // Demo payment — complete via API
      api.completeDemoPayment(sessionId).then(() => setCompleted(true)).catch(() => {});
    } else {
      // Real Stripe — webhook handles it, just show success
      setCompleted(true);
    }
  }, [sessionId]);

  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="text-center">
        <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-green-500/20 text-4xl">
          {completed ? "✅" : "⏳"}
        </div>
        <h1 className="text-2xl font-bold text-text-primary">
          {completed ? t("premium.successTitle") : "Processing..."}
        </h1>
        <p className="mt-2 text-text-secondary">
          {completed ? t("premium.successDesc") : "Please wait..."}
        </p>
        {completed && (
          <Link href="/dashboard" className="mt-6 inline-block rounded-lg bg-brand-600 px-8 py-3 font-medium text-white transition hover:bg-brand-700">
            {t("premium.goToDashboard")}
          </Link>
        )}
      </div>
    </div>
  );
}
