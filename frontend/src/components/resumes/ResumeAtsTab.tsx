"use client";

import { useCallback, useEffect, useState } from "react";
import {
  FiAlertTriangle,
  FiCheck,
  FiCopy,
  FiDownload,
  FiRefreshCw,
  FiShield,
} from "react-icons/fi";
import { resumeApi } from "@/lib/api";
import type { ResumeAtsScoreResponse, ResumeExportTextResponse } from "@/types/resume";

interface ResumeAtsTabProps {
  resumeId: string;
  offerId?: string | null;
  refreshKey?: number;
}

const AXES: Array<{
  key: keyof ResumeAtsScoreResponse["breakdown"];
  label: string;
  max: number;
}> = [
  { key: "offer_alignment", label: "Adéquation à l'offre", max: 40 },
  { key: "text", label: "Texte sélectionnable", max: 10 },
  { key: "sections", label: "Sections reconnues", max: 10 },
  { key: "contact", label: "Coordonnées atteignables", max: 10 },
  { key: "layout", label: "Structure ATS", max: 10 },
  { key: "metrics_and_bullets", label: "Puces & métriques", max: 10 },
  { key: "charset_and_markers", label: "Encodage & propreté", max: 10 },
];

const GRADE_CLS: Record<ResumeAtsScoreResponse["grade"], string> = {
  A: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
  B: "bg-blue-500/20 text-blue-300 border-blue-500/40",
  C: "bg-amber-500/20 text-amber-300 border-amber-500/40",
  D: "bg-rose-500/20 text-rose-300 border-rose-500/40",
};

