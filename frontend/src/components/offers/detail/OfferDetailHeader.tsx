"use client";

import type { JobOffer, OfferEvaluation } from "@/lib/api";
import type { OfferDetailTab } from "@/hooks/useOfferDetail";
import { getContractBadgeStyles } from "@/lib/contractBadge";
import {
  FiBriefcase,
  FiMapPin,
  FiCalendar,
  FiExternalLink,
  FiAlertTriangle,
  FiShield,
  FiFileText,
  FiAward,
  FiTarget,
} from "react-icons/fi";

interface OfferDetailHeaderProps {
  offer: JobOffer;
  evaluation: OfferEvaluation | null;
  error: string | null;
  activeTab: OfferDetailTab;
  onSelectTab: (tab: OfferDetailTab) => void;
}

function getScoreColor(score: number | undefined | null) {
  if (!score) return "text-gray-400 border-gray-700 bg-gray-800/40";
  if (score >= 4.0) return "text-emerald-400 border-emerald-500/40 bg-emerald-500/10";
  if (score >= 3.0) return "text-amber-400 border-amber-500/40 bg-amber-500/10";
  return "text-rose-400 border-rose-500/40 bg-rose-500/10";
}

export default function OfferDetailHeader({
  offer,
  evaluation,
  error,
  activeTab,
  onSelectTab,
}: OfferDetailHeaderProps) {
  const score = evaluation ? evaluation.score : offer.evaluation_score;
  const badge = getContractBadgeStyles(offer.type_contrat);
  const hasVigilance =
    evaluation &&
    (evaluation.bloc_a.geo_mismatch ||
      evaluation.bloc_a.visa_sponsoring_refused ||
      (evaluation.bloc_a.red_flags && evaluation.bloc_a.red_flags.length > 0));

  return (
    <>
      {error && (
        <div className="mb-6 bg-rose-500/10 border border-rose-500/30 rounded-xl p-4 text-rose-300 flex items-center gap-3 text-sm">
          <FiAlertTriangle className="w-5 h-5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="bg-blue-night-lighter rounded-2xl p-6 md:p-8 border border-gray-700/70 shadow-xl mb-8">
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-6">
          <div className="flex-1">
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <span className="px-2.5 py-1 bg-blue-500/20 text-blue-300 text-xs font-medium rounded-full border border-blue-500/30">
                {offer.pipeline_stage || "discovered"}
              </span>
              {badge && (
                <span className={`px-2.5 py-1 text-xs rounded-full border shadow-sm ${badge.className}`}>
                  {badge.label}
                </span>
              )}
              {offer.mode_travail && (
                <span className="px-2.5 py-1 bg-purple-500/20 text-purple-300 text-xs font-medium rounded-full border border-purple-500/30">
                  {offer.mode_travail}
                </span>
              )}
              {offer.is_active === false && (
                <span className="px-2.5 py-1 bg-red-500/20 text-red-300 text-xs font-medium rounded-full border border-red-500/30">
                  Expirée / Inactive
                </span>
              )}
            </div>

            <h1 className="text-2xl md:text-3xl font-bold text-white mb-2">
              {offer.poste}
            </h1>

            <div className="flex flex-wrap items-center gap-4 text-gray-300 text-sm mb-4">
              <span className="flex items-center gap-1.5 font-medium text-white">
                <FiBriefcase className="text-blue-400" />
                {offer.entreprise}
              </span>
              {offer.localisation && (
                <span className="flex items-center gap-1.5 text-gray-400">
                  <FiMapPin className="text-blue-400" />
                  {offer.localisation}
                </span>
              )}
              {offer.salaire && offer.salaire !== "Non spécifié" && (
                <span className="text-emerald-400 font-medium">{offer.salaire}</span>
              )}
              {offer.date && (
                <span className="flex items-center gap-1.5 text-gray-400 text-xs">
                  <FiCalendar />
                  {new Date(offer.date).toLocaleDateString("fr-FR")}
                </span>
              )}
            </div>

            {offer.url && (
              <a
                href={offer.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 font-medium transition-colors"
              >
                <FiExternalLink />
                Consulter l&apos;annonce originale sur le site source
              </a>
            )}
          </div>

          <div className="flex md:flex-col items-center md:items-end justify-between border-t md:border-t-0 border-gray-700/60 pt-4 md:pt-0">
            <div
              className={`flex flex-col items-center justify-center p-4 rounded-2xl border ${getScoreColor(
                score
              )} min-w-[140px] text-center shadow-lg`}
            >
              <div className="flex items-baseline gap-1">
                <span className="text-4xl font-extrabold tracking-tight">
                  {score !== undefined && score !== null ? score.toFixed(1) : "—"}
                </span>
                <span className="text-xs text-gray-400 font-semibold">/ 5.0</span>
              </div>
              <span className="text-xs font-medium mt-1">
                {!score
                  ? "Non évalué"
                  : score >= 4.0
                  ? "Excellent Match"
                  : score >= 3.0
                  ? "Match Favorable"
                  : "Écart Important"}
              </span>
            </div>

            {!evaluation && (
              <p className="text-[11px] text-gray-400 mt-2 text-center md:text-right">
                Score IA d&apos;adéquation calculé selon votre profil
              </p>
            )}
          </div>
        </div>
      </div>

      {hasVigilance && evaluation && (
        <div className="bg-rose-500/10 border border-rose-500/30 rounded-2xl p-5 mb-6 text-rose-200">
          <div className="flex items-center gap-2.5 font-bold text-rose-400 mb-2">
            <FiAlertTriangle className="w-5 h-5 flex-shrink-0" />
            Points de vigilance identifiés
          </div>
          <ul className="list-disc list-inside space-y-1 text-sm pl-2">
            {evaluation.bloc_a.geo_mismatch && (
              <li>Incompatibilité géographique ou de télétravail sévère.</li>
            )}
            {evaluation.bloc_a.visa_sponsoring_refused && (
              <li>Sponsoring de visa non assuré par l&apos;entreprise.</li>
            )}
            {evaluation.bloc_a.red_flags?.map((flag, idx) => (
              <li key={idx}>{flag}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex border-b border-gray-700/80 mb-6 gap-2 overflow-x-auto">
        <button
          onClick={() => onSelectTab("job")}
          className={`px-4 py-2.5 text-sm font-semibold flex items-center gap-2 border-b-2 transition-colors whitespace-nowrap ${
            activeTab === "job"
              ? "border-blue-500 text-blue-400"
              : "border-transparent text-gray-400 hover:text-gray-200"
          }`}
        >
          <FiFileText className="w-4 h-4" />
          Annonce du Poste
        </button>

        <button
          onClick={() => onSelectTab("matching")}
          className={`px-4 py-2.5 text-sm font-semibold flex items-center gap-2 border-b-2 transition-colors whitespace-nowrap ${
            activeTab === "matching"
              ? "border-blue-500 text-blue-400"
              : "border-transparent text-gray-400 hover:text-gray-200"
          }`}
        >
          <FiAward className="w-4 h-4" />
          Adéquation Exigences
          {evaluation && (
            <span className="ml-1 text-xs px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300">
              {evaluation.bloc_b.matched_requirements.length}
            </span>
          )}
        </button>

        <button
          onClick={() => onSelectTab("analysis")}
          className={`px-4 py-2.5 text-sm font-semibold flex items-center gap-2 border-b-2 transition-colors whitespace-nowrap ${
            activeTab === "analysis"
              ? "border-blue-500 text-blue-400"
              : "border-transparent text-gray-400 hover:text-gray-200"
          }`}
        >
          <FiShield className="w-4 h-4" />
          Stratégie & Intégrité
        </button>

        <button
          onClick={() => onSelectTab("interview")}
          className={`px-4 py-2.5 text-sm font-semibold flex items-center gap-2 border-b-2 transition-colors whitespace-nowrap ${
            activeTab === "interview"
              ? "border-purple-500 text-purple-400"
              : "border-transparent text-gray-400 hover:text-gray-200"
          }`}
        >
          <FiTarget className="w-4 h-4 text-purple-400" />
          🎯 Préparation Entretien
        </button>
      </div>
    </>
  );
}
