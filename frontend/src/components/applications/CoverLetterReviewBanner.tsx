"use client";

import React from "react";
import { CoverLetterVersion } from "@/types/coverLetter";
import {
  FiAlertCircle,
  FiEdit3,
  FiChevronDown,
  FiChevronUp,
  FiCheckCircle,
} from "react-icons/fi";

interface ReviewBannerProps {
  needsReview: boolean;
  reviewViolations: string[];
  viewMode: "preview" | "edit";
  confirmingExport: boolean;
  isDirty: boolean;
  downloadingPdf: boolean;
  exportError: string | null;
  onStartFix: () => void;
  onCancelExportConfirm: () => void;
  onForceExportPdf: () => void;
}

/**
 * Displays guard violations requiring review, force-export confirmation, and PDF export errors.
 */
export function CoverLetterReviewBanner({
  needsReview,
  reviewViolations,
  viewMode,
  confirmingExport,
  isDirty,
  downloadingPdf,
  exportError,
  onStartFix,
  onCancelExportConfirm,
  onForceExportPdf,
}: ReviewBannerProps) {
  return (
    <>
      {needsReview && (
        <div
          role="alert"
          className="p-4 sm:p-5 border-b border-amber-700/50 bg-amber-950/30 text-amber-200 space-y-3"
        >
          <div className="flex items-start gap-3">
            <FiAlertCircle className="text-amber-400 text-lg mt-0.5 shrink-0" />
            <div className="space-y-1.5">
              <p className="text-sm font-semibold text-white">
                Cette lettre doit être relue avant envoi
              </p>
              <p className="text-xs text-amber-300/90">
                Les contrôles qualité détectent encore des points à corriger. Modifiez le texte
                ou améliorez un passage ciblé : le contrôle est refait à l&apos;enregistrement.
              </p>
              {reviewViolations.length > 0 && (
                <ul className="list-disc pl-4 text-xs text-amber-200 space-y-0.5">
                  {reviewViolations.map((violation, i) => (
                    <li key={i}>{violation}</li>
                  ))}
                </ul>
              )}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {viewMode !== "edit" && (
              <button
                type="button"
                onClick={onStartFix}
                className="px-3 py-1.5 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors"
              >
                <FiEdit3 />
                <span>Corriger</span>
              </button>
            )}
          </div>
          {confirmingExport && (
            <div className="p-3 rounded-lg bg-gray-900/80 border border-amber-700/50 text-xs text-amber-200 space-y-2">
              <p>
                Exporter quand même ? La lettre contient encore des points à corriger et ne sera
                pas marquée comme prête.
              </p>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={onForceExportPdf}
                  disabled={isDirty || downloadingPdf}
                  className="px-3 py-1.5 bg-amber-600 hover:bg-amber-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-colors"
                >
                  Exporter malgré tout
                </button>
                <button
                  type="button"
                  onClick={onCancelExportConfirm}
                  className="px-3 py-1.5 text-gray-300 hover:text-white bg-gray-800 hover:bg-gray-700 rounded-lg border border-gray-700 transition-colors"
                >
                  Annuler
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {exportError && (
        <div className="mx-4 sm:mx-6 mt-4 p-2.5 rounded-lg bg-red-950/40 border border-red-800/50 text-xs text-red-300 flex items-center gap-2">
          <FiAlertCircle className="shrink-0 text-red-400" />
          <span>{exportError}</span>
        </div>
      )}
    </>
  );
}

interface QualityReportProps {
  version: CoverLetterVersion;
  showReport: boolean;
  onToggleReport: () => void;
}

/** Collapsible panel displaying writer/critic AI models and critic verdict. */
export function CoverLetterQualityReport({
  version,
  showReport,
  onToggleReport,
}: QualityReportProps) {
  return (
    <div className="mt-4 pt-3 border-t border-gray-700/50 text-xs text-gray-400">
      <button
        type="button"
        onClick={onToggleReport}
        className="flex items-center gap-1.5 text-gray-300 hover:text-white transition-colors"
      >
        {showReport ? <FiChevronUp /> : <FiChevronDown />}
        <span className="font-medium">Détails du contrôle qualité & Modèles d&apos;IA</span>
      </button>

      {showReport && (
        <div className="mt-2.5 p-3.5 bg-gray-900/90 rounded-lg border border-gray-800/80 space-y-2.5">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
            <div>
              <span className="text-gray-400">Rédacteur : </span>
              <span className="font-mono text-gray-200">
                {version.models?.writer || "openai/gpt-5.6-terra"}
              </span>
            </div>
            <div>
              <span className="text-gray-400">Critique croisé : </span>
              <span className="font-mono text-gray-200">
                {version.models?.critic || "gemini/gemini-3.8-flash"}
              </span>
            </div>
          </div>

          {version.critic_verdict && (
            <div className="flex items-center gap-2 pt-1 border-t border-gray-800">
              <span className="text-gray-400">Verdict du critique : </span>
              <span
                className={`inline-flex items-center gap-1 font-semibold ${
                  version.critic_verdict.verdict === "pass"
                    ? "text-green-400"
                    : "text-amber-400"
                }`}
              >
                {version.critic_verdict.verdict === "pass" && (
                  <FiCheckCircle className="text-xs" />
                )}
                {version.critic_verdict.verdict.toUpperCase()}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
