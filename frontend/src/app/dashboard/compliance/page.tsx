"use client";

import { useEffect, useState, useRef } from "react";
import { useI18n } from "@/lib/i18n";

interface ComplianceItem {
  id: string;
  doc_type: string;
  title: string;
  description: string;
  category: string;
  status: string;
  is_required: boolean;
  file_name: string | null;
  admin_note: string | null;
  warning: string;
  updated_at: string | null;
}

interface ComplianceData {
  total_required: number;
  total_completed: number;
  compliance_pct: number;
  critical_warnings: { doc_type: string; title: string; warning: string }[];
  items: ComplianceItem[];
}

const CATEGORY_LABELS: Record<string, { ru: string; en: string }> = {
  business: { ru: "Регистрация бизнеса", en: "Business Registration" },
  licenses: { ru: "Лицензии и разрешения", en: "Licenses & Permits" },
  data_protection: { ru: "Защита персональных данных", en: "Data Protection" },
  aml: { ru: "AML / KYC", en: "AML / KYC" },
  user_docs: { ru: "Пользовательские документы", en: "User Documents" },
  financial: { ru: "Финансовые гарантии", en: "Financial Guarantees" },
};

const STATUS_LABELS: Record<string, { ru: string; en: string; color: string }> = {
  not_started: { ru: "Не начато", en: "Not Started", color: "bg-red-500/20 text-red-400" },
  in_progress: { ru: "В процессе", en: "In Progress", color: "bg-yellow-500/20 text-yellow-400" },
  uploaded: { ru: "Загружено", en: "Uploaded", color: "bg-blue-500/20 text-blue-400" },
  verified: { ru: "Подтверждено", en: "Verified", color: "bg-green-500/20 text-green-400" },
  expired: { ru: "Истекло", en: "Expired", color: "bg-red-500/20 text-red-400" },
  not_required: { ru: "Не требуется", en: "Not Required", color: "bg-gray-500/20 text-gray-400" },
};