export default function ResumeAtsTab({ resumeId, offerId, refreshKey = 0 }: ResumeAtsTabProps) {
  const [ats, setAts] = useState<ResumeAtsScoreResponse | null>(null);
  const [exported, setExported] = useState<ResumeExportTextResponse | null>(null);
  const [format, setFormat] = useState<"markdown" | "txt">("markdown");
  const [loadingScore, setLoadingScore] = useState(false);
  const [loadingExport, setLoadingExport] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadScore = useCallback(async () => {
    if (!resumeId) return;
    setLoadingScore(true);
    setError(null);
    try {
      const data = await resumeApi.getAtsScore(resumeId, offerId || undefined);
      setAts(data);
    } catch {
      setError("Impossible de calculer le score ATS pour ce CV.");
    } finally {
      setLoadingScore(false);
    }
  }, [resumeId, offerId]);

  const loadExport = useCallback(async () => {
    if (!resumeId) return;
    setLoadingExport(true);
    try {
      const data = await resumeApi.exportText(resumeId, format);
      setExported(data);
    } catch {
      setError("Impossible de générer l'export texte ATS.");
    } finally {
      setLoadingExport(false);
    }
  }, [resumeId, format]);

  useEffect(() => {
    loadScore();
  }, [loadScore, refreshKey]);

  useEffect(() => {
    loadExport();
  }, [loadExport, refreshKey]);

  const handleCopyExport = async () => {
    if (!exported?.content) return;
    try {
      await navigator.clipboard.writeText(exported.content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      // Clipboard unavailable
    }
  };

  const handleDownloadText = () => {
    if (!exported?.content) return;
    const blob = new Blob([exported.content], { type: "text/plain;charset=utf-8" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = exported.filename || `CV_ATS.${format === "markdown" ? "md" : "txt"}`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  };

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-5 bg-[#0f172a] custom-scrollbar">
      {error && (
        <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-4 py-2.5 text-xs text-rose-300">
          {error}
        </div>
      )}

      {/* ATS Score Header & Breakdown */}
      <div className="rounded-xl border border-slate-700/80 bg-slate-900/60 p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-blue-500/15 text-blue-400 border border-blue-500/30">
              <FiShield className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white">Score de compatibilité ATS</h3>
              <p className="text-xs text-slate-400">
                Adéquation aux mots-clés de l&apos;offre (40 pts) et conformité technique ATS (60 pts)
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            {ats && (
              <>
                <span className="text-xl font-extrabold font-mono text-white">
                  {ats.score}<span className="text-xs font-normal text-slate-400">/100</span>
                </span>
                <span className={`px-2.5 py-0.5 rounded-lg border text-xs font-bold ${GRADE_CLS[ats.grade]}`}>
                  Grade {ats.grade}
                </span>
              </>
            )}
            <button
              type="button"
              onClick={() => { loadScore(); loadExport(); }}
              disabled={loadingScore}
              className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors disabled:opacity-50"
              title="Recalculer"
            >
              <FiRefreshCw className={`w-3.5 h-3.5 ${loadingScore ? "animate-spin" : ""}`} />
            </button>
          </div>
        </div>

        {loadingScore && !ats ? (
          <div className="py-8 text-center text-xs text-slate-400">Calcul du score ATS...</div>
        ) : ats ? (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {AXES.map((axis) => {
                const value = ats.breakdown[axis.key] ?? 0;
                const pct = Math.min(100, Math.round((value / axis.max) * 100));
                const barCls = pct >= 80 ? "bg-emerald-500" : pct >= 55 ? "bg-amber-500" : "bg-rose-500";
                return (
                  <div key={axis.key} className="rounded-lg bg-slate-950/70 border border-slate-800 p-3 space-y-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-slate-300">{axis.label}</span>
                      <span className="font-mono font-semibold text-white">{value}/{axis.max}</span>
                    </div>
                    <div
                      role="progressbar"
                      aria-label={axis.label}
                      aria-valuenow={value}
                      aria-valuemin={0}
                      aria-valuemax={axis.max}
                      className="h-1.5 w-full rounded-full bg-slate-800 overflow-hidden"
                    >
                      <div className={`h-full rounded-full transition-all ${barCls}`} style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>

            {Object.keys(ats.invisible_markers || {}).length > 0 && (
              <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-200 flex items-start gap-2">
                <FiAlertTriangle className="shrink-0 mt-0.5 text-amber-400" />
                <span>
                  Marqueurs Unicode invisibles détectés :{" "}
                  {Object.entries(ats.invisible_markers).map(([k, v]) => `${k} (${v})`).join(", ")}
                </span>
              </div>
            )}

            {ats.keyword_coverage && (
              <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3.5 space-y-2.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-200">Couverture mots-clés de l&apos;offre</span>
                  <span className="font-mono font-bold text-blue-300">{ats.keyword_coverage.coverage_pct}%</span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {ats.keyword_coverage.matched.map((kw) => (
                    <span key={`m-${kw}`} className="px-2 py-0.5 rounded text-[11px] bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                      {kw}
                    </span>
                  ))}
                  {ats.keyword_coverage.missing.map((kw) => (
                    <span key={`x-${kw}`} className="px-2 py-0.5 rounded text-[11px] bg-amber-500/15 text-amber-300 border border-amber-500/30">
                      {kw}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {ats.issues.length > 0 && (
              <ul className="space-y-1 text-xs text-amber-200/90 bg-slate-950/50 border border-slate-800 rounded-lg p-3 list-disc pl-6">
                {ats.issues.map((issue, idx) => <li key={idx}>{issue}</li>)}
              </ul>
            )}
          </>
        ) : null}
      </div>

      {/* Export Markdown / TXT section */}
      <div className="rounded-xl border border-slate-700/80 bg-slate-900/60 p-5 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-bold text-white">Export mono-colonne nettoyé ATS</h3>
            <p className="text-xs text-slate-400">
              Texte sans caractères invisibles ni tableaux complexes, prêt pour Workday ou Greenhouse
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex bg-slate-950 p-0.5 rounded-lg border border-slate-700 text-xs">
              {(["markdown", "txt"] as const).map((fmt) => (
                <button
                  key={fmt}
                  type="button"
                  onClick={() => setFormat(fmt)}
                  className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                    format === fmt ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"
                  }`}
                >
                  {fmt === "markdown" ? "Markdown" : "Texte brut"}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={handleCopyExport}
              disabled={!exported?.content || loadingExport}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs text-slate-200 disabled:opacity-50"
            >
              {copied ? <FiCheck className="text-emerald-400" /> : <FiCopy />}
              <span>{copied ? "Copié" : "Copier"}</span>
            </button>
            <button
              type="button"
              onClick={handleDownloadText}
              disabled={!exported?.content || loadingExport}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-xs font-semibold text-white disabled:opacity-50"
            >
              <FiDownload />
              <span>Télécharger</span>
            </button>
          </div>
        </div>

        <pre className="max-h-72 overflow-auto rounded-lg border border-slate-800 bg-slate-950/90 p-3.5 text-xs font-mono text-slate-200 whitespace-pre-wrap custom-scrollbar">
          {loadingExport
            ? "Génération de l'export..."
            : exported?.content || "Aucun contenu disponible."}
        </pre>
      </div>
    </div>
  );
}
