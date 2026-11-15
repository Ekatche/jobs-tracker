"use client";

import CompanyFilters from "@/components/offers/CompanyFilters";
import type { OfferFiltersState } from "@/hooks/useOfferFilters";

export default function OffersAdvancedFilters({ filters }: { filters: OfferFiltersState }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-3 pt-4 mt-4 border-t border-slate-800 text-xs">
      <div>
        <label className="block font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
          Localisation
        </label>
        <input
          type="text"
          placeholder="Paris, Lyon, Distanciel..."
          value={filters.locationFilter}
          onChange={(e) => filters.setLocationFilter(e.target.value)}
          className="w-full px-3 py-2 bg-slate-800/80 border border-slate-700/80 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
        />
      </div>

      <div>
        <label className="block font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
          Entreprise
        </label>
        <input
          type="text"
          placeholder="Google, Thales, Doctolib..."
          value={filters.companyFilter}
          onChange={(e) => filters.setCompanyFilter(e.target.value)}
          className="w-full px-3 py-2 bg-slate-800/80 border border-slate-700/80 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
        />
      </div>

      <div>
        <label className="block font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
          Contrat
        </label>
        <select
          value={filters.contractTypeFilter}
          onChange={(e) => filters.setContractTypeFilter(e.target.value)}
          className="w-full px-3 py-2 bg-slate-800/80 border border-slate-700/80 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
        >
          {filters.profileContracts.length > 0 && (
            <option value="profile_targeted">
              🎯 Mes contrats ciblés ({filters.profileContracts.join(", ")})
            </option>
          )}
          <option value="">Tous les contrats (inclus Stages)</option>
          <option value="CDI">CDI</option>
          <option value="CDD">CDD</option>
          <option value="Freelance">Freelance</option>
          <option value="Stage">🎓 Stage</option>
          <option value="Alternance">📚 Alternance</option>
        </select>
      </div>

      <div>
        <label className="block font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
          Mode de travail
        </label>
        <select
          value={filters.workModeFilter}
          onChange={(e) => filters.setWorkModeFilter(e.target.value)}
          className="w-full px-3 py-2 bg-slate-800/80 border border-slate-700/80 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
        >
          <option value="">Tous les modes</option>
          <option value="Télétravail">Télétravail / Full Remote</option>
          <option value="Hybride">Hybride</option>
          <option value="Présentiel">Présentiel</option>
        </select>
      </div>

      <div>
        <label className="block font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
          Ajoutée en base
        </label>
        <select
          value={filters.daysRecentFilter ?? ""}
          onChange={(e) =>
            filters.setDaysRecentFilter(e.target.value ? Number(e.target.value) : undefined)
          }
          className="w-full px-3 py-2 bg-slate-800/80 border border-slate-700/80 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
        >
          <option value="">Toute la période</option>
          <option value="1">Dernières 24 heures</option>
          <option value="2">Dernières 48 heures</option>
          <option value="7">7 derniers jours</option>
          <option value="30">30 derniers jours</option>
        </select>
      </div>

      <div>
        <label
          htmlFor="offers-sort"
          className="block font-semibold text-slate-400 uppercase tracking-wider mb-1.5"
        >
          Tri
        </label>
        <select
          id="offers-sort"
          value={filters.sortFilter}
          onChange={(e) => filters.setSortFilter(e.target.value as "recent" | "relevance")}
          className="w-full px-3 py-2 bg-slate-800/80 border border-slate-700/80 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
        >
          <option value="recent">Plus récentes</option>
          <option value="relevance">Pertinence</option>
        </select>
      </div>

      <CompanyFilters
        sectorValues={filters.sectorFilter}
        onSectorChange={filters.setSectorFilter}
        companySizeValues={filters.companySizeFilter}
        onCompanySizeChange={filters.setCompanySizeFilter}
      />
    </div>
  );
}