export default function CompliancePage() {
  const [data, setData] = useState<ComplianceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState<string | null>(null);
  const [expandedWarnings, setExpandedWarnings] = useState(true);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadTarget, setUploadTarget] = useState<string | null>(null);
  const { locale } = useI18n();
  const isRu = locale === "ru";

  const load = async () => {
    try {
      const token = localStorage.getItem("token");
      const resp = await fetch("/api/v1/compliance/status", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) throw new Error("Access denied");
      setData(await resp.json());
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleUpload = async (docType: string, file: File) => {
    setUploading(docType);
    try {
      const token = localStorage.getItem("token");
      const form = new FormData();
      form.append("file", file);
      const resp = await fetch(`/api/v1/compliance/${docType}/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      if (!resp.ok) {
        const err = await resp.json();
        alert(err.detail || "Upload failed");
      }
      await load();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setUploading(null);
    }
  };

  const handleStatusChange = async (docType: string, status: string) => {
    const token = localStorage.getItem("token");
    await fetch(`/api/v1/compliance/${docType}/status?status=${status}`, {
      method: "PATCH",
      headers: { Authorization: `Bearer ${token}` },
    });
    await load();
  };

  const triggerUpload = (docType: string) => {
    setUploadTarget(docType);
    fileInputRef.current?.click();
  };

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && uploadTarget) {
      handleUpload(uploadTarget, file);
    }
    e.target.value = "";
  };

  if (loading) return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>;
  if (error) return <div className="mx-auto max-w-4xl rounded-xl bg-red-500/10 p-6 text-red-400">{error}</div>;
  if (!data) return null;

  const grouped = data.items.reduce<Record<string, ComplianceItem[]>>((acc, item) => {
    (acc[item.category] = acc[item.category] || []).push(item);
    return acc;
  }, {});

  return (
    <div className="mx-auto max-w-5xl">
      <input ref={fileInputRef} type="file" className="hidden" onChange={onFileChange}
        accept=".pdf,.jpg,.jpeg,.png,.doc,.docx" />

      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-text-primary">
          {isRu ? "Юридическое соответствие" : "Legal Compliance"}
        </h1>
        <p className="text-sm text-text-secondary">
          {isRu
            ? "Контрольный список документов и разрешений для коммерческой эксплуатации (законодательство РФ)"
            : "Checklist of documents and permits for commercial operation (Russian law)"}
        </p>
      </div>

      {/* Progress bar */}
      <div className="mb-6 rounded-xl border border-border bg-surface-card p-5">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-sm font-medium text-text-primary">
            {isRu ? "Общий прогресс" : "Overall Progress"}
          </span>
          <span className={`text-lg font-bold ${data.compliance_pct >= 80 ? "text-green-400" : data.compliance_pct >= 40 ? "text-yellow-400" : "text-red-400"}`}>
            {data.compliance_pct}% ({data.total_completed}/{data.total_required})
          </span>
        </div>
        <div className="h-3 overflow-hidden rounded-full bg-surface">
          <div
            className={`h-full rounded-full transition-all ${data.compliance_pct >= 80 ? "bg-green-500" : data.compliance_pct >= 40 ? "bg-yellow-500" : "bg-red-500"}`}
            style={{ width: `${data.compliance_pct}%` }}
          />
        </div>
      </div>

      {/* Critical Warnings */}
      {data.critical_warnings.length > 0 && (
        <div className="mb-6 rounded-xl border-2 border-red-500/50 bg-red-500/5 p-5">
          <button
            onClick={() => setExpandedWarnings(!expandedWarnings)}
            className="flex w-full items-center justify-between"
          >
            <h2 className="text-lg font-bold text-red-400">
              {isRu
                ? `КРИТИЧЕСКИЕ ПРЕДУПРЕЖДЕНИЯ (${data.critical_warnings.length})`
                : `CRITICAL WARNINGS (${data.critical_warnings.length})`}
            </h2>
            <span className="text-red-400">{expandedWarnings ? "—" : "+"}</span>
          </button>
          {expandedWarnings && (
            <div className="mt-4 space-y-3">
              {data.critical_warnings.map((w) => (
                <div key={w.doc_type} className="rounded-lg border border-red-500/30 bg-red-500/10 p-4">
                  <p className="mb-1 text-sm font-bold text-red-300">{w.title}</p>
                  <p className="text-xs text-red-300/80">{w.warning}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Checklist by category */}
      {Object.entries(grouped).map(([category, items]) => (
        <div key={category} className="mb-6">
          <h2 className="mb-3 text-lg font-bold text-text-primary">
            {isRu ? CATEGORY_LABELS[category]?.ru : CATEGORY_LABELS[category]?.en || category}
          </h2>
          <div className="space-y-2">
            {items.map((item) => {
              const st = STATUS_LABELS[item.status] || STATUS_LABELS.not_started;
              return (
                <div key={item.id} className="rounded-xl border border-border bg-surface-card p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="mb-1 flex items-center gap-2">
                        <span className={`rounded px-2 py-0.5 text-xs font-bold ${st.color}`}>
                          {isRu ? st.ru : st.en}
                        </span>
                        {item.is_required && (
                          <span className="rounded bg-red-500/10 px-2 py-0.5 text-xs text-red-400">
                            {isRu ? "ОБЯЗАТЕЛЬНО" : "REQUIRED"}
                          </span>
                        )}
                        <h3 className="text-sm font-medium text-text-primary">{item.title}</h3>
                      </div>
                      <p className="mb-2 text-xs text-text-secondary">{item.description}</p>
                      {item.warning && item.status === "not_started" && item.is_required && (
                        <p className="text-xs text-red-400/80">{item.warning}</p>
                      )}
                      {item.file_name && (
                        <p className="mt-1 text-xs text-brand-400">
                          {isRu ? "Файл:" : "File:"} {item.file_name}
                        </p>
                      )}
                      {item.admin_note && (
                        <p className="mt-1 text-xs text-text-muted">
                          {isRu ? "Заметка:" : "Note:"} {item.admin_note}
                        </p>
                      )}
                    </div>
                    <div className="flex flex-col gap-1">
                      <button
                        onClick={() => triggerUpload(item.doc_type)}
                        disabled={uploading === item.doc_type}
                        className="rounded-lg bg-brand-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-700 disabled:opacity-50"
                      >
                        {uploading === item.doc_type
                          ? "..."
                          : isRu ? "Загрузить" : "Upload"}
                      </button>
                      {item.status !== "verified" && item.status !== "not_required" && (
                        <button
                          onClick={() => handleStatusChange(item.doc_type, "verified")}
                          className="rounded-lg bg-green-600/20 px-3 py-1.5 text-xs font-medium text-green-400 hover:bg-green-600/30"
                        >
                          {isRu ? "Подтвердить" : "Verify"}
                        </button>
                      )}
                      {!item.is_required && item.status !== "not_required" && (
                        <button
                          onClick={() => handleStatusChange(item.doc_type, "not_required")}
                          className="rounded-lg bg-gray-600/20 px-3 py-1.5 text-xs font-medium text-gray-400 hover:bg-gray-600/30"
                        >
                          {isRu ? "Не нужно" : "N/A"}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ))}

      {/* Footer disclaimer */}
      <div className="mb-8 rounded-xl border border-border bg-surface-card p-5 text-xs text-text-muted">
        {isRu ? (
          <p>
            Данный контрольный список составлен на основе законодательства Российской Федерации.
            Он НЕ является юридической консультацией. Для получения квалифицированной помощи обратитесь
            к лицензированному юристу, специализирующемуся на финансовом праве и IT-праве.
            Законодательство может меняться — регулярно проверяйте актуальность требований.
          </p>
        ) : (
          <p>
            This checklist is based on the legislation of the Russian Federation.
            It is NOT legal advice. Consult a licensed lawyer specializing in financial
            and IT law for qualified assistance. Legislation may change — regularly check
            the relevance of requirements.
          </p>
        )}
      </div>
    </div>
  );
}
