"use client";

import { Suspense } from "react";
import Link from "next/link";
import { FiArrowLeft, FiAlertTriangle, FiRefreshCw, FiZap } from "react-icons/fi";
import NewApplicationModal from "@/components/dashboard/NewApplicationModal";
import InterviewPrepTab from "@/components/interview/InterviewPrepTab";
import { useOfferDetail } from "@/hooks/useOfferDetail";
import OfferDetailHeader from "@/components/offers/detail/OfferDetailHeader";
import OfferDetailTopBar from "@/components/offers/detail/OfferDetailTopBar";
import OfferMatchingTab from "@/components/offers/detail/OfferMatchingTab";
import OfferAnalysisTab from "@/components/offers/detail/OfferAnalysisTab";

function OfferDetailLoadingFallback() {
  return (
    <div className="min-h-screen bg-blue-night text-white p-8 flex flex-col items-center justify-center">
      <div className="flex items-center gap-3 text-blue-400">
        <FiRefreshCw className="w-6 h-6 animate-spin" />
        <span className="text-lg font-medium">Chargement de l&apos;offre...</span>
      </div>
    </div>
  );
}

function OfferDetailPageContent() {
  const {
    offerId,
    returnUrl,
    offer,
    evaluation,
    loading,
    evaluating,
    error,
    activeTab,
    setActiveTab,
    isApplyModalOpen,
    setIsApplyModalOpen,
    prefilledData,
    handleBackToOffers,
    handleTriggerEvaluation,
    handleOpenApplyModal,
    navigateToApplications,
  } = useOfferDetail();

  if (loading) return <OfferDetailLoadingFallback />;

  if (error && !offer) {
    return (
      <div className="min-h-screen bg-blue-night text-white p-8 max-w-4xl mx-auto">
        <Link
          href={returnUrl}
          onClick={handleBackToOffers}
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

  return (
    <div className="min-h-screen bg-blue-night text-white pb-16">
      <OfferDetailTopBar
        offerId={offerId}
        returnUrl={returnUrl}
        hasEvaluation={Boolean(evaluation)}
        evaluating={evaluating}
        activeTab={activeTab}
        onBackToOffers={handleBackToOffers}
        onTriggerEvaluation={handleTriggerEvaluation}
        onSelectTab={setActiveTab}
        onOpenApplyModal={handleOpenApplyModal}
      />

      <div className="max-w-6xl mx-auto px-4 pt-6">
        <OfferDetailHeader
          offer={offer}
          evaluation={evaluation}
          error={error}
          activeTab={activeTab}
          onSelectTab={setActiveTab}
        />

        {!evaluation && (activeTab === "matching" || activeTab === "analysis") && (
          <div className="bg-gradient-to-r from-blue-900/30 to-indigo-900/20 border border-blue-500/30 rounded-2xl p-8 text-center my-8 shadow-md">
            <div className="w-12 h-12 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center mx-auto mb-4 border border-blue-500/40">
              <FiZap className="w-6 h-6" />
            </div>
            <h2 className="text-xl font-bold text-white mb-2">
              Cette offre n&apos;a pas encore été évaluée
            </h2>
            <p className="text-gray-300 text-sm max-w-xl mx-auto mb-6">
              L&apos;évaluation d&apos;adéquation analyse minutieusement les exigences réelles et la
              viabilité du poste, puis les confronte avec vos compétences et réalisations exactes.
            </p>
            <button
              onClick={handleTriggerEvaluation}
              disabled={evaluating}
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 text-white font-semibold shadow-lg hover:shadow-blue-500/25 transition-all text-sm"
            >
              <FiRefreshCw className={`w-4 h-4 ${evaluating ? "animate-spin" : ""}`} />
              {evaluating ? "Analyse d'adéquation en cours..." : "Lancer l'évaluation complète"}
            </button>
          </div>
        )}

        {activeTab === "job" && (
          <div className="bg-blue-night-lighter rounded-xl p-6 border border-gray-700/60 shadow-md mb-6">
            <h3 className="text-base font-bold text-white mb-4">Description du Poste</h3>

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

        {evaluation && activeTab === "matching" && (
          <OfferMatchingTab evaluation={evaluation} />
        )}

        {evaluation && activeTab === "analysis" && (
          <OfferAnalysisTab evaluation={evaluation} />
        )}

        {activeTab === "interview" && (
          <InterviewPrepTab
            offerId={offerId}
            targetRole={offer.poste}
            targetCompany={offer.entreprise}
          />
        )}
      </div>

      <NewApplicationModal
        isOpen={isApplyModalOpen}
        onClose={() => setIsApplyModalOpen(false)}
        onSuccess={() => {
          setIsApplyModalOpen(false);
          navigateToApplications();
        }}
        prefilledData={prefilledData}
      />
    </div>
  );
}

export default function OfferDetailPage() {
  return (
    <Suspense fallback={<OfferDetailLoadingFallback />}>
      <OfferDetailPageContent />
    </Suspense>
  );
}
