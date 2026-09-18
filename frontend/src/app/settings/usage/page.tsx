"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { usageApi } from "@/lib/api";
import {
  UserQuotaSummary,
  ApiUsageRecord,
  TierPricingInfo,
  UserTier,
  ActionQuotaUsage,
} from "@/types/usage";
import {
  FiZap,
  FiFileText,
  FiMail,
  FiAward,
  FiCpu,
  FiLayers,
  FiCheckCircle,
  FiAlertCircle,
  FiRefreshCw,
  FiArrowLeft,
  FiTrendingUp,
  FiDollarSign,
  FiClock,
  FiShield,
  FiCheck,
} from "react-icons/fi";

const ACTION_CONFIG: Record<
  string,
  { label: string; icon: React.ComponentType<{ className?: string }>; color: string }
> = {
  interview_prep: {
    label: "Préparation d'Entretien (STAR+R)",
    icon: FiAward,
    color: "indigo",
  },
  cv_tailoring: {
    label: "CVs Sur-Mesure (ATS)",
    icon: FiFileText,
    color: "blue",
  },
  cover_letter: {
    label: "Lettres de Motivation IA",
    icon: FiMail,
    color: "purple",
  },
  evaluation: {
    label: "Évaluations Two-Pass (Blocs A-G)",
    icon: FiZap,
    color: "amber",
  },
  cv_parsing: {
    label: "Parsing de CV (Mistral VLM)",
    icon: FiLayers,
    color: "sky",
  },
  offer_summary: {
    label: "Résumés d'Offres & Découverte",
    icon: FiCpu,
    color: "emerald",
  },
};

