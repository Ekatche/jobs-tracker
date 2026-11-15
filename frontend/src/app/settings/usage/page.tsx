"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { usageApi } from "@/lib/api";
import { UserQuotaSummary, ApiUsageRecord, UserTier } from "@/types/usage";
import {
  FiCheckCircle,
  FiAlertCircle,
  FiRefreshCw,
  FiArrowLeft,
} from "react-icons/fi";
import UsageQuotaGauges from "@/components/settings/UsageQuotaGauges";
import UsageTierPlans from "@/components/settings/UsageTierPlans";
import UsageAuditLog from "@/components/settings/UsageAuditLog";

export default function UsageSettingsPage() {
  const [summary, setSummary] = useState<UserQuotaSummary | null>(null);
  const [records, setRecords] = useState<ApiUsageRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [updatingTier, setUpdatingTier] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [sumData, recData] = await Promise.all([
        usageApi.getSummary(),
        usageApi.getRecords(0, 50),
      ]);
      setSummary(sumData);
      setRecords(recData);
    } catch (err: unknown) {
      console.error("Error loading usage settings:", err);
      setError(err instanceof Error ? err.message : "Erreur lors du chargement des quotas.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleTierSwitch = async (tierKey: UserTier) => {
    try {
      setUpdatingTier(tierKey);
      setError(null);
      const updated = await usageApi.updateTier(tierKey);
      setSummary(updated);
      setSuccessMsg(`Plan ${tierKey.toUpperCase()} activé avec succès !`);
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: unknown) {
      console.error("Error updating tier:", err);
      setError(err instanceof Error ? err.message : "Impossible de changer de palier.");
    } finally {
      setUpdatingTier(null);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <FiRefreshCw className="w-8 h-8 animate-spin text-indigo-400" />
          <p className="text-sm text-slate-400">
            Chargement de votre tableau de bord de consommation...
          </p>
        </div>
      </div>
    );
  }

  const currentTier = (summary?.tier || "free").toLowerCase() as UserTier;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-6xl mx-auto space-y-8">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <Link
              href="/profile"
              className="inline-flex items-center gap-2 text-xs font-medium text-slate-400 hover:text-white transition-colors mb-1"
            >
              <FiArrowLeft className="w-3.5 h-3.5" />
              Retour au profil
            </Link>
            <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
              Quotas &amp; Abonnement
            </h1>
            <p className="text-xs sm:text-sm text-slate-400">
              Gérez votre formule, suivez votre consommation mensuelle d&apos;IA et débloquez des
              capacités accrues.
            </p>
          </div>

          <button
            type="button"
            onClick={loadData}
            title="Rafraîchir les compteurs"
            className="self-start sm:self-auto px-3.5 py-2 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-300 text-xs font-semibold flex items-center gap-2 transition-colors shadow-sm"
          >
            <FiRefreshCw className="w-3.5 h-3.5" />
            Actualiser
          </button>
        </div>

        {successMsg && (
          <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs sm:text-sm text-emerald-300 flex items-center gap-2.5">
            <FiCheckCircle className="w-5 h-5 text-emerald-400 shrink-0" />
            <span>{successMsg}</span>
          </div>
        )}

        {error && (
          <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs sm:text-sm text-rose-300 flex items-center gap-2.5">
            <FiAlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="bg-gradient-to-br from-slate-900 via-indigo-950/30 to-slate-900 border border-slate-800/90 rounded-2xl p-6 sm:p-8 shadow-2xl backdrop-blur-sm">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div className="space-y-2">
              <div className="flex items-center gap-2.5">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Formule Active :
                </span>
                <span
                  className={`px-3 py-1 rounded-full text-xs font-extrabold uppercase tracking-wide border ${
                    currentTier === "pro"
                      ? "bg-purple-500/20 text-purple-300 border-purple-500/40 shadow-sm shadow-purple-500/20"
                      : currentTier === "advanced"
                      ? "bg-indigo-500/20 text-indigo-300 border-indigo-500/40 shadow-sm shadow-indigo-500/20"
                      : "bg-slate-800 text-slate-300 border-slate-700"
                  }`}
                >
                  Plan {currentTier}
                </span>
              </div>
              <h2 className="text-xl sm:text-2xl font-bold text-white">
                Cycle mensuel en cours ({summary?.month}/{summary?.year})
              </h2>
              <p className="text-xs text-slate-400 max-w-xl leading-relaxed">
                Vos quotas mensuels sont automatiquement réinitialisés le 1er jour de chaque mois UTC.
              </p>
            </div>

            <div className="flex items-center gap-6 border-t md:border-t-0 md:border-l border-slate-800 pt-4 md:pt-0 md:pl-8">
              <div>
                <span className="text-xs text-slate-500 font-medium block">Tokens consommés</span>
                <span className="text-lg sm:text-xl font-extrabold text-white">
                  {(summary?.total_tokens ?? summary?.total_tokens_month ?? 0).toLocaleString()}
                </span>
              </div>
              <div>
                <span className="text-xs text-slate-500 font-medium block">Coût LLM estimé</span>
                <span className="text-lg sm:text-xl font-extrabold text-indigo-400">
                  ${(summary?.total_cost_usd ?? summary?.total_estimated_cost_usd ?? 0).toFixed(4)}
                </span>
              </div>
            </div>
          </div>
        </div>

        <UsageQuotaGauges summary={summary} />
        <UsageTierPlans
          currentTier={currentTier}
          updatingTier={updatingTier}
          onSelectTier={handleTierSwitch}
        />
        <UsageAuditLog
          records={records}
          currentPage={currentPage}
          onPageChange={setCurrentPage}
        />
      </div>
    </div>
  );
}
