"use client";

import React from "react";
import {
  FiZap,
  FiFileText,
  FiMail,
  FiAward,
  FiCpu,
  FiLayers,
  FiTrendingUp,
} from "react-icons/fi";
import type { ActionQuotaUsage, UserQuotaSummary } from "@/types/usage";

export const ACTION_CONFIG: Record<
  string,
  { label: string; icon: React.ComponentType<{ className?: string }>; color: string }
> = {
  interview_prep: { label: "Préparation d'Entretien (STAR+R)", icon: FiAward, color: "indigo" },
  cv_tailoring: { label: "CVs Sur-Mesure (ATS)", icon: FiFileText, color: "blue" },
  cover_letter: { label: "Lettres de Motivation IA", icon: FiMail, color: "purple" },
  evaluation: { label: "Évaluations d'Adéquation IA", icon: FiZap, color: "amber" },
  cv_parsing: { label: "Parsing de CV (Mistral VLM)", icon: FiLayers, color: "sky" },
  offer_summary: { label: "Résumés d'Offres & Découverte", icon: FiCpu, color: "emerald" },
};

export default function UsageQuotaGauges({
  summary,
}: {
  summary: UserQuotaSummary | null;
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-bold text-white flex items-center gap-2">
          <FiTrendingUp className="w-5 h-5 text-indigo-400" />
          Consommation Mensuelle par Ressource
        </h3>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {Object.entries(ACTION_CONFIG).map(([actionKey, config]) => {
          const quota: ActionQuotaUsage | undefined =
            summary?.usage?.[actionKey] ?? summary?.quotas?.[actionKey];
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
                    {isUnlimited
                      ? "Illimité"
                      : `${remaining} restant${remaining! > 1 ? "s" : ""}`}
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
  );
}
