"use client";

import React from "react";
import Link from "next/link";
import { Application, type PipelineSummary } from "@/types/application";
import {
  FiActivity,
  FiBriefcase,
  FiAlertCircle,
  FiTrendingUp,
  FiAward,
  FiSearch,
  FiPlus,
  FiRefreshCw,
  FiGrid,
  FiList,
  FiStar,
  FiExternalLink,
} from "react-icons/fi";

interface ApplicationsHeaderBarProps {
  applications: Application[];
  summary: PipelineSummary | null;
  scoredOffersCount: number;
  searchTerm: string;
  filterAlertOnly: boolean;
  viewMode: "kanban" | "table";
  refreshing: boolean;
  onSearchChange: (value: string) => void;
  onToggleAlertFilter: () => void;
  onOpenCalibration: () => void;
  onViewModeChange: (mode: "kanban" | "table") => void;
  onRefresh: () => void;
  onOpenNewModal: () => void;
}

/**
 * Top bar with search, follow-up filter, calibration action, Kanban/table toggle, and conversion KPIs.
 */
export function ApplicationsHeaderBar({
  applications,
  summary,
  scoredOffersCount,
  searchTerm,
  filterAlertOnly,
  viewMode,
  refreshing,
  onSearchChange,
  onToggleAlertFilter,
  onOpenCalibration,
  onViewModeChange,
  onRefresh,
  onOpenNewModal,
}: ApplicationsHeaderBarProps) {
  const activeCount = applications.filter((a) => !a.archived).length;

  return (
    <div className="border-b border-gray-800 bg-blue-night-lighter/40 px-4 py-3 flex-shrink-0">
      <div className="max-w-[1700px] mx-auto">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 mb-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white shadow-md">
              <FiBriefcase className="text-lg" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                Suivi des Candidatures
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/30">
                  {activeCount} actives
                </span>
              </h1>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <div className="relative">
              <FiSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-xs" />
              <input
                type="text"
                placeholder="Filtrer entreprise ou poste..."
                value={searchTerm}
                onChange={(e) => onSearchChange(e.target.value)}
                className="pl-8 pr-3 py-1.5 bg-gray-900/80 border border-gray-700 rounded-lg text-xs text-white placeholder-gray-400 focus:outline-none focus:border-blue-500 w-48 sm:w-60 transition-colors"
              />
            </div>

            <button
              onClick={onToggleAlertFilter}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors border ${
                filterAlertOnly
                  ? "bg-amber-500/25 text-amber-300 border-amber-500/50"
                  : "bg-gray-800 text-gray-300 border-gray-700 hover:bg-gray-700"
              }`}
              title="Afficher uniquement les candidatures nécessitant une action (Relance J+7 ou Remerciement J+1)"
            >
              <FiAlertCircle className="text-xs" />
              <span>Relances</span>
              {summary && summary.follow_ups_due_count > 0 && (
                <span className="px-1.5 py-0.2 rounded-full bg-amber-500 text-black text-[10px] font-bold">
                  {summary.follow_ups_due_count}
                </span>
              )}
            </button>

            <button
              type="button"
              onClick={onOpenCalibration}
              className="px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors border bg-gray-800 text-indigo-300 border-indigo-500/30 hover:bg-indigo-500/15"
              title="Comparer vos scores d'adéquation IA aux entretiens réellement obtenus"
            >
              <FiActivity className="text-xs" />
              <span>Calibration IA</span>
            </button>

            <div className="flex items-center bg-gray-900 border border-gray-700 rounded-lg p-0.5">
              <button
                onClick={() => onViewModeChange("kanban")}
                className={`px-2.5 py-1 rounded text-xs font-semibold flex items-center gap-1 transition-colors ${
                  viewMode === "kanban" ? "bg-blue-600 text-white shadow-sm" : "text-gray-400 hover:text-white"
                }`}
                title="Vue Kanban"
              >
                <FiGrid className="text-xs" /> Kanban
              </button>
              <button
                onClick={() => onViewModeChange("table")}
                className={`px-2.5 py-1 rounded text-xs font-semibold flex items-center gap-1 transition-colors ${
                  viewMode === "table" ? "bg-blue-600 text-white shadow-sm" : "text-gray-400 hover:text-white"
                }`}
                title="Vue Tableau"
              >
                <FiList className="text-xs" /> Tableau
              </button>
            </div>

            <button
              onClick={onRefresh}
              disabled={refreshing}
              className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors border border-gray-700"
              title="Actualiser les données"
            >
              <FiRefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
            </button>

            <button
              onClick={onOpenNewModal}
              className="px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-sm"
            >
              <FiPlus className="w-3.5 h-3.5" />
              <span>Nouvelle candidature</span>
            </button>
          </div>
        </div>

        {/* Career-Ops conversion KPI banner */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5 pt-2 border-t border-gray-800/80">
          <div className="bg-gray-900/60 px-3 py-1.5 rounded-lg border border-gray-800 flex items-center justify-between">
            <span className="text-[11px] text-gray-400">Actives</span>
            <span className="text-sm font-bold text-white">
              {summary ? summary.total_active : activeCount}
            </span>
          </div>

          <div className="bg-gray-900/60 px-3 py-1.5 rounded-lg border border-gray-800 flex items-center justify-between">
            <span className="text-[11px] text-gray-400 flex items-center gap-1">
              <FiTrendingUp className="text-blue-400 text-xs" /> Taux d&apos;entretien
            </span>
            <span className="text-sm font-bold text-blue-400">
              {summary ? `${summary.interview_conversion_rate}%` : "0%"}
            </span>
          </div>

          <div className="bg-gray-900/60 px-3 py-1.5 rounded-lg border border-gray-800 flex items-center justify-between">
            <span className="text-[11px] text-gray-400 flex items-center gap-1">
              <FiAward className="text-emerald-400 text-xs" /> Taux d&apos;offres
            </span>
            <span className="text-sm font-bold text-emerald-400">
              {summary ? `${summary.offer_conversion_rate}%` : "0%"}
            </span>
          </div>

          <div
            className={`px-3 py-1.5 rounded-lg border flex items-center justify-between transition-colors ${
              summary && summary.follow_ups_due_count > 0
                ? "bg-amber-500/15 border-amber-500/30 text-amber-300"
                : "bg-gray-900/60 border-gray-800 text-gray-400"
            }`}
          >
            <span className="text-[11px] flex items-center gap-1">
              <FiAlertCircle className="text-amber-400 text-xs" /> Relances J+7
            </span>
            <span className="text-sm font-bold text-white">
              {summary ? summary.follow_ups_due_count : 0}
            </span>
          </div>

          <Link
            href="/offers"
            className="bg-gray-900/60 hover:bg-gray-800 px-3 py-1.5 rounded-lg border border-gray-800 flex items-center justify-between group transition-colors"
            title="Consulter les offres scorées prêtes à postuler"
          >
            <span className="text-[11px] text-gray-400 group-hover:text-yellow-300 flex items-center gap-1">
              <FiStar className="text-yellow-400 text-xs" /> Offres Scorées
            </span>
            <span className="text-sm font-bold text-yellow-400 flex items-center gap-1">
              {scoredOffersCount}
              <FiExternalLink className="text-[10px] text-gray-500 group-hover:text-yellow-400" />
            </span>
          </Link>
        </div>
      </div>
    </div>
  );
}
