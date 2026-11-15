"use client";

import { useState } from "react";
import {
  FiAlertTriangle,
  FiCheck,
  FiCheckCircle,
  FiCopy,
  FiFileText,
  FiInfo,
  FiShield,
  FiTag,
} from "react-icons/fi";
import type { BlocG, BlocH, ImportanceEvidenceTier } from "@/types/jobOffer";

const TIER_STYLES: Record<ImportanceEvidenceTier, { label: string; cls: string }> = {
  stated: {
    label: "Explicite",
    cls: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  },
  structural: {
    label: "Structurelle",
    cls: "bg-purple-500/15 text-purple-300 border-purple-500/30",
  },
  inferred: {
    label: "Déduite",
    cls: "bg-slate-700/60 text-slate-300 border-slate-600/60",
  },
};

export function EvidenceTierBadge({ tier }: { tier?: ImportanceEvidenceTier }) {
  if (!tier || !(tier in TIER_STYLES)) return null;
  const style = TIER_STYLES[tier];
  return (
    <span
      title="Origine de la pondération dans l'offre"
      className={`px-2 py-0.5 rounded text-[10px] font-medium border ${style.cls}`}
    >
      {style.label}
    </span>
  );
}

export function BlocGRiskSummary({ blocG }: { blocG: BlocG }) {
  const extraFlags = [
    blocG.employment_classification_risk
      ? `Classification : ${blocG.employment_classification_risk}`
      : null,
    blocG.pay_range_width_warning ? `Fourchette salariale : ${blocG.pay_range_width_warning}` : null,
    blocG.ai_buzzword_mismatch ? `Buzzwords IA : ${blocG.ai_buzzword_mismatch}` : null,
  ].filter((x): x is string => Boolean(x));

  const summaryItems = blocG.risk_summary ?? [];
  if (!blocG.company_history_note && extraFlags.length === 0 && summaryItems.length === 0) {
    return null;
  }

  return (
    <div className="space-y-3 mt-4">
      {blocG.company_history_note && (
        <div className="bg-slate-900/70 border border-slate-700/70 rounded-lg p-3 text-xs text-slate-300 flex items-start gap-2.5">
          <FiInfo className="text-sky-400 shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold text-sky-300 block mb-0.5">
              Contexte &amp; historique entreprise
            </span>
            <p className="leading-relaxed">{blocG.company_history_note}</p>
          </div>
        </div>
      )}

      {extraFlags.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {extraFlags.map((flag, idx) => (
            <span
              key={idx}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs bg-amber-500/10 text-amber-300 border border-amber-500/30"
            >
              <FiAlertTriangle className="shrink-0" />
              {flag}
            </span>
          ))}
        </div>
      )}

      {summaryItems.length > 0 && (
        <div className="rounded-lg border border-slate-700/70 overflow-hidden bg-slate-900/50">
          <div className="px-3 py-2 border-b border-slate-800 text-[11px] font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
            <FiShield className="text-blue-400" />
            <span>Matrice des signaux Bloc G</span>
          </div>
          <div className="divide-y divide-slate-800/80">
            {summaryItems.map((row, idx) => (
              <div key={idx} className="flex items-center justify-between gap-3 px-3 py-2 text-xs">
                <span className="text-slate-300">{row.signal}</span>
                <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-slate-800 text-slate-200 border border-slate-700">
                  {row.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function BlocHDraftPanel({
  blocH,
  compact = false,
}: {
  blocH?: BlocH | null;
  compact?: boolean;
}) {
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);

  if (!blocH?.eligible) return null;

  const hasContent =
    (blocH.answers?.length ?? 0) > 0 ||
    (blocH.key_achievements?.length ?? 0) > 0 ||
    (blocH.gaps_flagged?.length ?? 0) > 0 ||
    (blocH.jd_keywords?.length ?? 0) > 0;
  if (!hasContent) return null;

  const handleCopy = async (text: string, idx: number) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedIdx(idx);
      window.setTimeout(() => setCopiedIdx((curr) => (curr === idx ? null : curr)), 1800);
    } catch {
      // Clipboard unavailable in restricted context
    }
  };

  return (
    <div className="bg-emerald-950/20 border border-emerald-500/30 rounded-xl p-4 sm:p-5 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm sm:text-base font-bold text-white flex items-center gap-2">
          <FiFileText className="text-emerald-400" />
          <span>Bloc H — Brouillons de réponse formulaire</span>
        </h3>
        <span className="text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
          Offre &ge; 4.0 éligible
        </span>
      </div>

      {blocH.answers && blocH.answers.length > 0 && (
        <div className="space-y-2.5">
          {blocH.answers.map((item, idx) => (
            <div
              key={idx}
              className="rounded-lg bg-slate-900/75 border border-slate-700/70 p-3 space-y-1.5"
            >
              <div className="flex items-start justify-between gap-2">
                <p className="text-xs font-semibold text-blue-300">{item.question}</p>
                <button
                  type="button"
                  onClick={() => handleCopy(item.answer, idx)}
                  className="shrink-0 inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors"
                >
                  {copiedIdx === idx ? (
                    <>
                      <FiCheck className="text-emerald-400" />
                      <span>Copié</span>
                    </>
                  ) : (
                    <>
                      <FiCopy />
                      <span>Copier</span>
                    </>
                  )}
                </button>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed whitespace-pre-line">
                {item.answer}
              </p>
            </div>
          ))}
        </div>
      )}

      <div className={`grid grid-cols-1 ${compact ? "" : "md:grid-cols-2"} gap-3 text-xs`}>
        {blocH.key_achievements && blocH.key_achievements.length > 0 && (
          <div className="rounded-lg bg-slate-900/60 border border-slate-800 p-3">
            <p className="font-semibold text-emerald-300 mb-1.5 flex items-center gap-1.5">
              <FiCheckCircle /> Réalisations clés à valoriser
            </p>
            <ul className="space-y-1 text-slate-300 list-disc pl-4">
              {blocH.key_achievements.map((ach, i) => (
                <li key={i}>{ach}</li>
              ))}
            </ul>
          </div>
        )}

        {blocH.gaps_flagged && blocH.gaps_flagged.length > 0 && (
          <div className="rounded-lg bg-slate-900/60 border border-slate-800 p-3">
            <p className="font-semibold text-amber-300 mb-1.5 flex items-center gap-1.5">
              <FiAlertTriangle /> Points à préparer / cadrer
            </p>
            <ul className="space-y-1 text-slate-300 list-disc pl-4">
              {blocH.gaps_flagged.map((gap, i) => (
                <li key={i}>{gap}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {blocH.jd_keywords && blocH.jd_keywords.length > 0 && (
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-1.5 flex items-center gap-1.5">
            <FiTag /> Mots-clés JD à réutiliser
          </p>
          <div className="flex flex-wrap gap-1.5">
            {blocH.jd_keywords.map((kw, idx) => (
              <span
                key={idx}
                className="px-2 py-0.5 rounded-md text-[11px] bg-blue-500/15 text-blue-300 border border-blue-500/30"
              >
                {kw}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
