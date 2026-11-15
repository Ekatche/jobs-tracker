"use client";

import { Suspense, useState } from "react";
import {
  FiAlertCircle,
  FiBarChart2,
  FiClock,
  FiFilter,
  FiGrid,
  FiLayers,
  FiSearch,
  FiX,
} from "react-icons/fi";
import OfferCard from "@/components/offers/OfferCard";
import OffersFilterBar from "@/components/offers/OffersFilterBar";
import OffersPagination from "@/components/offers/OffersPagination";
import OffersStatsView from "@/components/offers/OffersStatsView";
import SkillGapsModal from "@/components/offers/SkillGapsModal";
import { useOfferFilters } from "@/hooks/useOfferFilters";
import { useOffersCatalog } from "@/hooks/useOffersCatalog";
import { ITEMS_PER_PAGE, formatCollectionTime } from "@/lib/offerFormatters";

function OffersPageContent() {
  const [showFilters, setShowFilters] = useState(false);
  const [isSkillGapsOpen, setIsSkillGapsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<"offers" | "stats">("offers");

  const filters = useOfferFilters();
  const catalog = useOffersCatalog({
    currentFilters: filters.currentFilters,
    onlySaved: filters.onlySaved,
    unseenOnly: filters.unseenOnly,
    activeTab,
  });

  return (
    <div className="min-h-screen bg-blue-night text-white p-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20">
              <FiSearch className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-white">Offres d&apos;emploi</h1>
              <p className="text-xs text-slate-400 mt-0.5">
                Explorez les opportunités scrapées et mesurez votre adéquation
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setIsSkillGapsOpen(true)}
              className="flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold transition-all border shadow-sm bg-slate-800/90 text-amber-300 hover:bg-amber-500/15 border-amber-500/30"
              title="Voir les compétences manquantes récurrentes dans vos offres évaluées"
            >
              <FiLayers className="w-3.5 h-3.5" />
              <span>Lacunes JD</span>
            </button>

            <button
              type="button"
              onClick={() => setShowFilters(!showFilters)}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all border shadow-sm ${
                showFilters || filters.locationFilter || filters.companyFilter
                  ? "bg-blue-600 text-white border-blue-500 shadow-blue-500/20"
                  : "bg-slate-800/90 text-slate-300 hover:text-white border-slate-700 hover:bg-slate-700"
              }`}
            >
              <FiFilter className="w-3.5 h-3.5" />
              <span>Filtres</span>
              {(filters.locationFilter || filters.companyFilter) && (
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              )}
            </button>
          </div>
        </div>

        <div className="flex space-x-2 mb-6">
          <button
            type="button"
            onClick={() => setActiveTab("offers")}
            className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all flex items-center gap-2 ${
              activeTab === "offers"
                ? "bg-blue-600 text-white shadow-md shadow-blue-500/20"
                : "bg-slate-800/80 text-slate-400 hover:text-white hover:bg-slate-800 border border-slate-700/60"
            }`}
          >
            <FiGrid className="w-3.5 h-3.5" />
            <span>Offres</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("stats")}
            className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all flex items-center gap-2 ${
              activeTab === "stats"
                ? "bg-blue-600 text-white shadow-md shadow-blue-500/20"
                : "bg-slate-800/80 text-slate-400 hover:text-white hover:bg-slate-800 border border-slate-700/60"
            }`}
          >
            <FiBarChart2 className="w-3.5 h-3.5" />
            <span>Statistiques</span>
          </button>
        </div>

        {activeTab === "offers" && (
          <>
            <OffersFilterBar filters={filters} showFilters={showFilters} />

            {catalog.collectionSchedule?.awaiting_first_collection && (
              <div className="mb-4 p-3 rounded-xl bg-blue-500/10 border border-blue-500/30 text-blue-200 text-xs flex items-start gap-2">
                <FiClock className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
                <span className="flex-1">
                  Votre profil vient d&apos;être créé : la recherche d&apos;offres ciblées sur votre
                  profil sera lancée le{" "}
                  {formatCollectionTime(catalog.collectionSchedule.next_collection_at)}.
                </span>
              </div>
            )}

            {catalog.regenerateError && (
              <div className="mb-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start gap-2">
                <FiAlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                <span className="flex-1">{catalog.regenerateError}</span>
                <button
                  type="button"
                  onClick={() => catalog.setRegenerateError(null)}
                  className="text-rose-400 hover:text-rose-200"
                >
                  <FiX className="w-3.5 h-3.5" />
                </button>
              </div>
            )}

            <div className="flex items-center justify-between mb-5 px-1">
              <p className="text-xs font-medium text-slate-400">
                {catalog.loading
                  ? "Chargement des offres..."
                  : `${catalog.totalOffers.toLocaleString()} offre${catalog.totalOffers > 1 ? "s" : ""} au total • ${catalog.offers.length} affichée${catalog.offers.length > 1 ? "s" : ""}`}
              </p>

              {filters.hasActiveFilters && (
                <button
                  type="button"
                  onClick={filters.resetAllFilters}
                  className="text-xs font-semibold text-blue-400 hover:text-blue-300 transition-colors"
                >
                  Effacer les filtres
                </button>
              )}
            </div>

            {catalog.loading && catalog.offers.length === 0 ? (
              <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-400" />
                <span className="ml-3 text-blue-400">Chargement des offres...</span>
              </div>
            ) : catalog.error ? (
              <div className="text-center py-12">
                <p className="text-red-400 text-lg">{catalog.error}</p>
                <button
                  type="button"
                  onClick={() => catalog.fetchOffers()}
                  className="mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-colors"
                >
                  Réessayer
                </button>
              </div>
            ) : catalog.offers.length === 0 && !filters.hasActiveFilters && !filters.unseenOnly ? (
              <div className="text-center py-12">
                <FiClock className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-400 text-lg">
                  Aucune offre adaptée à votre profil pour l&apos;instant
                </p>
                {catalog.collectionSchedule && (
                  <p className="text-gray-500 text-sm mt-2">
                    Prochaine recherche d&apos;offres le{" "}
                    {formatCollectionTime(catalog.collectionSchedule.next_collection_at)}.
                  </p>
                )}
              </div>
            ) : catalog.offers.length === 0 ? (
              <div className="text-center py-12">
                <FiSearch className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-400 text-lg">Aucune offre trouvée</p>
                <p className="text-gray-500 text-sm mt-2">
                  Essayez de modifier vos critères de recherche
                </p>
              </div>
            ) : (
              <>
                <div className={`relative ${catalog.loading ? "opacity-50 pointer-events-none" : ""}`}>
                  {catalog.loading && (
                    <div className="absolute inset-0 flex items-center justify-center z-10">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-400" />
                    </div>
                  )}
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 items-start">
                    {catalog.offers.map((offer) => (
                      <OfferCard
                        key={offer.id}
                        offer={offer}
                        currentPage={catalog.currentPage}
                        regeneratingId={catalog.regeneratingId}
                        onToggleSeen={catalog.handleToggleSeen}
                        onToggleSaveOffer={catalog.handleToggleSaveOffer}
                        onRegenerateDescription={catalog.handleRegenerateDescription}
                        onHideOffer={catalog.handleHideOffer}
                        onApplyToOffer={catalog.handleApplyToOffer}
                      />
                    ))}
                  </div>
                </div>

                <OffersPagination
                  currentPage={catalog.currentPage}
                  totalOffers={catalog.totalOffers}
                  itemsPerPage={ITEMS_PER_PAGE}
                  onPageChange={catalog.handlePageClick}
                />
              </>
            )}
          </>
        )}

        {activeTab === "stats" && (
          <OffersStatsView stats={catalog.stats} loading={catalog.statsLoading} />
        )}
      </div>

      <SkillGapsModal isOpen={isSkillGapsOpen} onClose={() => setIsSkillGapsOpen(false)} />
    </div>
  );
}

export default function OffersPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center py-24">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-400" />
        </div>
      }
    >
      <OffersPageContent />
    </Suspense>
  );
}
