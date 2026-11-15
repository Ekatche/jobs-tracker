"use client";

import React from "react";
import { AdminCostSummary, AdminPeriod } from "@/types/admin";
import {
  FiDollarSign,
  FiCpu,
  FiUsers,
  FiActivity,
  FiZap,
  FiFileText,
  FiMail,
  FiAward,
  FiLayers,
} from "react-icons/fi";

const ACTION_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  interview_prep: FiAward,
  cv_tailoring: FiFileText,
  cover_letter: FiMail,
  evaluation: FiZap,
  cv_parsing: FiLayers,
  offer_summary: FiCpu,
};

interface AdminCostsTabProps {
  costSummary: AdminCostSummary | null;
  period: AdminPeriod;
}

/**
 * Displays aggregate LLM cost KPIs, per-model spend table, and per-feature usage cards.
 */
export function AdminCostsTab({ costSummary, period }: AdminCostsTabProps) {
  return (
    <div className="space-y-8 animate-fade-in">
      {/* KPI Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-5 shadow-lg backdrop-blur">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Dépense Totale
            </span>
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center border border-emerald-500/20">
              <FiDollarSign className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-black text-white tracking-tight">
            ${costSummary ? costSummary.total_cost_usd.toFixed(4) : "0.0000"}
          </div>
          <div className="text-[11px] text-slate-400 mt-1 flex items-center gap-1">
            <span>Période active :</span>
            <span className="font-semibold text-emerald-400 uppercase">{period}</span>
          </div>
        </div>

        <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-5 shadow-lg backdrop-blur">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Tokens Consommés
            </span>
            <div className="w-8 h-8 rounded-lg bg-blue-500/10 text-blue-400 flex items-center justify-center border border-blue-500/20">
              <FiCpu className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-black text-white tracking-tight">
            {costSummary ? costSummary.total_tokens.toLocaleString() : "0"}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Entrée + sortie cumulées</div>
        </div>

        <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-5 shadow-lg backdrop-blur">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Appels LLM
            </span>
            <div className="w-8 h-8 rounded-lg bg-indigo-500/10 text-indigo-400 flex items-center justify-center border border-indigo-500/20">
              <FiActivity className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-black text-white tracking-tight">
            {costSummary ? costSummary.total_requests.toLocaleString() : "0"}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Générations et inférences</div>
        </div>

        <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-5 shadow-lg backdrop-blur">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Coût Moyen / Utilisateur
            </span>
            <div className="w-8 h-8 rounded-lg bg-amber-500/10 text-amber-400 flex items-center justify-center border border-amber-500/20">
              <FiUsers className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-black text-white tracking-tight">
            ${costSummary ? costSummary.avg_cost_per_user.toFixed(4) : "0.0000"}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">
            Sur {costSummary?.active_users_count || 0} utilisateur(s) actif(s)
          </div>
        </div>
      </div>

      {/* Model Breakdown */}
      <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-6 shadow-xl backdrop-blur">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <FiCpu className="text-blue-400" />
              Répartition des Dépenses par Modèle IA
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Coûts unitaires et volume de tokens par modèle (OpenAI, Gemini, Mistral)
            </p>
          </div>
        </div>

        {costSummary?.model_breakdown && costSummary.model_breakdown.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-800 text-xs text-slate-400 font-semibold uppercase tracking-wider">
                  <th className="pb-3 pl-2">Modèle</th>
                  <th className="pb-3 text-right">Appels</th>
                  <th className="pb-3 text-right">Tokens In / Out</th>
                  <th className="pb-3 text-right">Total Tokens</th>
                  <th className="pb-3 text-right">Coût ($ USD)</th>
                  <th className="pb-3 pr-2 text-right">% du Budget</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {costSummary.model_breakdown.map((m) => {
                  const pct =
                    costSummary.total_cost_usd > 0
                      ? Math.min(100, (m.cost_usd / costSummary.total_cost_usd) * 100)
                      : 0;
                  return (
                    <tr key={m.model} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-3 pl-2 font-semibold text-white">
                        <span className="font-mono text-xs text-blue-300 bg-blue-950/60 px-2 py-1 rounded-lg border border-blue-800/40">
                          {m.model}
                        </span>
                      </td>
                      <td className="py-3 text-right text-slate-300 font-mono text-xs">
                        {m.requests_count.toLocaleString()}
                      </td>
                      <td className="py-3 text-right text-slate-400 font-mono text-xs">
                        {m.input_tokens.toLocaleString()} / {m.output_tokens.toLocaleString()}
                      </td>
                      <td className="py-3 text-right text-slate-200 font-mono text-xs font-semibold">
                        {m.total_tokens.toLocaleString()}
                      </td>
                      <td className="py-3 text-right text-emerald-400 font-mono text-xs font-bold">
                        ${m.cost_usd.toFixed(4)}
                      </td>
                      <td className="py-3 pr-2 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <div className="w-20 bg-slate-800 rounded-full h-1.5 overflow-hidden">
                            <div className="bg-emerald-500 h-1.5 rounded-full" style={{ width: `${pct}%` }} />
                          </div>
                          <span className="text-xs text-slate-400 font-mono w-10 text-right">
                            {pct.toFixed(1)}%
                          </span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-12 text-slate-500 text-sm">
            Aucun appel API enregistré pour cette période.
          </div>
        )}
      </div>

      {/* Action Breakdown */}
      <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-6 shadow-xl backdrop-blur">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <FiZap className="text-amber-400" />
              Consommation par Fonctionnalité Métier
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Coûts imputables aux différents générateurs (STAR+R, CV ATS, Lettres, Évaluations)
            </p>
          </div>
        </div>

        {costSummary?.action_breakdown && costSummary.action_breakdown.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {costSummary.action_breakdown.map((a) => {
              const Icon = ACTION_ICONS[a.action] || FiZap;
              const pct =
                costSummary.total_cost_usd > 0
                  ? Math.min(100, (a.cost_usd / costSummary.total_cost_usd) * 100)
                  : 0;
              return (
                <div
                  key={a.action}
                  className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 flex flex-col justify-between"
                >
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="flex items-center gap-2.5">
                      <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20">
                        <Icon className="w-4 h-4" />
                      </div>
                      <span className="font-semibold text-sm text-slate-200 leading-snug">
                        {a.label}
                      </span>
                    </div>
                    <span className="text-xs font-mono font-bold text-emerald-400 shrink-0">
                      ${a.cost_usd.toFixed(4)}
                    </span>
                  </div>

                  <div>
                    <div className="flex justify-between text-[11px] text-slate-400 mb-1">
                      <span>{a.requests_count} appels</span>
                      <span>{a.total_tokens.toLocaleString()} tokens</span>
                    </div>
                    <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                      <div className="bg-blue-500 h-1.5 rounded-full" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="text-center py-12 text-slate-500 text-sm">
            Aucun appel API enregistré pour cette période.
          </div>
        )}
      </div>
    </div>
  );
}
