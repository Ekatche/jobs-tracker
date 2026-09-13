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
} from "react-icons/fi";

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
                onClick={() => setViewMode("preview")}
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
          <div>
            <label htmlFor="cover_letter_editor" className="block text-xs font-semibold text-gray-400 uppercase mb-2">
              Édition directe de la lettre
            </label>
            <textarea
              id="cover_letter_editor"
              value={textBody}
              onChange={(e) => setTextBody(e.target.value)}
              rows={16}
              className="w-full bg-gray-900 text-gray-100 p-4 rounded-xl border border-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm font-sans leading-relaxed resize-y"
              placeholder="Saisissez ou modifiez votre lettre ici..."
            />
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
