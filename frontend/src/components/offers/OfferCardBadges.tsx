"use client";

import { FiAlertCircle, FiZap } from "react-icons/fi";
import type { JobOffer } from "@/lib/api";
import { getContractBadgeStyles } from "@/lib/contractBadge";
import { FAILED_CONDITION_LABELS, getRecentBadgeInfo } from "@/lib/offerFormatters";
import { getRelevanceLevelOption } from "@/lib/relevanceLevels";

export default function OfferCardBadges({ offer }: { offer: JobOffer }) {
  const recentBadge = getRecentBadgeInfo(offer.created_at);
  const relevance = getRelevanceLevelOption(offer.relevance_level);
  const contractBadge = getContractBadgeStyles(offer.type_contrat);

  return (
    <>
      <div className="flex flex-wrap gap-1.5 mb-3 items-center">
        {recentBadge && (
          <span
            className={`px-2 py-0.5 text-xs font-bold rounded-lg border flex items-center gap-1 shadow-sm ${
              recentBadge.isFresh
                ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40 shadow-emerald-500/10"
                : "bg-cyan-500/20 text-cyan-300 border-cyan-500/40 shadow-cyan-500/10"
            }`}
            title={`Offre ajoutée en base récemment (${recentBadge.label})`}
          >
            <FiZap className="w-3 h-3 fill-current text-emerald-400" />
            <span>{recentBadge.label}</span>
          </span>
        )}

        {offer.evaluation_score !== undefined && offer.evaluation_score !== null ? (
          <span
            className={`px-2.5 py-0.5 text-xs font-bold rounded-lg border flex items-center gap-1.5 shadow-sm ${
              offer.evaluation_score >= 4.0
                ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/35"
                : offer.evaluation_score >= 3.0
                ? "bg-amber-500/15 text-amber-300 border-amber-500/35"
                : "bg-rose-500/15 text-rose-300 border-rose-500/35"
            }`}
            title="Score d'adéquation calculé par IA"
          >
            <FiZap className="w-3 h-3 fill-current" />
            <span>Match {offer.evaluation_score.toFixed(1)}/5</span>
          </span>
        ) : offer.pipeline_stage === "evaluated" ? (
          <span className="px-2.5 py-0.5 bg-blue-500/15 text-blue-300 text-xs font-semibold rounded-lg border border-blue-500/30 flex items-center gap-1">
            <FiZap className="w-3 h-3" />
            <span>Évaluée</span>
          </span>
        ) : null}

        {relevance && (
          <span className={`px-2.5 py-0.5 text-xs font-bold rounded-lg border shadow-sm ${relevance.className}`}>
            {relevance.label}
          </span>
        )}

        {contractBadge && (
          <span className={`px-2 py-0.5 text-[11px] rounded-md border shadow-sm ${contractBadge.className}`}>
            {contractBadge.label}
          </span>
        )}

        {offer.mode_travail && offer.mode_travail !== "Non spécifié" && (
          <span className="px-2 py-0.5 bg-purple-500/10 text-purple-300 text-[11px] font-medium rounded-md border border-purple-500/20">
            {offer.mode_travail}
          </span>
        )}

        {offer.salaire && offer.salaire !== "Non spécifié" && (
          <span className="px-2 py-0.5 bg-emerald-500/10 text-emerald-300 text-[11px] font-medium rounded-md border border-emerald-500/20">
            {offer.salaire}
          </span>
        )}

        {offer.is_active === false && (
          <span className="px-2 py-0.5 bg-rose-500/15 text-rose-300 text-[11px] font-medium rounded-md border border-rose-500/30">
            Expirée
          </span>
        )}
      </div>

      {offer.failed_conditions && offer.failed_conditions.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {offer.failed_conditions.map((code) => {
            const label = FAILED_CONDITION_LABELS[code];
            if (!label) return null;
            return (
              <span
                key={code}
                className="px-2 py-0.5 bg-slate-800/60 text-slate-400 text-[11px] rounded-md border border-slate-700/50 flex items-center gap-1"
              >
                <FiAlertCircle className="w-3 h-3" />
                <span>{label}</span>
              </span>
            );
          })}
        </div>
      )}
    </>
  );
}
