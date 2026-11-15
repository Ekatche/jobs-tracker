"use client";

import React from "react";
import { FiRefreshCw, FiAlertCircle } from "react-icons/fi";

interface ActionStateProps {
  isPending: boolean;
  onRegenerate: () => void;
}

/** Loading skeleton shown while fetching initial cover letter data. */
export function CoverLetterLoadingState() {
  return (
    <div className="mt-6 border border-gray-700/60 rounded-xl p-5 bg-gray-800/50 flex items-center gap-3 text-sm text-gray-400 animate-pulse">
      <FiRefreshCw className="animate-spin text-blue-400" />
      <span>Chargement de la lettre de motivation...</span>
    </div>
  );
}

/** Empty state inviting the user to generate a tailored cover letter. */
export function CoverLetterEmptyState({ isPending, onRegenerate }: ActionStateProps) {
  return (
    <div className="mt-6 border border-gray-700/60 rounded-xl p-5 bg-gray-800/60 shadow-lg backdrop-blur-sm">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h3 className="text-base font-semibold text-white flex items-center gap-2">
            <span>Lettre de motivation</span>
          </h3>
          <p className="text-xs text-gray-400 mt-1 max-w-md">
            Génération sur-mesure basée sur votre profil candidat (CV, projets, compétences) et analysée par un critique multi-modèles.
          </p>
        </div>
        <button
          type="button"
          onClick={onRegenerate}
          disabled={isPending}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-60 text-white rounded-lg text-xs font-medium flex items-center justify-center gap-2 transition-all shadow-md hover:shadow-blue-600/20 whitespace-nowrap self-start sm:self-auto"
        >
          <FiRefreshCw className={isPending ? "animate-spin" : ""} />
          <span>{isPending ? "Rédaction en cours..." : "Rédiger une lettre"}</span>
        </button>
      </div>
    </div>
  );
}

interface PendingStateProps {
  pollingTimeout: boolean;
  onRegenerate: () => void;
}

/** Progress state displayed while the multi-agent cover letter pipeline runs. */
export function CoverLetterPendingState({
  pollingTimeout,
  onRegenerate,
}: PendingStateProps) {
  return (
    <div className="mt-6 p-5 rounded-xl bg-blue-950/30 border border-blue-500/40 text-blue-200 flex flex-col gap-3 shadow-lg">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-blue-600/20 text-blue-400 border border-blue-500/30">
          <FiRefreshCw className="animate-spin text-lg" />
        </div>
        <div>
          <h4 className="text-sm font-semibold text-white">
            Rédaction de votre lettre en cours...
          </h4>
          <p className="text-xs text-blue-300/80 mt-0.5">
            CrewAI analyse l&apos;offre, sélectionne vos réalisations et affine le texte.
          </p>
        </div>
      </div>

      {pollingTimeout && (
        <div className="text-xs text-amber-300 bg-amber-950/40 p-3 rounded-lg border border-amber-800/50 mt-1 flex items-center justify-between gap-2">
          <span>La génération prend un peu plus de temps que prévu.</span>
          <button
            onClick={onRegenerate}
            className="px-2.5 py-1 bg-amber-600 hover:bg-amber-500 text-white rounded text-xs font-medium"
          >
            Relancer
          </button>
        </div>
      )}
    </div>
  );
}

interface FailedStateProps extends ActionStateProps {
  error?: string | null;
}

/** Error state shown when cover letter generation fails. */
export function CoverLetterFailedState({
  error,
  isPending,
  onRegenerate,
}: FailedStateProps) {
  const isCreditOrQuotaError =
    error?.includes("Crédits épuisés") ||
    error?.includes("quota") ||
    error?.includes("Rate Limit");

  return (
    <div className="mt-6 p-5 rounded-xl bg-red-950/30 border border-red-500/40 text-red-200 flex flex-col gap-3 shadow-lg">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <FiAlertCircle className="text-red-400 text-lg mt-0.5 shrink-0" />
          <div>
            <p className="font-semibold text-sm text-white">Échec de la rédaction :</p>
            <p className="text-xs text-red-300 mt-1">{error || "Erreur inconnue"}</p>
          </div>
        </div>
        <button
          type="button"
          onClick={onRegenerate}
          disabled={isPending}
          className="px-3 py-1.5 bg-red-800 hover:bg-red-700 disabled:opacity-60 text-white text-xs font-medium rounded-md whitespace-nowrap flex items-center gap-1.5 transition-colors"
        >
          <FiRefreshCw className={isPending ? "animate-spin" : ""} />
          <span>Réessayer</span>
        </button>
      </div>

      {isCreditOrQuotaError && (
        <div className="text-xs text-amber-300/90 bg-amber-950/40 p-2.5 rounded-lg border border-amber-800/40 mt-1">
          💡 Astuce : Vérifiez votre solde sur la console de vos fournisseurs d&apos;API dans la page Profil.
        </div>
      )}
    </div>
  );
}
