"use client";

import { useEffect, useState } from "react";
import { useI18n } from "@/lib/i18n";

export default function KYCPage() {
  const { t } = useI18n();
  const [status, setStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);

  const load = async () => {
    try {
      const token = localStorage.getItem("token");
      const res = await fetch("/api/v1/kyc/status", { headers: { Authorization: `Bearer ${token}` } });
      setStatus(await res.json());
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (!["image/jpeg", "image/png", "image/jpg"].includes(f.type)) {
      setError(t("kyc.invalidFormat"));
      return;
    }
    if (f.size > 10 * 1024 * 1024) {
      setError(t("kyc.tooLarge"));
      return;
    }
    setFile(f);
    setPreview(URL.createObjectURL(f));
    setError("");
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError("");
    setSuccess("");
    try {
      const token = localStorage.getItem("token");
      const formData = new FormData();
      formData.append("photo", file);
      const res = await fetch("/api/v1/kyc/upload", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      if (res.ok) {
        setSuccess(t("kyc.submitted"));
        setFile(null);
        setPreview(null);
        load();
      } else {
        const data = await res.json();
        setError(data.detail || "Upload failed");
      }
    } catch { setError("Network error"); }
    finally { setUploading(false); }
  };

  if (loading) return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>;

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-2 text-2xl font-bold text-text-primary">{t("kyc.title")}</h1>
      <p className="mb-6 text-sm text-text-secondary">{t("kyc.subtitle")}</p>

      {/* Status Card */}
      <div className={`mb-6 rounded-xl border-2 p-6 ${
        status?.status === "approved" ? "border-green-500/50 bg-green-500/5" :
        status?.status === "pending" ? "border-yellow-500/50 bg-yellow-500/5" :
        status?.status === "rejected" ? "border-red-500/50 bg-red-500/5" :
        "border-border bg-surface-card"
      }`}>
        <div className="flex items-center gap-3">
          <span className="text-3xl">
            {status?.status === "approved" ? "✅" :
             status?.status === "pending" ? "⏳" :
             status?.status === "rejected" ? "❌" : "🔒"}
          </span>
          <div>
            <h2 className="text-lg font-bold text-text-primary">
              {status?.status === "approved" ? t("kyc.approved") :
               status?.status === "pending" ? t("kyc.pending") :
               status?.status === "rejected" ? t("kyc.rejected") :
               t("kyc.notSubmitted")}
            </h2>
            {status?.admin_comment && (
              <p className="text-sm text-red-400 mt-1">{t("kyc.reason")}: {status.admin_comment}</p>
            )}
          </div>
        </div>
      </div>

      {/* Upload Form — show if not approved and not pending */}
      {status?.status !== "approved" && status?.status !== "pending" && (
        <div className="rounded-xl border border-border bg-surface-card p-6">
          <h3 className="mb-3 font-semibold text-text-primary">{t("kyc.uploadTitle")}</h3>

          {/* Requirements */}
          <div className="mb-4 rounded-lg bg-surface p-4">
            <p className="text-sm font-medium text-text-primary mb-2">{t("kyc.requirements")}</p>
            <ul className="space-y-1 text-sm text-text-secondary">
              <li>1. {t("kyc.req1")}</li>
              <li>2. {t("kyc.req2")}</li>
              <li>3. {t("kyc.req3")}</li>
              <li>4. {t("kyc.req4")}</li>
            </ul>
          </div>

          {error && <div className="mb-4 rounded-lg bg-red-500/10 p-3 text-sm text-red-400">{error}</div>}
          {success && <div className="mb-4 rounded-lg bg-green-500/10 p-3 text-sm text-green-400">{success}</div>}

          {/* File Input */}
          <div className="mb-4">
            <label className="block cursor-pointer rounded-xl border-2 border-dashed border-border p-8 text-center hover:border-brand-500 transition">
              <input type="file" accept="image/jpeg,image/png" onChange={handleFile} className="hidden" />
              {preview ? (
                <img src={preview} alt="Preview" className="mx-auto max-h-64 rounded-lg" />
              ) : (
                <div>
                  <p className="text-3xl mb-2">📸</p>
                  <p className="text-text-primary font-medium">{t("kyc.clickToUpload")}</p>
                  <p className="text-xs text-text-muted mt-1">JPG, PNG. {t("kyc.maxSize")}</p>
                </div>
              )}
            </label>
          </div>

          {file && (
            <button onClick={handleUpload} disabled={uploading} className="w-full rounded-lg bg-brand-600 py-3 font-medium text-white hover:bg-brand-700 disabled:opacity-50">
              {uploading ? "..." : t("kyc.submit")}
            </button>
          )}
        </div>
      )}

      {/* Info about what KYC unlocks */}
      <div className="mt-6 rounded-xl border border-border bg-surface-card p-6">
        <h3 className="mb-3 font-semibold text-text-primary">{t("kyc.whyNeeded")}</h3>
        <ul className="space-y-2 text-sm text-text-secondary">
          <li className="flex items-center gap-2"><span className="text-brand-500">⚡</span> {t("kyc.unlock1")}</li>
          <li className="flex items-center gap-2"><span className="text-brand-500">📋</span> {t("kyc.unlock2")}</li>
          <li className="flex items-center gap-2"><span className="text-brand-500">🛒</span> {t("kyc.unlock3")}</li>
          <li className="flex items-center gap-2"><span className="text-brand-500">🔒</span> {t("kyc.unlock4")}</li>
        </ul>
      </div>
    </div>
  );
}
