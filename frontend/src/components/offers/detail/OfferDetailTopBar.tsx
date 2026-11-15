"use client";

import Link from "next/link";
import type { OfferDetailTab } from "@/hooks/useOfferDetail";
import {
  FiArrowLeft,
  FiRefreshCw,
  FiPlus,
  FiFileText,
  FiTarget,
} from "react-icons/fi";

interface OfferDetailTopBarProps {
  offerId: string;
  returnUrl: string;
  hasEvaluation: boolean;
  evaluating: boolean;
  activeTab: OfferDetailTab;
  onBackToOffers: (e: React.MouseEvent) => void;
  onTriggerEvaluation: () => void;
  onSelectTab: (tab: OfferDetailTab) => void;
  onOpenApplyModal: () => void;
}

export default function OfferDetailTopBar({
  offerId,
  returnUrl,
  hasEvaluation,
  evaluating,
  activeTab,
  onBackToOffers,
  onTriggerEvaluation,
  onSelectTab,
  onOpenApplyModal,
}: OfferDetailTopBarProps) {
  return (
    <div className="border-b border-gray-800 bg-blue-night-lighter/50 backdrop-blur sticky top-0 z-30">
      <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
        <Link
          href={returnUrl}
          onClick={onBackToOffers}
          className="inline-flex items-center gap-2 text-gray-300 hover:text-white transition-colors text-sm font-medium"
        >
          <FiArrowLeft className="w-4 h-4" />
          Retour aux offres
        </Link>

        <div className="flex items-center gap-3">
          <button
            onClick={onTriggerEvaluation}
            disabled={evaluating}
            className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 text-white text-sm font-medium transition-colors shadow-sm"
            title="Lancer ou rafraîchir l'évaluation Two-Pass de cette offre"
          >
            <FiRefreshCw className={`w-4 h-4 ${evaluating ? "animate-spin" : ""}`} />
            {evaluating
              ? "Évaluation en cours..."
              : hasEvaluation
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
            onClick={() => onSelectTab("interview")}
            className={`inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-sm font-medium transition-colors shadow-sm ${
              activeTab === "interview"
                ? "bg-purple-600 text-white shadow-purple-500/20"
                : "bg-purple-900/40 hover:bg-purple-800/60 text-purple-200 border border-purple-500/30"
            }`}
            title="Préparer l'entretien (STAR+R, packs d'audience, questions)"
          >
            <FiTarget className="w-4 h-4" />
            <span>Entretien</span>
          </button>

          <button
            onClick={onOpenApplyModal}
            className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-green-600 hover:bg-green-500 text-white text-sm font-medium transition-colors shadow-sm"
          >
            <FiPlus className="w-4 h-4" />
            Postuler
          </button>
        </div>
      </div>
    </div>
  );
}
