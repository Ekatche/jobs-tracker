"use client";

import { useCallback, useEffect, useState } from "react";
import { FiAlertCircle, FiCheckCircle, FiLayers, FiRefreshCw } from "react-icons/fi";
import AccessibleDialog from "@/components/ui/AccessibleDialog";
import { jobOffersApi, type JdSkillGapsResponse } from "@/lib/api";

interface SkillGapsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type ClassificationFilter = "all" | "gap" | "supported_by_resume";

export default function SkillGapsModal({ isOpen, onClose }: SkillGapsModalProps) {
  const [minScore, setMinScore] = useState<number>(0);
  const [kindFilter, setKindFilter] = useState<ClassificationFilter>("all");
  const [data, setData] = useState<JdSkillGapsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadSkillGaps = useCallback(async () => {
    if (!isOpen) return;
    setLoading(true);
    setError(null);
    try {
      const res = await jobOffersApi.getSkillGaps(minScore);
      setData(res);
    } catch {
      setError("Impossible de charger l'analyse des lacunes de compétences.");
    } finally {
      setLoading(false);
    }
  }, [isOpen, minScore]);

  useEffect(() => {
    loadSkillGaps();
  }, [loadSkillGaps]);

  const visibleItems = (data?.items || []).filter(
    (item) => kindFilter === "all" || item.classification === kindFilter
  );

  return (
    <AccessibleDialog
      isOpen={isOpen}
      onClose={onClose}
      titleId="skill-gaps-modal-title"
      title={
        <>
          <FiLayers className="text-amber-400" />
          <span>Lacunes de Compétences JD</span>
        </>
      }
      subtitle="Compétences manquantes récurrentes dans vos offres évaluées vs preuves existantes du CV"
      maxWidthClass="max-w-4xl"
    >
      <div className="space-y-4">
        {/* Controls */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="text-slate-400">Score min. :</span>
            {[
              { value: 0, label: "Toutes" },
              { value: 3.5, label: "≥ 3.5" },
              { value: 4.0, label: "≥ 4.0" },
            ].map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setMinScore(opt.value)}
                className={`px-2.5 py-1 rounded-lg border font-medium transition-colors ${
                  minScore === opt.value
                    ? "bg-blue-600 text-white border-blue-500"
                    : "bg-slate-900 text-slate-300 border-slate-700 hover:bg-slate-800"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2 text-xs">
            {(
              [
                { id: "all", label: "Tout" },
                { id: "gap", label: "Lacunes réelles" },
                { id: "supported_by_resume", label: "Déjà dans le CV" },
              ] as const
            ).map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setKindFilter(tab.id)}
                className={`px-2.5 py-1 rounded-lg border font-medium transition-colors ${
                  kindFilter === tab.id
                    ? "bg-amber-500/20 text-amber-200 border-amber-500/40"
                    : "bg-slate-900 text-slate-400 border-slate-700 hover:text-white"
                }`}
              >
                {tab.label}
              </button>
            ))}

            <button
              type="button"
              onClick={loadSkillGaps}
              disabled={loading}
              aria-label="Actualiser"
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 disabled:opacity-50"
            >
              <FiRefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            </button>
          </div>
        </div>

        {data && (
          <p className="text-xs text-slate-400">
            <strong className="text-slate-200">{data.total_evaluations_analyzed}</strong>{" "}
            évaluations analysées •{" "}
            <strong className="text-slate-200">{visibleItems.length}</strong> compétences listées
          </p>
        )}

        {error && (
          <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 p-3 text-xs text-rose-300">
            {error}
          </div>
        )}

        {loading && !data ? (
          <div className="py-12 text-center text-xs text-slate-400">
            Agrégation des exigences manquantes...
          </div>
        ) : visibleItems.length === 0 ? (
          <div className="rounded-xl border border-slate-800 bg-slate-900/50 py-10 text-center text-xs text-slate-400">
            Aucune lacune détectée sur ce filtre.
          </div>
        ) : (
          <div className="space-y-2">
            {visibleItems.map((item) => {
              const isSupported = item.classification === "supported_by_resume";
              return (
                <div
                  key={`${item.skill}-${item.classification}`}
                  className="rounded-xl border border-slate-800 bg-slate-900/65 p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                >
                  <div className="space-y-1.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-semibold text-white">{item.skill}</span>
                      {isSupported ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-sky-500/15 text-sky-300 border border-sky-500/30">
                          <FiCheckCircle className="w-3 h-3" />
                          Déjà dans le CV (à valoriser)
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-rose-500/15 text-rose-300 border border-rose-500/30">
                          <FiAlertCircle className="w-3 h-3" />
                          Lacune réelle
                        </span>
                      )}
                    </div>

                    {item.archetypes.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {item.archetypes.slice(0, 5).map((arch) => (
                          <span
                            key={arch}
                            className="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300 border border-slate-700"
                          >
                            {arch}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="shrink-0 text-right text-xs">
                    <p className="font-mono font-bold text-white">{item.count} offre(s)</p>
                    <p className="text-[11px] text-amber-300">
                      dont {item.critical_or_high_count} critique/haute
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </AccessibleDialog>
  );
}
