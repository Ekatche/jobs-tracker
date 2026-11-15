"use client";

import React from "react";
import { useCoverLetter } from "@/hooks/useCoverLetter";
import {
  CoverLetterLoadingState,
  CoverLetterEmptyState,
  CoverLetterPendingState,
  CoverLetterFailedState,
} from "./CoverLetterStates";
import {
  CoverLetterReviewBanner,
  CoverLetterQualityReport,
} from "./CoverLetterReviewBanner";
import { CoverLetterRewriteBox } from "./CoverLetterRewriteBox";
import {
  FiRefreshCw,
  FiSave,
  FiCopy,
  FiCheck,
  FiEye,
  FiEdit3,
  FiDownload,
} from "react-icons/fi";

interface CoverLetterPanelProps {
  applicationId: string;
  isEtudeStatus: boolean;
}

export default function CoverLetterPanel({ applicationId }: CoverLetterPanelProps) {
  const cl = useCoverLetter(applicationId);

  if (cl.loading && !cl.letterData) {
    return <CoverLetterLoadingState />;
  }

  if (!cl.letterData || cl.letterData.status === "none") {
    return <CoverLetterEmptyState isPending={cl.isPending} onRegenerate={cl.handleRegenerate} />;
  }

  if (cl.isPending) {
    return (
      <CoverLetterPendingState
        pollingTimeout={cl.pollingTimeout}
        onRegenerate={cl.handleRegenerate}
      />
    );
  }

  if (cl.letterData.status === "failed") {
    return (
      <CoverLetterFailedState
        error={cl.letterData.error}
        isPending={cl.isPending}
        onRegenerate={cl.handleRegenerate}
      />
    );
  }

  return (
    <div className="mt-6 border border-gray-700/70 rounded-xl bg-gray-800/70 shadow-xl overflow-hidden backdrop-blur-sm">
      {/* Header with version badge, word count, and toolbar actions */}
      <div className="p-4 sm:p-5 border-b border-gray-700/60 bg-gray-900/40">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap items-center gap-2.5">
            <h3 className="text-base font-semibold text-white tracking-wide">
              Lettre de motivation
            </h3>
            {cl.currentVersionData && (
              <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-blue-900/40 text-blue-300 border border-blue-700/40">
                v{cl.currentVersionData.n} ({cl.currentVersionData.origin === "generated" ? "IA" : "éditée"})
              </span>
            )}
            <span className="text-[11px] text-gray-400 font-mono">
              {cl.wordCount} mots
            </span>
          </div>

          {/* Responsive action buttons */}
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex bg-gray-900/80 p-0.5 rounded-lg border border-gray-700/80">
              <button
                type="button"
                onClick={() => {
                  cl.setViewMode("preview");
                  cl.setProposal(null);
                  cl.setSelection(null);
                  cl.setStaleError(null);
                }}
                className={`px-2.5 py-1 text-xs font-medium rounded-md flex items-center gap-1 transition-all ${
                  cl.viewMode === "preview"
                    ? "bg-blue-600 text-white shadow-sm"
                    : "text-gray-400 hover:text-white"
                }`}
              >
                <FiEye className="text-xs" />
                <span>Aperçu</span>
              </button>
              <button
                type="button"
                onClick={() => {
                  cl.setConfirmingExport(false);
                  cl.setViewMode("edit");
                }}
                className={`px-2.5 py-1 text-xs font-medium rounded-md flex items-center gap-1 transition-all ${
                  cl.viewMode === "edit"
                    ? "bg-blue-600 text-white shadow-sm"
                    : "text-gray-400 hover:text-white"
                }`}
              >
                <FiEdit3 className="text-xs" />
                <span>Éditer</span>
              </button>
            </div>

            <button
              type="button"
              onClick={cl.handleCopy}
              className="px-2.5 py-1.5 text-xs text-gray-300 hover:text-white bg-gray-800 hover:bg-gray-700 rounded-lg border border-gray-700 transition-colors flex items-center gap-1.5"
              title="Copier la lettre"
            >
              {cl.copied ? <FiCheck className="text-green-400" /> : <FiCopy />}
              <span>{cl.copied ? "Copié" : "Copier"}</span>
            </button>

            <button
              type="button"
              onClick={() => (cl.needsReview ? cl.setConfirmingExport(true) : cl.handleDownloadPdf())}
              disabled={cl.isDirty || cl.downloadingPdf || cl.isPending}
              className={`px-2.5 py-1.5 text-xs rounded-lg border transition-colors flex items-center gap-1.5 ${
                cl.isDirty
                  ? "bg-gray-800/40 text-gray-500 border-gray-700/40 cursor-not-allowed"
                  : "bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white border-gray-700"
              }`}
              title={
                cl.isDirty
                  ? "Enregistrez vos modifications avant de télécharger le PDF"
                  : "Télécharger la lettre en PDF"
              }
            >
              {cl.downloadingPdf ? (
                <FiRefreshCw className="animate-spin text-blue-400" />
              ) : (
                <FiDownload className={cl.isDirty ? "text-gray-500" : "text-blue-400"} />
              )}
              <span>{cl.downloadingPdf ? "Génération..." : "PDF"}</span>
            </button>

            <button
              type="button"
              onClick={cl.handleRegenerate}
              disabled={cl.isPending}
              className="px-2.5 py-1.5 text-xs text-gray-300 hover:text-white bg-gray-800 hover:bg-gray-700 disabled:opacity-50 rounded-lg border border-gray-700 transition-colors flex items-center gap-1.5"
              title="Générer une nouvelle version"
            >
              <FiRefreshCw className={cl.isPending ? "animate-spin text-blue-400" : ""} />
              <span>{cl.isPending ? "En cours..." : "Régénérer"}</span>
            </button>

            {cl.viewMode === "edit" && (
              <button
                type="button"
                onClick={cl.handleSaveEdit}
                disabled={cl.saving || !cl.isDirty}
                className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors shadow-sm"
              >
                <FiSave />
                <span>{cl.saving ? "Enregistrement..." : "Enregistrer"}</span>
              </button>
            )}
          </div>
        </div>
      </div>

      <CoverLetterReviewBanner
        needsReview={cl.needsReview}
        reviewViolations={cl.reviewViolations}
        viewMode={cl.viewMode}
        confirmingExport={cl.confirmingExport}
        isDirty={cl.isDirty}
        downloadingPdf={cl.downloadingPdf}
        exportError={cl.exportError}
        onStartFix={() => {
          cl.setConfirmingExport(false);
          cl.setExportError(null);
          cl.setViewMode("edit");
        }}
        onCancelExportConfirm={() => cl.setConfirmingExport(false)}
        onForceExportPdf={() => cl.handleDownloadPdf(true)}
      />

      {/* Document body: preview or editor */}
      <div className="p-4 sm:p-6">
        {cl.viewMode === "preview" ? (
          <div className="bg-gray-900/90 rounded-xl p-5 sm:p-7 border border-gray-800/80 shadow-inner">
            <div className="text-gray-100 text-sm sm:text-base leading-relaxed whitespace-pre-line font-sans select-text selection:bg-blue-600/40">
              {cl.textBody || "Aucun contenu disponible pour cette lettre."}
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div>
              <div className="flex items-center justify-between mb-2">
                <label
                  htmlFor="cover_letter_editor"
                  className="block text-xs font-semibold text-gray-400 uppercase"
                >
                  Édition directe de la lettre
                </label>
                {cl.proposal && (
                  <span className="text-xs text-amber-300 bg-amber-950/40 px-2 py-0.5 rounded border border-amber-800/40">
                    Éditeur verrouillé pendant la révision
                  </span>
                )}
              </div>
              <textarea
                ref={cl.textareaRef}
                id="cover_letter_editor"
                value={cl.textBody}
                onChange={(e) => {
                  cl.setTextBody(e.target.value);
                  if (cl.proposal) cl.setProposal(null);
                }}
                onSelect={cl.handleTextareaSelect}
                readOnly={Boolean(cl.proposal)}
                rows={16}
                className={`w-full bg-gray-900 text-gray-100 p-4 rounded-xl border focus:outline-none text-sm font-sans leading-relaxed resize-y transition-colors ${
                  cl.proposal
                    ? "border-amber-600/50 bg-gray-900/60 cursor-not-allowed"
                    : "border-gray-700 focus:ring-2 focus:ring-blue-500"
                }`}
                placeholder="Saisissez ou modifiez votre lettre ici..."
              />
            </div>

            <CoverLetterRewriteBox
              proposal={cl.proposal}
              staleError={cl.staleError}
              selectedPassage={cl.selectedPassage}
              customInstruction={cl.customInstruction}
              rewriting={cl.rewriting}
              isPending={cl.isPending}
              rewriteError={cl.rewriteError}
              onCustomInstructionChange={cl.setCustomInstruction}
              onRewrite={cl.handleRewrite}
              onAcceptProposal={cl.handleAcceptProposal}
              onRejectProposal={cl.handleRejectProposal}
            />
          </div>
        )}

        {cl.currentVersionData && (
          <CoverLetterQualityReport
            version={cl.currentVersionData}
            showReport={cl.showReport}
            onToggleReport={() => cl.setShowReport(!cl.showReport)}
          />
        )}
      </div>
    </div>
  );
}