export default function UsageSettingsPage() {
  const [summary, setSummary] = useState<UserQuotaSummary | null>(null);
  const [records, setRecords] = useState<ApiUsageRecord[]>([]);
  const [tiers, setTiers] = useState<Record<string, TierPricingInfo>>({});
  const [loading, setLoading] = useState(true);
  const [updatingTier, setUpdatingTier] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [sumData, recData, tierData] = await Promise.all([
        usageApi.getSummary(),
        usageApi.getRecords(0, 30),
        usageApi.getTiers().catch(() => ({})),
      ]);
      setSummary(sumData);
      setRecords(recData);
      setTiers(tierData);
    } catch (err: unknown) {
      console.error("Error loading usage settings:", err);
      const msg = err instanceof Error ? err.message : "Erreur lors du chargement des quotas.";
      setError(msg);
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
      const msg = err instanceof Error ? err.message : "Impossible de changer de palier.";
      setError(msg);
    } finally {
      setUpdatingTier(null);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <FiRefreshCw className="w-8 h-8 animate-spin text-indigo-400" />
          <p className="text-sm text-slate-400">Chargement de votre tableau de bord de consommation...</p>
        </div>
      </div>
    );
  }

  const currentTier = (summary?.tier || "free").toLowerCase() as UserTier;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-6xl mx-auto space-y-8">
        {/* Top Header */}
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
              Quotas & Abonnement
            </h1>
            <p className="text-xs sm:text-sm text-slate-400">
              Gérez votre formule, suivez votre consommation mensuelle d'IA et débloquez des capacités accrues.
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

        {/* Notifications */}
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

        {/* Summary Card */}
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

        {/* SECTION 1: QUOTA GAUGES */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <FiTrendingUp className="w-5 h-5 text-indigo-400" />
              Consommation Mensuelle par Ressource
            </h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Object.entries(ACTION_CONFIG).map(([actionKey, config]) => {
              const quota: ActionQuotaUsage | undefined = summary?.usage?.[actionKey] ?? summary?.quotas?.[actionKey];
              const used = quota?.used ?? 0;
              const limit = quota?.monthly_limit;
              const remaining = quota?.remaining;
              const isUnlimited = limit === null || limit === undefined;
              const percent = isUnlimited ? 0 : Math.min(100, Math.round((used / limit) * 100));

              let barColor = "bg-emerald-500";
              if (percent >= 100) barColor = "bg-rose-500";
              else if (percent >= 70) barColor = "bg-amber-500";

              const IconComponent = config.icon;

              return (
                <div
                  key={actionKey}
                  className="bg-slate-900/70 border border-slate-800 rounded-2xl p-5 flex flex-col justify-between shadow-lg hover:border-slate-700 transition-colors"
                >
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2.5">
                        <div className="p-2 rounded-xl bg-slate-800 text-indigo-400 border border-slate-700/60">
                          <IconComponent className="w-4 h-4" />
                        </div>
                        <span className="text-xs sm:text-sm font-semibold text-white">
                          {config.label}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-baseline justify-between pt-1">
                      <div className="text-2xl font-black text-white">
                        {used}{" "}
                        <span className="text-xs font-medium text-slate-400">
                          / {isUnlimited ? "Illimité" : limit}
                        </span>
                      </div>
                      <span
                        className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                          isUnlimited
                            ? "bg-purple-500/10 text-purple-300 border border-purple-500/20"
                            : remaining === 0
                            ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                            : "bg-slate-800 text-slate-300"
                        }`}
                      >
                        {isUnlimited ? "Illimité" : `${remaining} restant${remaining! > 1 ? "s" : ""}`}
                      </span>
                    </div>

                    {!isUnlimited && (
                      <div className="space-y-1">
                        <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                          <div
                            className={`h-full transition-all duration-500 ${barColor}`}
                            style={{ width: `${percent}%` }}
                          />
                        </div>
                        <span className="text-[11px] text-slate-500 block text-right">
                          {percent}% consommé
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* SECTION 2: SUBSCRIPTION TIERS */}
        <div className="space-y-4 pt-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <FiDollarSign className="w-5 h-5 text-indigo-400" />
              Changer de Formule (Simulation & Upgrade)
            </h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* FREE TIER */}
            <div
              className={`rounded-2xl p-6 border flex flex-col justify-between transition-all ${
                currentTier === "free"
                  ? "bg-slate-900/90 border-indigo-500/50 shadow-xl shadow-indigo-500/10"
                  : "bg-slate-900/50 border-slate-800 hover:border-slate-700"
              }`}
            >
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-lg font-bold text-white">Free</h4>
                  {currentTier === "free" && (
                    <span className="text-xs font-bold px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                      Actuel
                    </span>
                  )}
                </div>
                <div>
                  <span className="text-3xl font-black text-white">0€</span>
                  <span className="text-xs text-slate-400"> / pour toujours</span>
                </div>
                <ul className="space-y-2 text-xs text-slate-300 border-t border-slate-800 pt-4">
                  <li className="flex items-center gap-2">
                    <FiCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span><strong>1</strong> Préparation d'entretien / mois</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <FiCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span><strong>2</strong> CVs Sur-Mesure / mois</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <FiCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span><strong>5</strong> Lettres de motivation / mois</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <FiCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span><strong>20</strong> Évaluations Two-Pass / mois</span>
                  </li>
                </ul>
              </div>

              <button
                type="button"
                disabled={currentTier === "free" || updatingTier !== null}
                onClick={() => handleTierSwitch("free")}
                className="mt-6 w-full py-2.5 rounded-xl text-xs font-bold border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-200 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {currentTier === "free" ? "Plan Actif" : "Basculer en Free"}
              </button>
            </div>

            {/* ADVANCED TIER */}
            <div
              className={`rounded-2xl p-6 border flex flex-col justify-between transition-all relative overflow-hidden ${
                currentTier === "advanced"
                  ? "bg-slate-900/90 border-indigo-500 shadow-xl shadow-indigo-500/20"
                  : "bg-slate-900/60 border-slate-800 hover:border-slate-700"
              }`}
            >
              <div className="absolute top-0 right-0 bg-indigo-600 text-white text-[10px] font-extrabold uppercase px-3 py-1 rounded-bl-xl tracking-wider">
                Populaire
              </div>

              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-lg font-bold text-white">Advanced</h4>
                  {currentTier === "advanced" && (
                    <span className="text-xs font-bold px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                      Actuel
                    </span>
                  )}
                </div>
                <div>
                  <span className="text-3xl font-black text-white">9.90€</span>
                  <span className="text-xs text-slate-400"> / mois</span>
                </div>
                <ul className="space-y-2 text-xs text-slate-300 border-t border-slate-800 pt-4">
                  <li className="flex items-center gap-2">
                    <FiCheck className="w-4 h-4 text-indigo-400 shrink-0" />
                    <span><strong>10</strong> Préparations d'entretien / mois</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <FiCheck className="w-4 h-4 text-indigo-400 shrink-0" />
                    <span><strong>15</strong> CVs Sur-Mesure / mois</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <FiCheck className="w-4 h-4 text-indigo-400 shrink-0" />
                    <span><strong>30</strong> Lettres de motivation / mois</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <FiCheck className="w-4 h-4 text-indigo-400 shrink-0" />
                    <span><strong>100</strong> Évaluations Two-Pass / mois</span>
                  </li>
                </ul>
              </div>

              <button
                type="button"
                disabled={currentTier === "advanced" || updatingTier !== null}
                onClick={() => handleTierSwitch("advanced")}
                className="mt-6 w-full py-2.5 rounded-xl text-xs font-bold bg-indigo-600 hover:bg-indigo-500 text-white shadow-md shadow-indigo-500/20 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {updatingTier === "advanced"
                  ? "Mise à jour..."
                  : currentTier === "advanced"
                  ? "Plan Actif"
                  : "Choisir Advanced"}
              </button>
            </div>

            {/* PRO TIER */}
            <div
              className={`rounded-2xl p-6 border flex flex-col justify-between transition-all ${
                currentTier === "pro"
                  ? "bg-slate-900/90 border-purple-500 shadow-xl shadow-purple-500/20"
                  : "bg-slate-900/50 border-slate-800 hover:border-slate-700"
              }`}
            >
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-lg font-bold text-white">Pro</h4>
                  {currentTier === "pro" && (
                    <span className="text-xs font-bold px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30">
                      Actuel
                    </span>
                  )}
                </div>
                <div>
                  <span className="text-3xl font-black text-white">24.90€</span>
                  <span className="text-xs text-slate-400"> / mois</span>
                </div>
                <ul className="space-y-2 text-xs text-slate-300 border-t border-slate-800 pt-4">
                  <li className="flex items-center gap-2">
                    <FiCheck className="w-4 h-4 text-purple-400 shrink-0" />
                    <span className="font-bold text-purple-300">Tout Illimité</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <FiCheck className="w-4 h-4 text-purple-400 shrink-0" />
                    <span>Préparations d'entretien illimitées</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <FiCheck className="w-4 h-4 text-purple-400 shrink-0" />
                    <span>Générateur de CVs illimité</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <FiCheck className="w-4 h-4 text-purple-400 shrink-0" />
                    <span>Lettres & Évaluations illimitées</span>
                  </li>
                </ul>
              </div>

              <button
                type="button"
                disabled={currentTier === "pro" || updatingTier !== null}
                onClick={() => handleTierSwitch("pro")}
                className="mt-6 w-full py-2.5 rounded-xl text-xs font-bold bg-purple-600 hover:bg-purple-500 text-white shadow-md shadow-purple-500/20 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {updatingTier === "pro"
                  ? "Mise à jour..."
                  : currentTier === "pro"
                  ? "Plan Actif"
                  : "Choisir Pro"}
              </button>
            </div>
          </div>
        </div>

        {/* SECTION 3: RECENT LLM ACTIVITY AUDIT LOG */}
        <div className="space-y-4 pt-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <FiClock className="w-5 h-5 text-indigo-400" />
              Journal Récent des Appels IA ({records.length} opérations)
            </h3>
          </div>

          <div className="bg-slate-900/70 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
            {records.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500">
                Aucun appel IA enregistré récemment.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-950/60 text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-800">
                    <tr>
                      <th className="py-3 px-4">Date / Heure</th>
                      <th className="py-3 px-4">Action</th>
                      <th className="py-3 px-4">Modèle LLM</th>
                      <th className="py-3 px-4">Tokens (In / Out)</th>
                      <th className="py-3 px-4">Latence</th>
                      <th className="py-3 px-4">Coût USD</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 text-slate-300">
                    {records.map((rec, idx) => {
                      const dateStr = new Date(rec.created_at).toLocaleString("fr-FR", {
                        day: "2-digit",
                        month: "2-digit",
                        hour: "2-digit",
                        minute: "2-digit",
                      });
                      const actionLabel = ACTION_CONFIG[rec.action]?.label || rec.action;

                      return (
                        <tr key={rec.id || idx} className="hover:bg-slate-800/30 transition-colors">
                          <td className="py-3 px-4 text-slate-400 whitespace-nowrap">{dateStr}</td>
                          <td className="py-3 px-4 font-semibold text-white whitespace-nowrap">
                            {actionLabel}
                          </td>
                          <td className="py-3 px-4 text-indigo-300 font-mono text-[11px]">
                            {rec.models_used?.join(", ") || "—"}
                          </td>
                          <td className="py-3 px-4 text-slate-400 font-mono text-[11px]">
                            {rec.input_tokens.toLocaleString()} / {rec.output_tokens.toLocaleString()}
                          </td>
                          <td className="py-3 px-4 text-slate-400 whitespace-nowrap">
                            {rec.latency_ms ? `${rec.latency_ms} ms` : "—"}
                          </td>
                          <td className="py-3 px-4 text-emerald-400 font-mono font-medium">
                            ${rec.estimated_cost_usd?.toFixed(4) || "0.0000"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
