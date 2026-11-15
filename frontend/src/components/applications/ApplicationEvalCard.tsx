"use client";

import React from "react";
import { OfferEvaluation } from "@/lib/api";
import { BlocHDraftPanel } from "../offers/OfferEvaluationExtras";
import {
  FiRefreshCw,
  FiZap,
  FiCheckCircle,
  FiAlertTriangle,
  FiArrowRight,
  FiTarget,
} from "react-icons/fi";

interface ApplicationEvalCardProps {
  evaluation: OfferEvaluation | null;
  loadingEvaluation: boolean;
  isScoring: boolean;
  scoringError: string | null;
  scoreSuccessMessage: string | null;
  isLinkingOffer: boolean;
  onScoreApplication: () => void;
  onOpenOffer: (suffix?: string) => void;
}

function getScoreBadgeStyles(score: number) {
  if (score >= 4.0) {
    return {
      bg: "bg-emerald-500/10 border-emerald-500/30 text-emerald-300",
      label: "Excellent match",
    };
  }
  if (score >= 3.0) {
    return {
      bg: "bg-amber-500/10 border-amber-500/30 text-amber-300",
      label: "Match partiel",
    };
  }
  return {
    bg: "bg-rose-500/10 border-rose-500/30 text-rose-300",
    label: "Écart significatif",
  };
}

/**
 * Displays the Two-Pass AI scoring card, reliability alerts, and Bloc H draft inside the application drawer.
 */
