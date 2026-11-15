"use client";

import {
  FiBookmark,
  FiCheckCircle,
  FiEye,
  FiLayers,
  FiMapPin,
  FiSearch,
  FiStar,
  FiTarget,
  FiX,
  FiZap,
} from "react-icons/fi";
import type { OfferFiltersState } from "@/hooks/useOfferFilters";
import OffersAdvancedFilters from "@/components/offers/OffersAdvancedFilters";
import { RELEVANCE_LEVEL_OPTIONS } from "@/lib/relevanceLevels";

interface OffersFilterBarProps {
  filters: OfferFiltersState;
  showFilters: boolean;
}

export default function OffersFilterBar({ filters, showFilters }: OffersFilterBarProps) {
  const isDefaultQuickMode =
    !filters.onlySaved &&
    !filters.interactionStatus &&
    !filters.daysRecentFilter &&
    filters.minScoreFilter === undefined &&
    !filters.unseenOnly;

  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 mb-6 shadow-md backdrop-blur-sm">
      <div className="relative">
        <FiSearch className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4" />
        <input
          type="text"
          placeholder="Rechercher des offres (poste, compétences, mots-clés...)"
          value={filters.searchTerm}
          onChange={(e) => filters.setSearchTerm(e.target.value)}
          className="w-full pl-10 pr-10 py-2.5 bg-slate-800/80 border border-slate-700/80 rounded-xl text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 text-sm transition-all"
        />
        {filters.searchTerm && (
          <button
            type="button"
            onClick={() => filters.setSearchTerm("")}
            className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
          >
            <FiX className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Quick filter pills */}
      <div className="flex flex-wrap items-center gap-2 mt-3 pt-3 border-t border-slate-800/80">
        <button
          type="button"
          onClick={filters.resetQuickPills}
          className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 border ${
            isDefaultQuickMode
              ? "bg-blue-600 text-white border-blue-500 shadow-sm shadow-blue-500/20"
              : "bg-slate-800/70 text-slate-400 hover:text-white border-slate-700/60 hover:bg-slate-800"
          }`}
        >
          <FiLayers className="w-3.5 h-3.5" />
          <span>Toutes</span>
        </button>

        <button
          type="button"
          onClick={() => {
            filters.setOnlySaved(!filters.onlySaved);
            filters.setInteractionStatus(undefined);
          }}
          className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 border ${
            filters.onlySaved
              ? "bg-amber-500/20 text-amber-300 border-amber-500/40 shadow-sm shadow-amber-500/10"
              : "bg-slate-800/70 text-slate-400 hover:text-white border-slate-700/60 hover:bg-slate-800"
          }`}
        >
          <FiBookmark
            className={`w-3.5 h-3.5 ${filters.onlySaved ? "fill-amber-400 text-amber-400" : ""}`}
          />
          <span>⭐ Favoris</span>
        </button>

        <button
          type="button"
          onClick={() => filters.setDaysRecentFilter(filters.daysRecentFilter === 2 ? undefined : 2)}
          className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 border ${
            filters.daysRecentFilter === 2
              ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40 shadow-sm shadow-emerald-500/10"
              : "bg-slate-800/70 text-slate-400 hover:text-white border-slate-700/60 hover:bg-slate-800"
          }`}
          title="Offres ajoutées dans votre base au cours des dernières 48 heures"
        >
          <FiZap className="w-3.5 h-3.5 text-emerald-400" />
          <span>✨ Nouvelles (&lt; 48h)</span>
        </button>

        <button
          type="button"
          onClick={() =>
            filters.setMinScoreFilter(filters.minScoreFilter === 4.0 ? undefined : 4.0)
          }
          className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 border ${
            filters.minScoreFilter === 4.0
              ? "bg-indigo-500/20 text-indigo-300 border-indigo-500/40 shadow-sm shadow-indigo-500/10"
              : "bg-slate-800/70 text-slate-400 hover:text-white border-slate-700/60 hover:bg-slate-800"
          }`}
        >
          <FiStar className="w-3.5 h-3.5 text-indigo-400" />
          <span>Match IA ≥ 4.0</span>
        </button>

        <button
          type="button"
          onClick={() => {
            filters.setInteractionStatus(
              filters.interactionStatus === "applied" ? undefined : "applied"
            );
            filters.setOnlySaved(false);
          }}
          className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 border ${
            filters.interactionStatus === "applied"
              ? "bg-teal-500/20 text-teal-300 border-teal-500/40 shadow-sm shadow-teal-500/10"
              : "bg-slate-800/70 text-slate-400 hover:text-white border-slate-700/60 hover:bg-slate-800"
          }`}
        >
          <FiCheckCircle className="w-3.5 h-3.5 text-teal-400" />
          <span>Postulées</span>
        </button>

        <button
          type="button"
          onClick={() => filters.setUnseenOnly(!filters.unseenOnly)}
          className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 border ${
            filters.unseenOnly
              ? "bg-sky-500/20 text-sky-300 border-sky-500/40 shadow-sm shadow-sky-500/10"
              : "bg-slate-800/70 text-slate-400 hover:text-white border-slate-700/60 hover:bg-slate-800"
          }`}
          title="N'afficher que les offres pas encore marquées comme vues"
        >
          <FiEye className="w-3.5 h-3.5 text-sky-400" />
          <span>Non vues</span>
        </button>

        <div role="group" aria-label="Pertinence" className="flex flex-wrap items-center gap-2">
          {RELEVANCE_LEVEL_OPTIONS.map((level) => {
            const active = filters.relevanceLevelFilter.includes(level.value);
            return (
              <button
                key={level.value}
                type="button"
                aria-pressed={active}
                onClick={() =>
                  filters.setRelevanceLevelFilter(
                    active
                      ? filters.relevanceLevelFilter.filter((v) => v !== level.value)
                      : [...filters.relevanceLevelFilter, level.value]
                  )
                }
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 border ${
                  active
                    ? `${level.className} shadow-sm`
                    : "bg-slate-800/70 text-slate-400 hover:text-white border-slate-700/60 hover:bg-slate-800"
                }`}
              >
                {!active && <span className={`w-2 h-2 rounded-full ${level.dotClassName}`} />}
                <span>{level.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {filters.contractTypeFilter === "profile_targeted" && filters.profileContracts.length > 0 && (
        <div className="mt-3 pt-3 border-t border-slate-800/80">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs bg-indigo-600/20 text-indigo-300 border border-indigo-500/40">
            <FiTarget className="w-3 h-3" />
            Filtré sur vos contrats ciblés ({filters.profileContracts.join(", ")})
            <button
              type="button"
              onClick={() => filters.setContractTypeFilter("")}
              className="ml-1 hover:text-white"
              title="Retirer ce filtre"
            >
              ×
            </button>
          </span>
        </div>
      )}

      {filters.profileRoles.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 mt-3 pt-3 border-t border-slate-800/80">
          <span className="text-[11px] text-slate-400 flex items-center gap-1 font-medium mr-1">
            <FiTarget className="w-3 h-3 text-indigo-400" /> Postes cibles de votre profil :
          </span>
          {filters.profileRoles.map((role, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => filters.setSearchTerm(role)}
              className={`px-2.5 py-1 rounded-lg text-xs transition-all border ${
                filters.searchTerm.toLowerCase() === role.toLowerCase()
                  ? "bg-indigo-600 text-white border-indigo-500 font-semibold shadow-sm shadow-indigo-500/30"
                  : "bg-slate-800/80 text-slate-300 hover:text-white hover:bg-slate-700 border-slate-700/60"
              }`}
            >
              {role}
            </button>
          ))}
          {filters.profileLocations.length > 0 && (
            <div className="flex items-center gap-1 ml-2">
              <span className="text-[11px] text-slate-500">|</span>
              {filters.profileLocations.map((loc, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() =>
                    filters.setLocationFilter(
                      filters.locationFilter.toLowerCase() === loc.toLowerCase() ? "" : loc
                    )
                  }
                  className={`px-2 py-0.5 rounded-md text-[11px] transition-all border flex items-center gap-1 ${
                    filters.locationFilter.toLowerCase() === loc.toLowerCase()
                      ? "bg-blue-600 text-white border-blue-500 font-semibold"
                      : "bg-slate-800/50 text-slate-400 hover:text-slate-200 border-slate-700/50"
                  }`}
                >
                  <FiMapPin className="w-2.5 h-2.5" />
                  <span>{loc}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {filters.profileEmpty && (
        <div className="mt-3 pt-3 border-t border-slate-800/80 text-xs text-amber-300/90 flex items-center gap-1.5">
          <FiTarget className="w-3 h-3" />
          <span>
            Complétez vos postes ciblés ou votre localisation dans votre profil pour affiner les
            offres affichées.
          </span>
        </div>
      )}

      {showFilters && <OffersAdvancedFilters filters={filters} />}
    </div>
  );
}
