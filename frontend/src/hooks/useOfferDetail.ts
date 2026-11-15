"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { jobOffersApi, type JobOffer, type OfferEvaluation } from "@/lib/api";
import { type PrefilledData } from "@/components/dashboard/NewApplicationModal";

export type OfferDetailTab = "matching" | "analysis" | "job" | "interview";

/**
 * Manages loading, Two-Pass AI evaluation, tab selection, and apply modal state for an offer.
 */
export function useOfferDetail() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const offerId = params?.id as string;

  const returnPage = searchParams.get("page");
  const returnUrl = returnPage ? `/offers?page=${returnPage}` : "/offers";

  const [offer, setOffer] = useState<JobOffer | null>(null);
  const [evaluation, setEvaluation] = useState<OfferEvaluation | null>(null);
  const [loading, setLoading] = useState(true);
  const [evaluating, setEvaluating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<OfferDetailTab>("job");
  const [isApplyModalOpen, setIsApplyModalOpen] = useState(false);
  const [prefilledData, setPrefilledData] = useState<PrefilledData | undefined>(undefined);

  const handleBackToOffers = (e: React.MouseEvent) => {
    e.preventDefault();
    if (typeof window !== "undefined" && window.history.length > 1) {
      router.back();
    } else {
      router.push(returnUrl);
    }
  };

  const loadOfferAndEvaluation = useCallback(async () => {
    if (!offerId) return;
    setLoading(true);
    setError(null);

    try {
      const offerData = await jobOffersApi.getById(offerId);
      setOffer(offerData);

      try {
        const evalData = await jobOffersApi.getEvaluation(offerId);
        setEvaluation(evalData);
      } catch (evalErr: unknown) {
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

  const handleTriggerEvaluation = async () => {
    if (!offerId || evaluating) return;
    setEvaluating(true);
    setError(null);

    try {
      const result = await jobOffersApi.evaluate(offerId);
      setEvaluation(result);
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
    setPrefilledData({
      company: offer.entreprise,
      position: offer.poste,
      location: offer.localisation,
      url: offer.url,
      offer_id: offer.id,
      description:
        offer.description && offer.description !== "Non spécifié"
          ? offer.description
          : undefined,
    });
    setIsApplyModalOpen(true);
  };

  return {
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
    navigateToApplications: () => router.push("/applications"),
  };
}
