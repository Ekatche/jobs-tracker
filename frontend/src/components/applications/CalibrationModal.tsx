"use client";

import { useCallback, useEffect, useState } from "react";
import { FiActivity, FiAlertTriangle, FiRefreshCw } from "react-icons/fi";
import AccessibleDialog from "@/components/ui/AccessibleDialog";
import { applicationApi, type ScoreCalibrationBucket, type ScoreCalibrationResponse } from "@/lib/api";

interface CalibrationModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const BAND_ORDER = ["<3.5", "3.5-3.9", "4.0-4.4", ">=4.5"];

function BucketRows({
  rows,
  minBandN,
}: {
  rows: ScoreCalibrationBucket[];
  minBandN: number;
}) {
  return (
    <tbody className="divide-y divide-slate-800/80 text-xs">
      {rows.map((bucket) => (
        <tr key={bucket.label} className="hover:bg-slate-800/30">
          <td className="px-3 py-2.5 font-mono font-semibold text-white">{bucket.label}</td>
          <td className="px-3 py-2.5 text-slate-300">{bucket.resolved_count}</td>
          <td className="px-3 py-2.5 text-slate-400">{bucket.in_flight_count}</td>
          <td className="px-3 py-2.5 text-emerald-300 font-medium">{bucket.interview_count}</td>
          <td className="px-3 py-2.5">
            {bucket.interview_rate !== null ? (
              <span className="font-mono font-semibold text-white">
                {bucket.interview_rate}%
                {!bucket.sample_floor_met && (
                  <span className="ml-1.5 text-[10px] text-amber-300 font-normal">
                    (n&lt;{minBandN})
                  </span>
                )}
              </span>
            ) : (
              <span className="text-slate-500">—</span>
            )}
          </td>
          <td className="px-3 py-2.5">
            {bucket.offer_rate !== null ? (
              <span className="font-mono text-blue-300">{bucket.offer_rate}%</span>
            ) : (
              <span className="text-slate-500">—</span>
            )}
          </td>
        </tr>
      ))}
    </tbody>
  );
}

export default function CalibrationModal({ isOpen, onClose }: CalibrationModalProps) {
  const [minBandN, setMinBandN] = useState<number>(5);
  const [data, setData] = useState<ScoreCalibrationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadCalibration = useCallback(async () => {
    if (!isOpen) return;
    setLoading(true);
    setError(null);
    try {
      const res = await applicationApi.calibrateScores(minBandN);
      setData(res);
    } catch {
      setError("Impossible de charger la calibration IA du pipeline.");
    } finally {
      setLoading(false);
    }
  }, [isOpen, minBandN]);

  useEffect(() => {
    loadCalibration();
  }, [loadCalibration]);

  const bandRows = data
    ? BAND_ORDER.map((k) => data.bands[k]).filter((b): b is ScoreCalibrationBucket => Boolean(b))
    : [];
  const archetypeRows = data ? Object.values(data.by_archetype || {}) : [];

  return (
    <AccessibleDialog
      isOpen={isOpen}
      onClose={onClose}
      titleId="calibration-modal-title"
      title={
        <>
          <FiActivity className="text-blue-400" />
          <span>Calibration IA du Pipeline</span>
        </>
      }
      subtitle="Comparaison entre vos scores Career-Ops et vos entretiens / offres réels (hors dossiers en cours)"
      maxWidthClass="max-w-5xl"
    >
      <div className="space-y-5">
        {/* Controls */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-400">Seuil minimum par tranche (N) :</span>
            {[3, 5, 10].map((val) => (
              <button
                key={val}
                type="button"
                onClick={() => setMinBandN(val)}
                className={`px-2.5 py-1 rounded-lg border font-mono font-semibold transition-colors ${
                  minBandN === val
                    ? "bg-blue-600 text-white border-blue-500"
                    : "bg-slate-900 text-slate-300 border-slate-700 hover:bg-slate-800"
                }`}
              >
                {val}
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={loadCalibration}
            disabled={loading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 border border-slate-700 disabled:opacity-50"
          >
            <FiRefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            <span>Actualiser</span>
          </button>
        </div>

        {error && (
          <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 p-3 text-xs text-rose-300">
            {error}
          </div>
        )}

        {loading && !data ? (
          <div className="py-12 text-center text-xs text-slate-400">
            Calcul des métriques de calibration...
          </div>
        ) : data ? (
          <>
            {/* KPIs */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-3">
                <p className="text-slate-400">Candidatures scorées</p>
                <p className="text-lg font-bold text-white mt-0.5">
                  {data.matched_evaluations}
                  <span className="text-xs font-normal text-slate-400">
                    {" "}
                    / {data.total_applications}
                  </span>
                </p>
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-3">
                <p className="text-slate-400">Dossiers résolus</p>
                <p className="text-lg font-bold text-emerald-400 mt-0.5">{data.total_resolved}</p>
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-3">
                <p className="text-slate-400">En cours (exclus)</p>
                <p className="text-lg font-bold text-amber-300 mt-0.5">{data.total_in_flight}</p>
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-3">
                <p className="text-slate-400">Non évaluées</p>
                <p className="text-lg font-bold text-slate-300 mt-0.5">{data.unscored_count}</p>
              </div>
            </div>

            {data.warnings.length > 0 && (
              <div className="rounded-xl border border-amber-500/35 bg-amber-500/10 p-3.5 text-xs text-amber-200 space-y-1">
                {data.warnings.map((warn, i) => (
                  <p key={i} className="flex items-start gap-2">
                    <FiAlertTriangle className="text-amber-400 shrink-0 mt-0.5" />
                    <span>{warn}</span>
                  </p>
                ))}
              </div>
            )}

            {/* Table by Score Band */}
            <div className="rounded-xl border border-slate-800 overflow-hidden bg-slate-900/50">
              <div className="px-4 py-2.5 border-b border-slate-800 text-xs font-bold uppercase tracking-wider text-slate-300">
                Conversion par tranche de score IA
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead className="bg-slate-950/70 text-[11px] uppercase text-slate-400">
                    <tr>
                      <th className="px-3 py-2">Tranche</th>
                      <th className="px-3 py-2">Résolus</th>
                      <th className="px-3 py-2">En cours</th>
                      <th className="px-3 py-2">Entretiens</th>
                      <th className="px-3 py-2">Taux entretien</th>
                      <th className="px-3 py-2">Taux offre</th>
                    </tr>
                  </thead>
                  <BucketRows rows={bandRows} minBandN={data.min_band_n} />
                </table>
              </div>
            </div>

            {/* Table by Archetype */}
            {archetypeRows.length > 0 && (
              <div className="rounded-xl border border-slate-800 overflow-hidden bg-slate-900/50">
                <div className="px-4 py-2.5 border-b border-slate-800 text-xs font-bold uppercase tracking-wider text-slate-300">
                  Conversion par archétype de poste
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left">
                    <thead className="bg-slate-950/70 text-[11px] uppercase text-slate-400">
                      <tr>
                        <th className="px-3 py-2">Archétype</th>
                        <th className="px-3 py-2">Résolus</th>
                        <th className="px-3 py-2">En cours</th>
                        <th className="px-3 py-2">Entretiens</th>
                        <th className="px-3 py-2">Taux entretien</th>
                        <th className="px-3 py-2">Taux offre</th>
                      </tr>
                    </thead>
                    <BucketRows rows={archetypeRows} minBandN={data.min_band_n} />
                  </table>
                </div>
              </div>
            )}
          </>
        ) : null}
      </div>
    </AccessibleDialog>
  );
}
