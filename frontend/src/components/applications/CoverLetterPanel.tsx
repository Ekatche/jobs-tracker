import React, { useState, useEffect, useRef, useCallback } from "react";
import { coverLetterApi } from "@/lib/api";
import { CoverLetter } from "@/types/coverLetter";
import { FiRefreshCw, FiSave, FiAlertCircle, FiChevronDown, FiChevronUp, FiCopy, FiCheck } from "react-icons/fi";

interface CoverLetterPanelProps {
  applicationId: string;
  isEtudeStatus: boolean;
}

export default function CoverLetterPanel({ applicationId, isEtudeStatus }: CoverLetterPanelProps) {
  const [letterData, setLetterData] = useState<CoverLetter | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [textBody, setTextBody] = useState<string>("");
  const [saving, setSaving] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);
  const [showReport, setShowReport] = useState<boolean>(false);
  const [pollingTimeout, setPollingTimeout] = useState<boolean>(false);

  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const startTimeRef = useRef<number>(Date.now());

  const fetchLetter = useCallback(async () => {
    try {
      const data = await coverLetterApi.getByApplicationId(applicationId);
      setLetterData(data);
      if (data && data.versions && data.versions.length > 0) {
        const current = data.versions.find((v) => v.n === data.current_version) || data.versions[data.versions.length - 1];
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
          // 3 minutes timeout
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
          setPollingTimeout(true);
          return;
        }
        const updated = await fetchLetter();
        if (updated?.status === "ready" || updated?.status === "failed") {
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
    setLoading(true);
    await coverLetterApi.regenerate(applicationId);
    await fetchLetter();
  };

  const handleSaveEdit = async () => {
    setSaving(true);
    try {
      const updated = await coverLetterApi.edit(applicationId, textBody);
      setLetterData(updated);
    } finally {
      setSaving(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(textBody);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading && !letterData) {
    return <div className="p-4 text-sm text-gray-400">Chargement de la lettre de motivation...</div>;
  }

  if (!isEtudeStatus && (!letterData || letterData.status === "none")) {
    return null;
  }

  if (letterData?.status === "pending") {
    return (
      <div className="mt-4 p-4 rounded-lg bg-blue-900/20 border border-blue-800 text-blue-300 flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <FiRefreshCw className="animate-spin" />
          <span>Génération de la lettre de motivation en cours (CrewAI multi-modèles)...</span>
        </div>
        {pollingTimeout && (
          <div className="text-sm text-amber-400 mt-2">
            La génération prend plus de temps que prévu. Vérifiez dans un instant ou relancez.
            <button onClick={handleRegenerate} className="ml-2 underline">Réessayer</button>
          </div>
        )}
      </div>
    );
  }

  if (letterData?.status === "failed") {
    const isCreditOrQuotaError =
      letterData.error?.includes("Crédits épuisés") ||
      letterData.error?.includes("quota") ||
      letterData.error?.includes("Rate Limit");

    return (
      <div className="mt-4 p-4 rounded-lg bg-red-900/20 border border-red-800 text-red-300 flex flex-col gap-2">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-start gap-2">
            <FiAlertCircle className="mt-1 flex-shrink-0" />
            <div>
              <p className="font-medium text-sm">Échec de la génération :</p>
              <p className="text-xs text-red-200 mt-0.5">{letterData.error || "Erreur inconnue"}</p>
            </div>
          </div>
          <button
            onClick={handleRegenerate}
            className="px-3 py-1 bg-red-800 rounded hover:bg-red-700 text-white text-xs whitespace-nowrap"
          >
            Relancer
          </button>
        </div>
        {isCreditOrQuotaError && (
          <div className="text-xs text-amber-300/90 bg-amber-950/30 p-2 rounded border border-amber-800/40 mt-1">
            💡 Astuce : Vérifiez votre solde sur la console de facturation (OpenAI / Mistral) ou utilisez le modèle Gemini qui dispose d'un palier gratuit.
          </div>
        )}
      </div>
    );
  }

  const currentVersionData = letterData?.versions?.find((v) => v.n === letterData.current_version);

  return (
    <div className="mt-6 border border-gray-700 rounded-lg p-4 bg-gray-800/60">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <h3 className="text-base font-semibold text-white">Lettre de motivation</h3>
          {currentVersionData && (
            <span className="text-xs px-2 py-0.5 rounded bg-gray-700 text-gray-300">
              v{currentVersionData.n} ({currentVersionData.origin})
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleCopy} className="p-1.5 text-gray-400 hover:text-white rounded hover:bg-gray-700 text-sm flex items-center gap-1">
            {copied ? <FiCheck className="text-green-400" /> : <FiCopy />}
            <span>{copied ? "Copié" : "Copier"}</span>
          </button>
          <button onClick={handleRegenerate} className="p-1.5 text-gray-400 hover:text-white rounded hover:bg-gray-700 text-sm flex items-center gap-1">
            <FiRefreshCw />
            <span>Régénérer</span>
          </button>
          <button onClick={handleSaveEdit} disabled={saving} className="px-3 py-1 bg-blue-600 hover:bg-blue-500 rounded text-white text-sm flex items-center gap-1">
            <FiSave />
            <span>{saving ? "Sauvegarde..." : "Enregistrer"}</span>
          </button>
        </div>
      </div>

      <textarea
        value={textBody}
        onChange={(e) => setTextBody(e.target.value)}
        rows={12}
        className="w-full bg-gray-900 text-gray-100 p-3 rounded border border-gray-700 focus:outline-none focus:border-blue-500 text-sm font-sans leading-relaxed"
      />

      {/* Garde-fous et verdict du critique repliables */}
      {currentVersionData && (
        <div className="mt-3 border-t border-gray-700 pt-2 text-xs text-gray-400">
          <button onClick={() => setShowReport(!showReport)} className="flex items-center gap-1 text-gray-300 hover:text-white">
            {showReport ? <FiChevronUp /> : <FiChevronDown />}
            <span>Détails du contrôle qualité & Modèles utilisés</span>
          </button>
          {showReport && (
            <div className="mt-2 p-3 bg-gray-900/80 rounded border border-gray-800 space-y-2">
              <div>
                <span className="font-semibold text-gray-300">Modèles : </span>
                <span>{JSON.stringify(currentVersionData.models)}</span>
              </div>
              {currentVersionData.critic_verdict && (
                <div>
                  <span className="font-semibold text-gray-300">Verdict du critique : </span>
                  <span className={currentVersionData.critic_verdict.verdict === "pass" ? "text-green-400" : "text-amber-400"}>
                    {currentVersionData.critic_verdict.verdict.toUpperCase()}
                  </span>
                </div>
              )}
              {currentVersionData.guard_report && currentVersionData.guard_report.warnings && currentVersionData.guard_report.warnings.length > 0 && (
                <div>
                  <span className="font-semibold text-amber-400">Avertissements de style : </span>
                  <ul className="list-disc ml-4">
                    {currentVersionData.guard_report.warnings.map((w, idx) => (
                      <li key={idx}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
