"use client";

import type { OfferEvaluation } from "@/lib/api";
import {
  BlocGRiskSummary,
  BlocHDraftPanel,
} from "@/components/offers/OfferEvaluationExtras";
import {
  FiBriefcase,
  FiCheckCircle,
  FiAlertTriangle,
  FiXCircle,
  FiShield,
} from "react-icons/fi";

export default function OfferAnalysisTab({
  evaluation,
}: {
  evaluation: OfferEvaluation;
}) {
  const { bloc_a, bloc_g, bloc_h } = evaluation;

  return (
    <div className="space-y-6">
      <div className="bg-blue-night-lighter rounded-xl p-6 border border-gray-700/60 shadow-md">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-bold text-white flex items-center gap-2">
            <FiBriefcase className="text-blue-400" />
            Archétype Métier & Vision
          </h3>
          <span className="px-3 py-1 rounded-full text-xs font-semibold bg-blue-500/20 text-blue-300 border border-blue-500/30">
            {bloc_a.archetype}
          </span>
        </div>

        <p className="text-sm text-gray-300 leading-relaxed mb-4">{bloc_a.summary}</p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-3 border-t border-gray-700/60 text-xs">
          <div className="flex items-center gap-2 text-gray-300">
            <span className="text-gray-400">Géo-adéquation :</span>
            {bloc_a.geo_mismatch ? (
              <span className="text-rose-400 font-semibold flex items-center gap-1">
                <FiXCircle /> Écart de localisation
              </span>
            ) : (
              <span className="text-emerald-400 font-semibold flex items-center gap-1">
                <FiCheckCircle /> Alignée
              </span>
            )}
          </div>

          <div className="flex items-center gap-2 text-gray-300">
            <span className="text-gray-400">Visa / Autorisation :</span>
            {bloc_a.visa_sponsoring_refused ? (
              <span className="text-rose-400 font-semibold flex items-center gap-1">
                <FiXCircle /> Refus explicite
              </span>
            ) : (
              <span className="text-emerald-400 font-semibold flex items-center gap-1">
                <FiCheckCircle /> Pas de refus explicite
              </span>
            )}
          </div>

          {bloc_a.domain_coherence && (
            <div className="flex items-center gap-2 text-gray-300">
              <span className="text-gray-400">Cohérence métier :</span>
              {bloc_a.domain_coherence === "match" ? (
                <span className="text-emerald-400 font-semibold flex items-center gap-1">
                  <FiCheckCircle /> Même métier
                </span>
              ) : bloc_a.domain_coherence === "partial" ? (
                <span className="text-amber-300 font-semibold flex items-center gap-1">
                  <FiAlertTriangle /> Recoupement partiel
                </span>
              ) : (
                <span className="text-rose-400 font-semibold flex items-center gap-1">
                  <FiXCircle /> Autre métier
                </span>
              )}
            </div>
          )}
        </div>

        {bloc_a.preference_mismatches && bloc_a.preference_mismatches.length > 0 && (
          <div className="mt-4 p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg">
            <span className="text-xs font-semibold text-amber-300 block mb-1">
              Écarts avec vos préférences :
            </span>
            <ul className="list-disc list-inside text-xs text-amber-200/90 space-y-1">
              {bloc_a.preference_mismatches.map((m, i) => (
                <li key={i}>
                  {m.criterion} : {m.offer_value} (attendu : {m.expected})
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="bg-blue-night-lighter rounded-xl p-6 border border-gray-700/60 shadow-md">
        <h3 className="text-base font-bold text-white flex items-center gap-2 mb-4">
          <FiShield className="text-emerald-400" />
          Viabilité de l&apos;Offre & Signaux d&apos;Intégrité
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
          <div className="p-4 rounded-xl bg-gray-900/40 border border-gray-800">
            <span className="text-xs text-gray-400 block mb-1">
              Suspicion d&apos;Offre Fantôme (Ghost Job) :
            </span>
            {bloc_g.is_ghost_job && bloc_g.reposted_frequency ? (
              <span className="text-rose-400 font-bold text-sm flex items-center gap-1.5">
                <FiAlertTriangle /> Risque élevé ({bloc_g.reposted_frequency})
              </span>
            ) : bloc_g.is_ghost_job ? (
              <span className="text-amber-300 font-bold text-sm flex items-center gap-1.5">
                <FiAlertTriangle /> Soupçon non corroboré
              </span>
            ) : (
              <span className="text-emerald-400 font-bold text-sm flex items-center gap-1.5">
                <FiCheckCircle /> Offre active et crédible
              </span>
            )}
          </div>

          <div className="p-4 rounded-xl bg-gray-900/40 border border-gray-800">
            <span className="text-xs text-gray-400 block mb-1">
              Risque d&apos;Arnaque ou Faux Recrutement :
            </span>
            {bloc_g.is_scam_risk ? (
              <span className="text-rose-400 font-bold text-sm flex items-center gap-1.5">
                <FiAlertTriangle /> Signal suspect détecté
              </span>
            ) : (
              <span className="text-emerald-400 font-bold text-sm flex items-center gap-1.5">
                <FiCheckCircle /> Aucun signal suspect
              </span>
            )}
          </div>
        </div>

        {bloc_g.warnings && bloc_g.warnings.length > 0 && (
          <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg">
            <span className="text-xs font-semibold text-amber-300 block mb-1">
              Points d&apos;attention notés :
            </span>
            <ul className="list-disc list-inside text-xs text-amber-200/90 space-y-1">
              {bloc_g.warnings.map((warn, i) => (
                <li key={i}>{warn}</li>
              ))}
            </ul>
          </div>
        )}

        <BlocGRiskSummary blocG={bloc_g} />
      </div>

      <BlocHDraftPanel blocH={bloc_h} />
    </div>
  );
}