export function ApplicationEvalCard({
  evaluation,
  loadingEvaluation,
  isScoring,
  scoringError,
  scoreSuccessMessage,
  isLinkingOffer,
  onScoreApplication,
  onOpenOffer,
}: ApplicationEvalCardProps) {
  return (
    <div className="rounded-2xl border border-slate-700/70 bg-slate-800/40 p-5 shadow-lg relative overflow-hidden backdrop-blur-sm">
      <div className="absolute top-0 right-0 w-36 h-36 bg-blue-500/5 rounded-full blur-2xl pointer-events-none" />

      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 text-sm font-bold text-white">
          <span className="p-1.5 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20">
            <FiZap className="w-4 h-4" />
          </span>
          <span>Scoring IA Two-Pass (Gemini 3.8 Flash)</span>
        </div>

        {evaluation && (
          <button
            type="button"
            onClick={onScoreApplication}
            disabled={isScoring}
            className="inline-flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 px-2 py-1 rounded bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/30 transition-all font-medium disabled:opacity-50"
            title="Recalculer le scoring d'adéquation"
          >
            <FiRefreshCw className={`w-3 h-3 ${isScoring ? "animate-spin" : ""}`} />
            <span>{isScoring ? "Calcul..." : "Ré-évaluer"}</span>
          </button>
        )}
      </div>

      {scoringError && (
        <div className="mb-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start gap-2">
          <FiAlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="font-semibold">Échec du scoring IA</p>
            <p className="mt-0.5">{scoringError}</p>
          </div>
        </div>
      )}

      {scoreSuccessMessage && (
        <div className="mb-4 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-center gap-2">
          <FiCheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{scoreSuccessMessage}</span>
        </div>
      )}

      {loadingEvaluation ? (
        <div className="py-6 flex flex-col items-center justify-center gap-2 text-slate-400 text-xs">
          <FiRefreshCw className="w-5 h-5 animate-spin text-blue-400" />
          <span>Chargement de l&apos;évaluation IA...</span>
        </div>
      ) : evaluation ? (
        <div>
          <div className="flex items-center gap-4 bg-slate-900/60 rounded-xl p-4 border border-slate-700/50">
            <div
              className={`flex flex-col items-center justify-center p-3 rounded-xl border ${
                getScoreBadgeStyles(evaluation.score).bg
              } min-w-[90px] text-center shadow-inner`}
            >
              <div className="flex items-baseline gap-0.5">
                <span className="text-3xl font-extrabold tracking-tight">
                  {evaluation.score.toFixed(1)}
                </span>
                <span className="text-[11px] text-slate-400 font-medium">/ 5.0</span>
              </div>
              <span className="text-[10px] font-semibold mt-0.5">
                {getScoreBadgeStyles(evaluation.score).label}
              </span>
            </div>

            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-white leading-snug line-clamp-2">
                {evaluation.headline || "Évaluation de profil complétée"}
              </p>
              {evaluation.bloc_a?.archetype && (
                <p className="text-xs text-slate-400 mt-1 line-clamp-1">
                  Archétype :{" "}
                  <span className="text-indigo-300 font-medium">
                    {evaluation.bloc_a.archetype}
                  </span>
                </p>
              )}

              <div className="flex flex-wrap items-center gap-2 mt-2">
                {evaluation.bloc_b?.matched_requirements && (
                  <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 flex items-center gap-1">
                    <FiCheckCircle className="w-3 h-3 text-emerald-400" />
                    {evaluation.bloc_b.matched_requirements.length} match
                  </span>
                )}
                {evaluation.bloc_b?.missing_requirements &&
                  evaluation.bloc_b.missing_requirements.length > 0 && (
                    <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-slate-700/40 text-slate-300 border border-slate-600/40">
                      {evaluation.bloc_b.missing_requirements.length} écarts
                    </span>
                  )}
                {evaluation.bloc_a?.red_flags && evaluation.bloc_a.red_flags.length > 0 && (
                  <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/30 flex items-center gap-1">
                    <FiAlertTriangle className="w-3 h-3 text-rose-400" />
                    {evaluation.bloc_a.red_flags.length} red flag
                  </span>
                )}
              </div>
            </div>
          </div>

          {(evaluation.bloc_g?.is_scam_risk ||
            evaluation.bloc_g?.is_ghost_job ||
            evaluation.bloc_g?.company_history_note ||
            (evaluation.bloc_g?.warnings && evaluation.bloc_g.warnings.length > 0)) && (
            <div className="mt-3 p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex items-start gap-2">
              <FiAlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="font-semibold">
                  {evaluation.bloc_g.is_scam_risk
                    ? "Risque d'arnaque détecté — score peu fiable"
                    : evaluation.bloc_g.is_ghost_job
                    ? "Offre fantôme suspectée — score peu fiable"
                    : evaluation.bloc_g?.warnings?.length
                    ? "Contenu peu fiable — score à prendre avec précaution"
                    : "Contexte entreprise"}
                </p>
                {evaluation.bloc_g.company_history_note && (
                  <p className="mt-0.5 text-slate-200">
                    {evaluation.bloc_g.company_history_note}
                  </p>
                )}
                {evaluation.bloc_g.warnings?.map((warn, idx) => (
                  <p key={idx} className="mt-0.5">
                    {warn}
                  </p>
                ))}
              </div>
            </div>
          )}

          {evaluation.bloc_h?.eligible && (
            <div className="mt-3">
              <BlocHDraftPanel blocH={evaluation.bloc_h} compact />
            </div>
          )}

          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-slate-800/80 pt-3">
            <button
              type="button"
              onClick={() => onOpenOffer("?tab=interview")}
              disabled={isLinkingOffer}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 transition-colors disabled:opacity-60"
            >
              <FiTarget className="w-3.5 h-3.5 text-indigo-400" />
              <span>🎯 Préparer l&apos;entretien</span>
            </button>

            <button
              type="button"
              onClick={() => onOpenOffer()}
              disabled={isLinkingOffer}
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-blue-400 hover:text-blue-300 transition-colors disabled:opacity-60"
            >
              <span>Analyse complète</span>
              <FiArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-start gap-3 py-1">
          <p className="text-xs text-slate-300 leading-relaxed">
            Mesurez instantanément la pertinence de votre candidature grâce à l&apos;analyse d&apos;adéquation
            confrontant minutieusement votre profil aux exigences réelles et à la viabilité du poste.
          </p>

          <button
            type="button"
            onClick={onScoreApplication}
            disabled={isScoring}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white text-xs font-bold shadow-md shadow-blue-500/20 transition-all disabled:opacity-60 disabled:cursor-not-allowed"
          >
            <FiZap className={`w-4 h-4 ${isScoring ? "animate-spin" : ""}`} />
            <span>
              {isScoring ? "Analyse d'adéquation en cours..." : "✨ Lancer le scoring IA"}
            </span>
          </button>
        </div>
      )}
    </div>
  );
}
