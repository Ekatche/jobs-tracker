"use client";

import type {
  OfferEvaluation,
  RequirementMatch,
  MissingRequirement,
} from "@/lib/api";
import { EvidenceTierBadge } from "@/components/offers/OfferEvaluationExtras";
import {
  FiCheckCircle,
  FiAlertTriangle,
  FiXCircle,
  FiInfo,
} from "react-icons/fi";

function WeightBadge({ weight }: { weight: "critical" | "high" | "meaningful" }) {
  switch (weight) {
    case "critical":
      return (
        <span className="px-2 py-0.5 rounded text-[11px] font-semibold uppercase tracking-wider bg-rose-500/20 text-rose-300 border border-rose-500/30">
          Critique
        </span>
      );
    case "high":
      return (
        <span className="px-2 py-0.5 rounded text-[11px] font-semibold uppercase tracking-wider bg-blue-500/20 text-blue-300 border border-blue-500/30">
          Important
        </span>
      );
    case "meaningful":
    default:
      return (
        <span className="px-2 py-0.5 rounded text-[11px] font-semibold uppercase tracking-wider bg-gray-600/30 text-gray-300 border border-gray-600/30">
          Secondaire
        </span>
      );
  }
}

export default function OfferMatchingTab({
  evaluation,
}: {
  evaluation: OfferEvaluation;
}) {
  const { bloc_b } = evaluation;

  return (
    <div className="space-y-6">
      {bloc_b.score_justification && (
        <div className="bg-blue-night-lighter/70 border border-gray-700/70 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-300 mb-1 flex items-center gap-2">
            <FiInfo className="text-blue-400" />
            Justification du Score
          </h3>
          <p className="text-sm text-gray-300 leading-relaxed">
            {bloc_b.score_justification}
          </p>
          {(bloc_b.dropped_requirements_count ?? 0) > 0 && (
            <p className="mt-2.5 text-xs text-amber-300 bg-amber-500/10 border border-amber-500/25 rounded-lg px-3 py-1.5 inline-block">
              {bloc_b.dropped_requirements_count} critère(s) sans citation vérifiable dans
              l&apos;offre ont été écartés par le garde anti-hallucination.
            </p>
          )}
        </div>
      )}

      <div>
        <h3 className="text-base font-bold text-white mb-3 flex items-center gap-2">
          <FiCheckCircle className="text-emerald-400" />
          Exigences Remplies & Preuves du Profil ({bloc_b.matched_requirements.length})
        </h3>

        {bloc_b.matched_requirements.length === 0 ? (
          <p className="text-sm text-gray-400 italic">
            Aucune exigence formellement validée dans le profil.
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {bloc_b.matched_requirements.map((match: RequirementMatch, idx: number) => (
              <div
                key={idx}
                className="bg-blue-night-lighter rounded-xl p-5 border border-gray-700/60 hover:border-emerald-500/40 transition-colors"
              >
                <div className="flex flex-wrap items-center justify-between gap-2 mb-2.5">
                  <span className="font-semibold text-white text-base">
                    {match.requirement}
                  </span>
                  <div className="flex items-center gap-2">
                    <EvidenceTierBadge tier={match.importance_evidence_tier} />
                    <WeightBadge weight={match.weight} />
                    <span
                      className={`px-2 py-0.5 rounded text-[11px] font-medium ${
                        match.status === "full_match"
                          ? "bg-emerald-500/20 text-emerald-300"
                          : "bg-amber-500/20 text-amber-300"
                      }`}
                    >
                      {match.status === "full_match" ? "Validé complet" : "Match partiel"}
                    </span>
                  </div>
                </div>

                <div className="text-sm text-gray-300 mb-3 bg-gray-900/40 p-3 rounded-lg border border-gray-800">
                  <span className="text-xs uppercase tracking-wider font-semibold text-gray-400 block mb-1">
                    Preuve dans votre parcours :
                  </span>
                  {match.candidate_evidence}
                </div>

                <div className="bg-blue-950/30 border-l-4 border-blue-500 p-3 rounded-r-lg">
                  <span className="text-[11px] uppercase tracking-wider font-semibold text-blue-400 block mb-1">
                    Citation exacte de l&apos;offre (Verbatim) :
                  </span>
                  <p className="text-xs italic text-gray-300">
                    &laquo; {match.verbatim_quote} &raquo;
                  </p>
                  {match.quote_verified === false && (
                    <p className="text-[11px] text-amber-300 mt-1.5 flex items-center gap-1">
                      <FiAlertTriangle /> Citation introuvable telle quelle dans l&apos;offre : à vérifier
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {bloc_b.missing_requirements && bloc_b.missing_requirements.length > 0 && (
        <div className="pt-4">
          <h3 className="text-base font-bold text-white mb-3 flex items-center gap-2">
            <FiXCircle className="text-rose-400" />
            Exigences Manquantes ou Non Détectées ({bloc_b.missing_requirements.length})
          </h3>

          <div className="grid grid-cols-1 gap-4">
            {bloc_b.missing_requirements.map(
              (missing: MissingRequirement, idx: number) => (
                <div
                  key={idx}
                  className="bg-blue-night-lighter rounded-xl p-5 border border-rose-500/30 bg-rose-500/5"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                    <span className="font-semibold text-white text-base">
                      {missing.requirement}
                    </span>
                    <div className="flex items-center gap-2">
                      <EvidenceTierBadge tier={missing.importance_evidence_tier} />
                      <WeightBadge weight={missing.weight} />
                    </div>
                  </div>

                  <p className="text-sm text-gray-300 mb-2">
                    <span className="text-xs uppercase tracking-wider font-semibold text-gray-400 block">
                      Constat :
                    </span>
                    {missing.reason}
                  </p>

                  {missing.impact_on_role && (
                    <p className="text-xs text-rose-300/90 italic">
                      Impact attendu : {missing.impact_on_role}
                    </p>
                  )}
                </div>
              )
            )}
          </div>
        </div>
      )}
    </div>
  );
}
