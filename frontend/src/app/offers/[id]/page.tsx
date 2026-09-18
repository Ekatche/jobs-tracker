"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  jobOffersApi,
  type JobOffer,
  type OfferEvaluation,
  type RequirementMatch,
  type MissingRequirement,
} from "@/lib/api";
import {
  FiArrowLeft,
  FiBriefcase,
  FiMapPin,
  FiCalendar,
  FiExternalLink,
  FiCheckCircle,
  FiAlertTriangle,
  FiXCircle,
  FiRefreshCw,
  FiShield,
  FiPlus,
  FiZap,
  FiFileText,
  FiAward,
  FiInfo,
  FiTarget,
} from "react-icons/fi";
import NewApplicationModal, {
  PrefilledData,
} from "@/components/dashboard/NewApplicationModal";
import InterviewPrepTab from "@/components/interview/InterviewPrepTab";

export default function OfferDetailPage() {
  const params = useParams();
  const router = useRouter();
  const offerId = params?.id as string;

  const [offer, setOffer] = useState<JobOffer | null>(null);
  const [evaluation, setEvaluation] = useState<OfferEvaluation | null>(null);
  const [loading, setLoading] = useState(true);
  const [evaluating, setEvaluating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"matching" | "analysis" | "job" | "interview">("matching");

  // Modal application
  const [isApplyModalOpen, setIsApplyModalOpen] = useState(false);
  const [prefilledData, setPrefilledData] = useState<PrefilledData | undefined>(undefined);

  const loadOfferAndEvaluation = useCallback(async () => {
    if (!offerId) return;
    setLoading(true);
    setError(null);

    try {
      // 1. Charger l'offre
      const offerData = await jobOffersApi.getById(offerId);
      setOffer(offerData);

      // 2. Charger l'évaluation existante (si déjà évaluée)
      try {
        const evalData = await jobOffersApi.getEvaluation(offerId);
        setEvaluation(evalData);
      } catch (evalErr: unknown) {
        // 404 signifie simplement non encore évaluée pour cet utilisateur
        const status =
          evalErr && typeof evalErr === "object" && "status" in evalErr
            ? (evalErr as { status: number }).status
            : null;
        if (status !== 404) {
          console.log("Évaluation non existante ou non disponible:", evalErr);
        }
      }
    } catch (err: unknown) {
      console.error("Erreur lors du chargement de l'offre:", err);
      const msg =
        err instanceof Error
          ? err.message
          : "Impossible de charger cette offre d'emploi.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [offerId]);

  useEffect(() => {
    loadOfferAndEvaluation();
    if (typeof window !== "undefined") {
      const urlParams = new URLSearchParams(window.location.search);
      if (urlParams.get("tab") === "interview") {
        setActiveTab("interview");
      }
    }
  }, [loadOfferAndEvaluation]);

  // Déclencher l'évaluation Two-Pass
  const handleTriggerEvaluation = async () => {
    if (!offerId || evaluating) return;
    setEvaluating(true);
    setError(null);

    try {
      const result = await jobOffersApi.evaluate(offerId);
      setEvaluation(result);
      // Mettre à jour l'offre avec le nouveau score
      setOffer((prev) =>
        prev
          ? {
              ...prev,
              evaluation_score: result.score,
              pipeline_stage: result.pipeline_stage,
            }
          : prev
      );
    } catch (err: unknown) {
      console.error("Erreur lors de l'évaluation:", err);
      const detail =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : null;
      const msg =
        detail ||
        (err instanceof Error
          ? err.message
          : "Une erreur est survenue lors de l'évaluation IA de l'offre.");
      setError(msg);
    } finally {
      setEvaluating(false);
    }
  };

  const handleOpenApplyModal = () => {
    if (!offer) return;
    const data: PrefilledData = {
      company: offer.entreprise,
      position: offer.poste,
      location: offer.localisation,
      url: offer.url,
      offer_id: offer.id,
      description:
        offer.description && offer.description !== "Non spécifié"
          ? offer.description
          : undefined,
    };
    setPrefilledData(data);
    setIsApplyModalOpen(true);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-blue-night text-white p-8 flex flex-col items-center justify-center">
        <div className="flex items-center gap-3 text-blue-400">
          <FiRefreshCw className="w-6 h-6 animate-spin" />
          <span className="text-lg font-medium">Chargement de l'offre...</span>
        </div>
      </div>
    );
  }

  if (error && !offer) {
    return (
      <div className="min-h-screen bg-blue-night text-white p-8 max-w-4xl mx-auto">
        <Link
          href="/offers"
          className="inline-flex items-center gap-2 text-blue-400 hover:text-blue-300 mb-6 transition-colors"
        >
          <FiArrowLeft className="w-4 h-4" />
          Retour aux offres
        </Link>
        <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-6 text-rose-300">
          <div className="flex items-center gap-3 font-semibold text-lg mb-2">
            <FiAlertTriangle className="w-6 h-6 flex-shrink-0" />
            Erreur
          </div>
          <p className="text-sm">{error}</p>
        </div>
      </div>
    );
  }

  if (!offer) return null;

  const score = evaluation ? evaluation.score : offer.evaluation_score;

  const getScoreColor = (s: number | undefined | null) => {
    if (!s) return "text-gray-400 border-gray-700 bg-gray-800/40";
    if (s >= 4.0) return "text-emerald-400 border-emerald-500/40 bg-emerald-500/10";
    if (s >= 3.0) return "text-amber-400 border-amber-500/40 bg-amber-500/10";
    return "text-rose-400 border-rose-500/40 bg-rose-500/10";
  };

  const getWeightBadge = (weight: "critical" | "high" | "meaningful") => {
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
  };

  return (
    <div className="min-h-screen bg-blue-night text-white pb-16">
      {/* Navigation supérieure */}
      <div className="border-b border-gray-800 bg-blue-night-lighter/50 backdrop-blur sticky top-0 z-30">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <Link
            href="/offers"
            className="inline-flex items-center gap-2 text-gray-300 hover:text-white transition-colors text-sm font-medium"
          >
            <FiArrowLeft className="w-4 h-4" />
            Retour aux offres
          </Link>

          <div className="flex items-center gap-3">
            <button
              onClick={handleTriggerEvaluation}
              disabled={evaluating}
              className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 text-white text-sm font-medium transition-colors shadow-sm"
              title="Lancer ou rafraîchir l'évaluation Two-Pass de cette offre"
            >
              <FiRefreshCw className={`w-4 h-4 ${evaluating ? "animate-spin" : ""}`} />
              {evaluating
                ? "Évaluation en cours..."
                : evaluation
                ? "Ré-évaluer"
                : "Évaluer l'offre"}
            </button>

            <Link
              href={`/resumes?generate_offer_id=${offerId}`}
              className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-colors shadow-sm"
              title="Générer un CV adapté sur-mesure pour cette offre"
            >
              <FiFileText className="w-4 h-4" />
              <span>CV Adapté</span>
            </Link>

            <button
              onClick={handleOpenApplyModal}
              className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-green-600 hover:bg-green-500 text-white text-sm font-medium transition-colors shadow-sm"
            >
              <FiPlus className="w-4 h-4" />
              Postuler
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 pt-6">
        {/* Bannière Erreur éventuelle */}
        {error && (
          <div className="mb-6 bg-rose-500/10 border border-rose-500/30 rounded-xl p-4 text-rose-300 flex items-center gap-3 text-sm">
            <FiAlertTriangle className="w-5 h-5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Fiche d'En-tête de l'Offre */}
        <div className="bg-blue-night-lighter rounded-2xl p-6 md:p-8 border border-gray-700/70 shadow-xl mb-8">
          <div className="flex flex-col md:flex-row md:items-start justify-between gap-6">
            <div className="flex-1">
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <span className="px-2.5 py-1 bg-blue-500/20 text-blue-300 text-xs font-medium rounded-full border border-blue-500/30">
                  {offer.pipeline_stage || "discovered"}
                </span>
                {offer.type_contrat && (
                  <span className="px-2.5 py-1 bg-gray-700/50 text-gray-300 text-xs font-medium rounded-full border border-gray-600/40">
                    {offer.type_contrat}
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
                  <span className="text-emerald-400 font-medium">
                    {offer.salaire}
                  </span>
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
                  Consulter l'annonce originale sur le site source
                </a>
              )}
            </div>

            {/* Score Hero Card */}
            <div className="flex md:flex-col items-center md:items-end justify-between border-t md:border-t-0 border-gray-700/60 pt-4 md:pt-0">
              <div
                className={`flex flex-col items-center justify-center p-4 rounded-2xl border ${getScoreColor(
                  score
                )} min-w-[140px] text-center shadow-lg`}
              >
                <div className="flex items-baseline gap-1">
                  <span className="text-4xl font-extrabold tracking-tight">
                    {score !== undefined && score !== null
                      ? score.toFixed(1)
                      : "—"}
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
                  Score IA Two-Pass calculé selon votre profil
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Section Évaluation IA Two-Pass */}
        {!evaluation ? (
          <div className="bg-gradient-to-r from-blue-900/30 to-indigo-900/20 border border-blue-500/30 rounded-2xl p-8 text-center my-8 shadow-md">
            <div className="w-12 h-12 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center mx-auto mb-4 border border-blue-500/40">
              <FiZap className="w-6 h-6" />
            </div>
            <h2 className="text-xl font-bold text-white mb-2">
              Cette offre n'a pas encore été évaluée
            </h2>
            <p className="text-gray-300 text-sm max-w-xl mx-auto mb-6">
              L'évaluation Two-Pass analyse d'abord les exigences réelles et la viabilité
              de l'offre sans a priori, puis confronte minutieusement vos compétences et
              votre profil avec des citations textuelles exactes.
            </p>
            <button
              onClick={handleTriggerEvaluation}
              disabled={evaluating}
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 text-white font-semibold shadow-lg hover:shadow-blue-500/25 transition-all text-sm"
            >
              <FiRefreshCw className={`w-4 h-4 ${evaluating ? "animate-spin" : ""}`} />
              {evaluating ? "Analyse Two-Pass en cours..." : "Lancer l'évaluation complète"}
            </button>
          </div>
        ) : (
          <div>
            {/* Drapeaux rouges Bloc A (s'il y en a) */}
            {(evaluation.bloc_a.geo_mismatch ||
              evaluation.bloc_a.visa_sponsoring_refused ||
              (evaluation.bloc_a.red_flags && evaluation.bloc_a.red_flags.length > 0)) && (
              <div className="bg-rose-500/10 border border-rose-500/30 rounded-2xl p-5 mb-6 text-rose-200">
                <div className="flex items-center gap-2.5 font-bold text-rose-400 mb-2">
                  <FiAlertTriangle className="w-5 h-5 flex-shrink-0" />
                  Drapeaux rouges identifiés (Bloc A)
                </div>
                <ul className="list-disc list-inside space-y-1 text-sm pl-2">
                  {evaluation.bloc_a.geo_mismatch && (
                    <li>Incompatibilité géographique ou de télétravail sévère.</li>
                  )}
                  {evaluation.bloc_a.visa_sponsoring_refused && (
                    <li>Sponsoring de visa non assuré par l'entreprise.</li>
                  )}
                  {evaluation.bloc_a.red_flags?.map((flag, idx) => (
                    <li key={idx}>{flag}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Onglets de Navigation de l'Analyse */}
            <div className="flex border-b border-gray-700/80 mb-6 gap-2">
              <button
                onClick={() => setActiveTab("matching")}
                className={`px-4 py-2.5 text-sm font-semibold flex items-center gap-2 border-b-2 transition-colors ${
                  activeTab === "matching"
                    ? "border-blue-500 text-blue-400"
                    : "border-transparent text-gray-400 hover:text-gray-200"
                }`}
              >
                <FiAward className="w-4 h-4" />
                Adéquation Exigences (Bloc B)
                <span className="ml-1 text-xs px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300">
                  {evaluation.bloc_b.matched_requirements.length}
                </span>
              </button>

              <button
                onClick={() => setActiveTab("analysis")}
                className={`px-4 py-2.5 text-sm font-semibold flex items-center gap-2 border-b-2 transition-colors ${
                  activeTab === "analysis"
                    ? "border-blue-500 text-blue-400"
                    : "border-transparent text-gray-400 hover:text-gray-200"
                }`}
              >
                <FiShield className="w-4 h-4" />
                Stratégie & Intégrité (Blocs A & G)
              </button>

              <button
                onClick={() => setActiveTab("job")}
                className={`px-4 py-2.5 text-sm font-semibold flex items-center gap-2 border-b-2 transition-colors ${
                  activeTab === "job"
                    ? "border-blue-500 text-blue-400"
                    : "border-transparent text-gray-400 hover:text-gray-200"
                }`}
              >
                <FiFileText className="w-4 h-4" />
                Annonce du Poste
              </button>

              <button
                onClick={() => setActiveTab("interview")}
                className={`px-4 py-2.5 text-sm font-semibold flex items-center gap-2 border-b-2 transition-colors ${
                  activeTab === "interview"
                    ? "border-indigo-500 text-indigo-400"
                    : "border-transparent text-gray-400 hover:text-gray-200"
                }`}
              >
                <FiTarget className="w-4 h-4 text-indigo-400" />
                🎯 Préparation Entretien
              </button>
            </div>

            {/* CONTENU ONGLET 1: MATCHING EXIGENCES (BLOC B) */}
            {activeTab === "matching" && (
              <div className="space-y-6">
                {/* Synthèse du matching */}
                {evaluation.bloc_b.score_justification && (
                  <div className="bg-blue-night-lighter/70 border border-gray-700/70 rounded-xl p-5">
                    <h3 className="text-sm font-semibold text-gray-300 mb-1 flex items-center gap-2">
                      <FiInfo className="text-blue-400" />
                      Justification du Score
                    </h3>
                    <p className="text-sm text-gray-300 leading-relaxed">
                      {evaluation.bloc_b.score_justification}
                    </p>
                  </div>
                )}

                {/* Exigences Validées avec Verbatim */}
                <div>
                  <h3 className="text-base font-bold text-white mb-3 flex items-center gap-2">
                    <FiCheckCircle className="text-emerald-400" />
                    Exigences Remplies & Preuves du Profil (
                    {evaluation.bloc_b.matched_requirements.length})
                  </h3>

                  {evaluation.bloc_b.matched_requirements.length === 0 ? (
                    <p className="text-sm text-gray-400 italic">
                      Aucune exigence formellement validée dans le profil.
                    </p>
                  ) : (
                    <div className="grid grid-cols-1 gap-4">
                      {evaluation.bloc_b.matched_requirements.map(
                        (match: RequirementMatch, idx: number) => (
                          <div
                            key={idx}
                            className="bg-blue-night-lighter rounded-xl p-5 border border-gray-700/60 hover:border-emerald-500/40 transition-colors"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2 mb-2.5">
                              <span className="font-semibold text-white text-base">
                                {match.requirement}
                              </span>
                              <div className="flex items-center gap-2">
                                {getWeightBadge(match.weight)}
                                <span
                                  className={`px-2 py-0.5 rounded text-[11px] font-medium ${
                                    match.status === "full_match"
                                      ? "bg-emerald-500/20 text-emerald-300"
                                      : "bg-amber-500/20 text-amber-300"
                                  }`}
                                >
                                  {match.status === "full_match"
                                    ? "Validé complet"
                                    : "Match partiel"}
                                </span>
                              </div>
                            </div>

                            <div className="text-sm text-gray-300 mb-3 bg-gray-900/40 p-3 rounded-lg border border-gray-800">
                              <span className="text-xs uppercase tracking-wider font-semibold text-gray-400 block mb-1">
                                Preuve dans votre parcours :
                              </span>
                              {match.candidate_evidence}
                            </div>

                            {/* Citation Verbatim de l'Offre */}
                            <div className="bg-blue-950/30 border-l-4 border-blue-500 p-3 rounded-r-lg">
                              <span className="text-[11px] uppercase tracking-wider font-semibold text-blue-400 block mb-1">
                                Citation exacte de l'offre (Verbatim) :
                              </span>
                              <p className="text-xs italic text-gray-300">
                                &laquo; {match.verbatim_quote} &raquo;
                              </p>
                            </div>
                          </div>
                        )
                      )}
                    </div>
                  )}
                </div>

                {/* Exigences Manquantes */}
                {evaluation.bloc_b.missing_requirements &&
                  evaluation.bloc_b.missing_requirements.length > 0 && (
                    <div className="pt-4">
                      <h3 className="text-base font-bold text-white mb-3 flex items-center gap-2">
                        <FiXCircle className="text-rose-400" />
                        Exigences Manquantes ou Non Détectées (
                        {evaluation.bloc_b.missing_requirements.length})
                      </h3>

                      <div className="grid grid-cols-1 gap-4">
                        {evaluation.bloc_b.missing_requirements.map(
                          (missing: MissingRequirement, idx: number) => (
                            <div
                              key={idx}
                              className="bg-blue-night-lighter rounded-xl p-5 border border-rose-500/30 bg-rose-500/5"
                            >
                              <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                                <span className="font-semibold text-white text-base">
                                  {missing.requirement}
                                </span>
                                {getWeightBadge(missing.weight)}
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
            )}

            {/* CONTENU ONGLET 2: STRATÉGIE & INTÉGRITÉ (BLOCS A & G) */}
            {activeTab === "analysis" && (
              <div className="space-y-6">
                {/* Bloc A: Archétype & Résumé exécutif */}
                <div className="bg-blue-night-lighter rounded-xl p-6 border border-gray-700/60 shadow-md">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-base font-bold text-white flex items-center gap-2">
                      <FiBriefcase className="text-blue-400" />
                      Archétype Métier & Vision (Bloc A)
                    </h3>
                    <span className="px-3 py-1 rounded-full text-xs font-semibold bg-blue-500/20 text-blue-300 border border-blue-500/30">
                      {evaluation.bloc_a.archetype}
                    </span>
                  </div>

                  <p className="text-sm text-gray-300 leading-relaxed mb-4">
                    {evaluation.bloc_a.summary}
                  </p>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-3 border-t border-gray-700/60 text-xs">
                    <div className="flex items-center gap-2 text-gray-300">
                      <span className="text-gray-400">Géo-adéquation :</span>
                      {evaluation.bloc_a.geo_mismatch ? (
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
                      {evaluation.bloc_a.visa_sponsoring_refused ? (
                        <span className="text-rose-400 font-semibold flex items-center gap-1">
                          <FiXCircle /> Refus explicite
                        </span>
                      ) : (
                        <span className="text-emerald-400 font-semibold flex items-center gap-1">
                          <FiCheckCircle /> Pas de refus explicite
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Bloc G: Viabilité & Détection Ghost Job / Scam */}
                <div className="bg-blue-night-lighter rounded-xl p-6 border border-gray-700/60 shadow-md">
                  <h3 className="text-base font-bold text-white flex items-center gap-2 mb-4">
                    <FiShield className="text-emerald-400" />
                    Viabilité de l'Offre & Signaux d'Intégrité (Bloc G)
                  </h3>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
                    <div className="p-4 rounded-xl bg-gray-900/40 border border-gray-800">
                      <span className="text-xs text-gray-400 block mb-1">
                        Suspicion d'Offre Fantôme (Ghost Job) :
                      </span>
                      {evaluation.bloc_g.is_ghost_job ? (
                        <span className="text-rose-400 font-bold text-sm flex items-center gap-1.5">
                          <FiAlertTriangle /> Risque élevé
                        </span>
                      ) : (
                        <span className="text-emerald-400 font-bold text-sm flex items-center gap-1.5">
                          <FiCheckCircle /> Offre active et crédible
                        </span>
                      )}
                    </div>

                    <div className="p-4 rounded-xl bg-gray-900/40 border border-gray-800">
                      <span className="text-xs text-gray-400 block mb-1">
                        Risque d'Arnaque ou Faux Recrutement :
                      </span>
                      {evaluation.bloc_g.is_scam_risk ? (
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

                  {evaluation.bloc_g.warnings && evaluation.bloc_g.warnings.length > 0 && (
                    <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg">
                      <span className="text-xs font-semibold text-amber-300 block mb-1">
                        Points d'attention notés :
                      </span>
                      <ul className="list-disc list-inside text-xs text-amber-200/90 space-y-1">
                        {evaluation.bloc_g.warnings.map((warn, i) => (
                          <li key={i}>{warn}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* CONTENU ONGLET 3: ANNONCE DU POSTE */}
            {activeTab === "job" && (
              <div className="bg-blue-night-lighter rounded-xl p-6 border border-gray-700/60 shadow-md">
                <h3 className="text-base font-bold text-white mb-4">
                  Description du Poste
                </h3>

                {offer.competences_cles && offer.competences_cles.length > 0 && (
                  <div className="mb-6">
                    <span className="text-xs text-gray-400 uppercase font-semibold block mb-2">
                      Compétences identifiées :
                    </span>
                    <div className="flex flex-wrap gap-2">
                      {offer.competences_cles.map((comp, i) => (
                        <span
                          key={i}
                          className="px-2.5 py-1 rounded bg-gray-800 text-gray-200 text-xs font-medium border border-gray-700"
                        >
                          {comp}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                <div className="prose prose-invert max-w-none text-sm text-gray-300 leading-relaxed whitespace-pre-line">
                  {offer.description || "Aucune description détaillée disponible."}
                </div>
              </div>
            )}

            {/* CONTENU ONGLET 4: PRÉPARATION D'ENTRETIEN (PHASE 6) */}
            {activeTab === "interview" && (
              <InterviewPrepTab
                offerId={offerId}
                targetRole={offer.poste}
                targetCompany={offer.entreprise}
              />
            )}
          </div>
        )}
      </div>

      {/* Modal Candidature */}
      <NewApplicationModal
        isOpen={isApplyModalOpen}
        onClose={() => setIsApplyModalOpen(false)}
        onSuccess={() => {
          setIsApplyModalOpen(false);
          router.push("/applications");
        }}
        prefilledData={prefilledData}
      />
    </div>
  );
}
