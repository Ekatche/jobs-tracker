"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { coverLetterApi } from "@/lib/api";
import { CoverLetter } from "@/types/coverLetter";
import {
  FiRefreshCw,
  FiSave,
  FiAlertCircle,
  FiChevronDown,
  FiChevronUp,
  FiCopy,
  FiCheck,
  FiEye,
  FiEdit3,
  FiCheckCircle,
  FiDownload,
  FiZap,
  FiX,
} from "react-icons/fi";

const QUICK_INSTRUCTIONS = [
  "Plus percutant",
  "Plus concis",
  "Corriger",
  "Plus naturel",
];

interface RewriteProposal {
  start: number;
  end: number;
  originalPassage: string;
  rewritten: string;
  warnings: string[];
}

interface CoverLetterPanelProps {
  applicationId: string;
  isEtudeStatus: boolean;
}

export default function CoverLetterPanel({ applicationId }: CoverLetterPanelProps) {
  const [letterData, setLetterData] = useState<CoverLetter | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [generating, setGenerating] = useState<boolean>(false);
  const [textBody, setTextBody] = useState<string>("");
  const [saving, setSaving] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);
  const [viewMode, setViewMode] = useState<"preview" | "edit">("preview");
  const [showReport, setShowReport] = useState<boolean>(false);
  const [pollingTimeout, setPollingTimeout] = useState<boolean>(false);
  const [downloadingPdf, setDownloadingPdf] = useState<boolean>(false);

  // Partial rewrite states
  const [selection, setSelection] = useState<{
    start: number;
    end: number;
    letter: string;
  } | null>(null);
  const [customInstruction, setCustomInstruction] = useState<string>("");
  const [proposal, setProposal] = useState<RewriteProposal | null>(null);
  const [rewriting, setRewriting] = useState<boolean>(false);
  const [rewriteError, setRewriteError] = useState<string | null>(null);
  const [staleError, setStaleError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const startTimeRef = useRef<number>(Date.now());

  const fetchLetter = useCallback(async () => {
    try {
      const data = await coverLetterApi.getByApplicationId(applicationId);
      setLetterData(data);
      if (data && data.versions && data.versions.length > 0) {
        const current =
          data.versions.find((v) => v.n === data.current_version) ||
          data.versions[data.versions.length - 1];
        setTextBody(current.body);
      }
      return data;
    } catch (err) {
      console.error("Erreur chargement lettre:", err);
      return null;
    } finally {
      setLoading(false);
    }
  }, [applicationId]);

  useEffect(() => {
    fetchLetter();
  }, [fetchLetter]);

  // Polling automatique si status == pending (3s interval, 3min timeout)
  useEffect(() => {
    if (letterData?.status === "pending") {
      startTimeRef.current = Date.now();
      setPollingTimeout(false);
      pollIntervalRef.current = setInterval(async () => {
        if (Date.now() - startTimeRef.current > 180000) {
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
          setPollingTimeout(true);
          return;
        }
        const updated = await fetchLetter();
        if (updated?.status === "ready" || updated?.status === "failed") {
          setGenerating(false);
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
        }
      }, 3000);
    } else {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    }

    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, [letterData?.status, fetchLetter]);

  const handleRegenerate = async () => {
    setGenerating(true);
    setProposal(null);
    setSelection(null);
    // Mise à jour optimiste immédiate pour afficher le spinner
    setLetterData((prev) =>
      prev
        ? { ...prev, status: "pending" }
        : ({
            application_id: applicationId,
            user_id: "",
            status: "pending",
            current_version: 0,
            versions: [],
          } as unknown as CoverLetter)
    );
    try {
      await coverLetterApi.regenerate(applicationId);
      await fetchLetter();
    } catch (err) {
      console.error("Erreur lors de la régénération:", err);
    }
  };

  const handleSaveEdit = async () => {
    setSaving(true);
    setProposal(null);
    setSelection(null);
    setStaleError(null);
    try {
      const updated = await coverLetterApi.edit(applicationId, textBody);
      setLetterData(updated);
      setViewMode("preview");
    } finally {
      setSaving(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(textBody);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadPdf = async () => {
    if (downloadingPdf) return;
    setDownloadingPdf(true);
    try {
      await coverLetterApi.downloadPdf(applicationId);
    } catch (err) {
      console.error("Erreur téléchargement PDF:", err);
    } finally {
      setDownloadingPdf(false);
    }
  };

  // Les positions ne valent que pour le texte sur lequel la sélection a été faite
  const selectedPassage =
    selection && selection.letter === textBody
      ? textBody.slice(selection.start, selection.end)
      : "";

  const handleTextareaSelect = (e: React.SyntheticEvent<HTMLTextAreaElement>) => {
    const { selectionStart, selectionEnd, value } = e.currentTarget;
    // Un clic ailleurs ou une frappe laisse une sélection vide : on oublie l'ancienne
    setSelection(
      selectionStart !== selectionEnd
        ? { start: selectionStart, end: selectionEnd, letter: value }
        : null
    );
  };

  const handleRewrite = async (instructionToUse: string) => {
    if (!selection || !selectedPassage.trim()) return;
    const passage = selectedPassage;

    setRewriting(true);
    setRewriteError(null);
    setStaleError(null);

    try {
      const res = await coverLetterApi.rewritePassage(applicationId, {
        letter: textBody,
        passage,
        instruction: instructionToUse,
      });
      setProposal({
        start: selection.start,
        end: selection.end,
        originalPassage: passage,
        rewritten: res.rewritten,
        warnings: res.warnings || [],
      });
    } catch (err: unknown) {
      console.error("Erreur réécriture passage:", err);
      const message =
        err instanceof Error
          ? err.message
          : "Erreur lors de la réécriture du passage";
      setRewriteError(message);
    } finally {
      setRewriting(false);
    }
  };

  const handleAcceptProposal = () => {
    if (!proposal) return;
    const currentSlice = textBody.slice(proposal.start, proposal.end);
    if (currentSlice !== proposal.originalPassage) {
      setStaleError("Le texte a changé depuis la proposition, relancez-la.");
      return;
    }

    const newText =
      textBody.slice(0, proposal.start) +
      proposal.rewritten +
      textBody.slice(proposal.end);

    setTextBody(newText);
    setProposal(null);
    setSelection(null);
    setStaleError(null);
  };

  const handleRejectProposal = () => {
    setProposal(null);
    setStaleError(null);
  };

  const isPending = generating || letterData?.status === "pending";

  if (loading && !letterData) {
    return (
      <div className="mt-6 border border-gray-700/60 rounded-xl p-5 bg-gray-800/50 flex items-center gap-3 text-sm text-gray-400 animate-pulse">
        <FiRefreshCw className="animate-spin text-blue-400" />
        <span>Chargement de la lettre de motivation...</span>
      </div>
    );
  }

  // État initial (aucune lettre)
  if (!letterData || letterData.status === "none") {
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
            onClick={handleRegenerate}
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

  // État en cours de génération
  if (isPending) {
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
              CrewAI analyse l'offre, sélectionne vos réalisations et affine le texte.
            </p>
          </div>
        </div>

        {pollingTimeout && (
          <div className="text-xs text-amber-300 bg-amber-950/40 p-3 rounded-lg border border-amber-800/50 mt-1 flex items-center justify-between gap-2">
            <span>La génération prend un peu plus de temps que prévu.</span>
            <button
              onClick={handleRegenerate}
              className="px-2.5 py-1 bg-amber-600 hover:bg-amber-500 text-white rounded text-xs font-medium"
            >
              Relancer
            </button>
          </div>
        )}
      </div>
    );
  }

  // État échec
  if (letterData.status === "failed") {
    const isCreditOrQuotaError =
      letterData.error?.includes("Crédits épuisés") ||
      letterData.error?.includes("quota") ||
      letterData.error?.includes("Rate Limit");

    return (
      <div className="mt-6 p-5 rounded-xl bg-red-950/30 border border-red-500/40 text-red-200 flex flex-col gap-3 shadow-lg">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <FiAlertCircle className="text-red-400 text-lg mt-0.5 shrink-0" />
            <div>
              <p className="font-semibold text-sm text-white">Échec de la rédaction :</p>
              <p className="text-xs text-red-300 mt-1">{letterData.error || "Erreur inconnue"}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleRegenerate}
            disabled={isPending}
            className="px-3 py-1.5 bg-red-800 hover:bg-red-700 disabled:opacity-60 text-white text-xs font-medium rounded-md whitespace-nowrap flex items-center gap-1.5 transition-colors"
          >
            <FiRefreshCw className={isPending ? "animate-spin" : ""} />
            <span>Réessayer</span>
          </button>
        </div>

        {isCreditOrQuotaError && (
          <div className="text-xs text-amber-300/90 bg-amber-950/40 p-2.5 rounded-lg border border-amber-800/40 mt-1">
            💡 Astuce : Vérifiez votre solde sur la console de vos fournisseurs d'API dans la page Profil.
          </div>
        )}
      </div>
    );
  }

  // État lettre prête (ready)
  const currentVersionData = letterData.versions?.find(
    (v) => v.n === letterData.current_version
  );
  const savedBody = currentVersionData?.body || "";
  const isDirty = textBody !== savedBody;
  const wordCount = textBody.trim() ? textBody.trim().split(/\s+/).length : 0;

  return (
    <div className="mt-6 border border-gray-700/70 rounded-xl bg-gray-800/70 shadow-xl overflow-hidden backdrop-blur-sm">
      {/* En-tête avec titre, badges et contrôles aérés */}
      <div className="p-4 sm:p-5 border-b border-gray-700/60 bg-gray-900/40">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap items-center gap-2.5">
            <h3 className="text-base font-semibold text-white tracking-wide">
              Lettre de motivation
            </h3>
            {currentVersionData && (
              <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-blue-900/40 text-blue-300 border border-blue-700/40">
                v{currentVersionData.n} ({currentVersionData.origin === "generated" ? "IA" : "éditée"})
              </span>
            )}
            <span className="text-[11px] text-gray-400 font-mono">
              {wordCount} mots
            </span>
          </div>

          {/* Boutons d'action responsives */}
          <div className="flex flex-wrap items-center gap-2">
            {/* Toggle Aperçu / Édition */}
            <div className="flex bg-gray-900/80 p-0.5 rounded-lg border border-gray-700/80">
              <button
                type="button"
                onClick={() => {
                  setViewMode("preview");
                  setProposal(null);
                  setSelection(null);
                  setStaleError(null);
                }}
                className={`px-2.5 py-1 text-xs font-medium rounded-md flex items-center gap-1 transition-all ${
                  viewMode === "preview"
                    ? "bg-blue-600 text-white shadow-sm"
                    : "text-gray-400 hover:text-white"
                }`}
              >
                <FiEye className="text-xs" />
                <span>Aperçu</span>
              </button>
              <button
                type="button"
                onClick={() => setViewMode("edit")}
                className={`px-2.5 py-1 text-xs font-medium rounded-md flex items-center gap-1 transition-all ${
                  viewMode === "edit"
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
              onClick={handleCopy}
              className="px-2.5 py-1.5 text-xs text-gray-300 hover:text-white bg-gray-800 hover:bg-gray-700 rounded-lg border border-gray-700 transition-colors flex items-center gap-1.5"
              title="Copier la lettre"
            >
              {copied ? <FiCheck className="text-green-400" /> : <FiCopy />}
              <span>{copied ? "Copié" : "Copier"}</span>
            </button>

            <button
              type="button"
              onClick={handleDownloadPdf}
              disabled={isDirty || downloadingPdf || isPending}
              className={`px-2.5 py-1.5 text-xs rounded-lg border transition-colors flex items-center gap-1.5 ${
                isDirty
                  ? "bg-gray-800/40 text-gray-500 border-gray-700/40 cursor-not-allowed"
                  : "bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white border-gray-700"
              }`}
              title={
                isDirty
                  ? "Enregistrez vos modifications avant de télécharger le PDF"
                  : "Télécharger la lettre en PDF"
              }
            >
              {downloadingPdf ? (
                <FiRefreshCw className="animate-spin text-blue-400" />
              ) : (
                <FiDownload className={isDirty ? "text-gray-500" : "text-blue-400"} />
              )}
              <span>{downloadingPdf ? "Génération..." : "PDF"}</span>
            </button>

            <button
              type="button"
              onClick={handleRegenerate}
              disabled={isPending}
              className="px-2.5 py-1.5 text-xs text-gray-300 hover:text-white bg-gray-800 hover:bg-gray-700 disabled:opacity-50 rounded-lg border border-gray-700 transition-colors flex items-center gap-1.5"
              title="Générer une nouvelle version"
            >
              <FiRefreshCw className={isPending ? "animate-spin text-blue-400" : ""} />
              <span>{isPending ? "En cours..." : "Régénérer"}</span>
            </button>

            {viewMode === "edit" && (
              <button
                type="button"
                onClick={handleSaveEdit}
                disabled={saving}
                className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors shadow-sm"
              >
                <FiSave />
                <span>{saving ? "Enregistrement..." : "Enregistrer"}</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Corps du document : Aperçu ou Éditeur */}
      <div className="p-4 sm:p-6">
        {viewMode === "preview" ? (
          <div className="bg-gray-900/90 rounded-xl p-5 sm:p-7 border border-gray-800/80 shadow-inner">
            <div className="text-gray-100 text-sm sm:text-base leading-relaxed whitespace-pre-line font-sans select-text selection:bg-blue-600/40">
              {textBody || "Aucun contenu disponible pour cette lettre."}
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
                {proposal && (
                  <span className="text-xs text-amber-300 bg-amber-950/40 px-2 py-0.5 rounded border border-amber-800/40">
                    Éditeur verrouillé pendant la révision
                  </span>
                )}
              </div>
              <textarea
                ref={textareaRef}
                id="cover_letter_editor"
                value={textBody}
                onChange={(e) => {
                  setTextBody(e.target.value);
                  if (proposal) setProposal(null);
                }}
                onSelect={handleTextareaSelect}
                readOnly={Boolean(proposal)}
                rows={16}
                className={`w-full bg-gray-900 text-gray-100 p-4 rounded-xl border focus:outline-none text-sm font-sans leading-relaxed resize-y transition-colors ${
                  proposal
                    ? "border-amber-600/50 bg-gray-900/60 cursor-not-allowed"
                    : "border-gray-700 focus:ring-2 focus:ring-blue-500"
                }`}
                placeholder="Saisissez ou modifiez votre lettre ici..."
              />
            </div>

            {/* Panneau proposition ou barre d'outils réécriture */}
            {proposal ? (
              <div className="p-4 rounded-xl bg-blue-950/30 border border-blue-500/40 space-y-3 shadow-lg">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <FiZap className="text-blue-400" />
                    <h4 className="text-sm font-semibold text-white">
                      Proposition d'amélioration ciblée
                    </h4>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={handleRejectProposal}
                      className="px-3 py-1.5 text-xs text-gray-300 hover:text-white bg-gray-800 hover:bg-gray-700 rounded-lg border border-gray-700 transition-colors flex items-center gap-1.5"
                    >
                      <FiX />
                      <span>Rejeter</span>
                    </button>
                    <button
                      type="button"
                      onClick={handleAcceptProposal}
                      className="px-3 py-1.5 text-xs font-medium text-white bg-green-600 hover:bg-green-500 rounded-lg transition-colors flex items-center gap-1.5 shadow-sm"
                    >
                      <FiCheck />
                      <span>Accepter</span>
                    </button>
                  </div>
                </div>

                {staleError && (
                  <div className="p-2.5 rounded-lg bg-red-950/40 border border-red-800/50 text-xs text-red-300 flex items-center gap-2">
                    <FiAlertCircle className="shrink-0 text-red-400" />
                    <span>{staleError}</span>
                  </div>
                )}

                {proposal.warnings.length > 0 && (
                  <div className="p-2.5 rounded-lg bg-amber-950/40 border border-amber-800/50 text-xs text-amber-300 space-y-1">
                    {proposal.warnings.map((warn, i) => (
                      <div key={i} className="flex items-center gap-2">
                        <FiAlertCircle className="shrink-0 text-amber-400" />
                        <span>{warn}</span>
                      </div>
                    ))}
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                  <div className="p-3 rounded-lg bg-gray-900/90 border border-gray-800">
                    <div className="text-[11px] font-semibold text-gray-400 uppercase tracking-wide mb-1.5">
                      Passage original
                    </div>
                    <div className="text-gray-300 whitespace-pre-wrap font-sans leading-relaxed">
                      {proposal.originalPassage}
                    </div>
                  </div>
                  <div className="p-3 rounded-lg bg-blue-900/20 border border-blue-500/30">
                    <div className="text-[11px] font-semibold text-blue-300 uppercase tracking-wide mb-1.5">
                      Texte réécrit
                    </div>
                    <div className="text-white whitespace-pre-wrap font-sans leading-relaxed">
                      {proposal.rewritten}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="p-3.5 rounded-xl bg-gray-900/80 border border-gray-800 space-y-2.5">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-2 text-xs">
                    <FiZap className="text-blue-400" />
                    <span className="font-medium text-gray-200">
                      Améliorer une partie ciblée
                    </span>
                    {selectedPassage ? (
                      <span className="text-gray-400 text-[11px] truncate max-w-xs">
                        ({selectedPassage.length} car. sélectionnés)
                      </span>
                    ) : (
                      <span className="text-gray-500 text-[11px]">
                        (sélectionnez d'abord du texte dans l'éditeur)
                      </span>
                    )}
                  </div>

                  {/* Chips rapides */}
                  <div className="flex flex-wrap items-center gap-1.5">
                    {QUICK_INSTRUCTIONS.map((chip) => (
                      <button
                        key={chip}
                        type="button"
                        disabled={!selectedPassage || rewriting || isPending}
                        onClick={() => handleRewrite(chip)}
                        className="px-2 py-1 text-[11px] font-medium rounded-md bg-gray-800 hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed text-gray-300 hover:text-white border border-gray-700/80 transition-colors"
                      >
                        {chip}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Champ d'instruction personnalisée + bouton Proposer */}
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={customInstruction}
                    onChange={(e) => setCustomInstruction(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && selectedPassage && !rewriting && !isPending) {
                        e.preventDefault();
                        handleRewrite(customInstruction);
                      }
                    }}
                    disabled={!selectedPassage || rewriting || isPending}
                    placeholder={
                      selectedPassage
                        ? "Consigne libre (ex: insister sur les résultats, ton plus formel...)"
                        : "Sélectionnez un passage ci-dessus pour activer la réécriture"
                    }
                    className="flex-1 bg-gray-950/80 text-gray-200 text-xs px-3 py-2 rounded-lg border border-gray-700/80 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed placeholder:text-gray-500"
                  />
                  <button
                    type="button"
                    disabled={!selectedPassage || rewriting || isPending}
                    onClick={() => handleRewrite(customInstruction)}
                    className="px-3 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-medium rounded-lg flex items-center gap-1.5 transition-colors shadow-sm whitespace-nowrap"
                  >
                    {rewriting ? (
                      <FiRefreshCw className="animate-spin text-xs" />
                    ) : (
                      <FiZap className="text-xs" />
                    )}
                    <span>{rewriting ? "Réécriture..." : "Proposer"}</span>
                  </button>
                </div>

                {rewriteError && (
                  <div className="p-2 rounded-lg bg-red-950/40 border border-red-800/40 text-xs text-red-300 flex items-center gap-2">
                    <FiAlertCircle className="shrink-0 text-red-400" />
                    <span>{rewriteError}</span>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Panneau rétractable d'audit qualité et modèles */}
        {currentVersionData && (
          <div className="mt-4 pt-3 border-t border-gray-700/50 text-xs text-gray-400">
            <button
              type="button"
              onClick={() => setShowReport(!showReport)}
              className="flex items-center gap-1.5 text-gray-300 hover:text-white transition-colors"
            >
              {showReport ? <FiChevronUp /> : <FiChevronDown />}
              <span className="font-medium">Détails du contrôle qualité & Modèles d'IA</span>
            </button>

            {showReport && (
              <div className="mt-2.5 p-3.5 bg-gray-900/90 rounded-lg border border-gray-800/80 space-y-2.5">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="text-gray-400">Rédacteur : </span>
                    <span className="font-mono text-gray-200">
                      {currentVersionData.models?.writer || "gpt-4o-mini"}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-400">Critique croisé : </span>
                    <span className="font-mono text-gray-200">
                      {currentVersionData.models?.critic || "mistral-small-2501"}
                    </span>
                  </div>
                </div>

                {currentVersionData.critic_verdict && (
                  <div className="flex items-center gap-2 pt-1 border-t border-gray-800">
                    <span className="text-gray-400">Verdict du critique : </span>
                    <span
                      className={`inline-flex items-center gap-1 font-semibold ${
                        currentVersionData.critic_verdict.verdict === "pass"
                          ? "text-green-400"
                          : "text-amber-400"
                      }`}
                    >
                      {currentVersionData.critic_verdict.verdict === "pass" && (
                        <FiCheckCircle className="text-xs" />
                      )}
                      {currentVersionData.critic_verdict.verdict.toUpperCase()}
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
