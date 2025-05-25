"use client";

import { useState, useEffect, useCallback } from "react";
import {
  jobOffersApi,
  type JobOffer,
  type JobOfferFilter,
  type JobOfferStats,
} from "@/lib/api";
import {
  FiSearch,
  FiMapPin,
  FiBriefcase,
  FiCalendar,
  FiExternalLink,
  FiFilter,
  FiBarChart2,
  FiGrid,
  FiTrash2,
  FiPlus,
} from "react-icons/fi";
import { PrefilledData } from "@/components/dashboard/NewApplicationModal";

const ITEMS_PER_PAGE = 16; // 4x4 grille

export default function OffersPage() {
  const [offers, setOffers] = useState<JobOffer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filtres et recherche
  const [searchTerm, setSearchTerm] = useState("");
  const [locationFilter, setLocationFilter] = useState("");
  const [companyFilter, setCompanyFilter] = useState("");

  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const [totalOffers, setTotalOffers] = useState(0);

  // UI
  const [showFilters, setShowFilters] = useState(false);
  const [activeTab, setActiveTab] = useState<"offers" | "stats">("offers");

  // Stats
  const [stats, setStats] = useState<JobOfferStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);

  // Fonction pour charger le nombre total d'offres
  const fetchTotalCount = useCallback(async () => {
    try {
      const filters = {
        keywords: searchTerm || undefined,
        location: locationFilter || undefined,
        company: companyFilter || undefined,
      };

      const countData = await jobOffersApi.getCount(filters);
      setTotalOffers(countData.total);
    } catch (err) {
      console.error("Erreur lors du comptage des offres:", err);
      setTotalOffers(0);
    }
  }, [searchTerm, locationFilter, companyFilter]);

  // Fonction pour charger les offres
  const fetchOffers = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const filters: JobOfferFilter = {
        keywords: searchTerm || undefined,
        location: locationFilter || undefined,
        company: companyFilter || undefined,
        limit: ITEMS_PER_PAGE,
        skip: (currentPage - 1) * ITEMS_PER_PAGE,
      };

      const data = await jobOffersApi.getAll(filters);
      setOffers(data);
    } catch (err) {
      setError("Erreur lors du chargement des offres d'emploi");
      console.error("Erreur:", err);
    } finally {
      setLoading(false);
    }
  }, [searchTerm, locationFilter, companyFilter, currentPage]);

  // Fonction pour charger les statistiques
  const fetchStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      const statsData = await jobOffersApi.getStats();
      setStats(statsData);
    } catch (err) {
      console.error("Erreur lors du chargement des statistiques:", err);
    } finally {
      setStatsLoading(false);
    }
  }, []);

  // Fonction pour supprimer une offre
  const handleDeleteOffer = async (offerId: string) => {
    if (!confirm("Êtes-vous sûr de vouloir supprimer cette offre ?")) return;

    try {
      await jobOffersApi.delete(offerId);
      // Recharger les offres et le total
      await Promise.all([fetchOffers(), fetchTotalCount()]);
    } catch (err) {
      console.error("Erreur lors de la suppression:", err);
      alert("Erreur lors de la suppression de l'offre");
    }
  };

  // Fonction pour ouvrir la modal de candidature avec des données pré-remplies
  const handleApplyToOffer = (offer: JobOffer) => {
    const prefilledData: PrefilledData = {
      company: offer.entreprise,
      position: offer.poste,
      location: offer.localisation,
      url: offer.url,
    };

    // Émettre un événement pour ouvrir la modal avec les données pré-remplies
    const event = new CustomEvent("open-application-modal", {
      detail: prefilledData,
    });
    window.dispatchEvent(event);
  };

  // Charger les offres et le total au montage et quand les filtres changent
  useEffect(() => {
    if (activeTab === "offers") {
      Promise.all([fetchOffers(), fetchTotalCount()]);
    } else if (activeTab === "stats") {
      fetchStats();
    }
  }, [fetchOffers, fetchTotalCount, fetchStats, activeTab]);

  // Reset pagination quand on change les filtres
  useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm, locationFilter, companyFilter]);

  // Fonction pour formater la date
  const formatDate = (dateString: string) => {
    if (!dateString || dateString === "Non spécifié") {
      return "Date non spécifiée";
    }

    // Si c'est une date relative (ex: "il y a 2 jours")
    if (dateString.includes("il y a") || dateString.includes("ago")) {
      return dateString;
    }

    try {
      // Essayer de parser comme date ISO
      const date = new Date(dateString);
      if (!isNaN(date.getTime())) {
        return date.toLocaleDateString("fr-FR");
      }
      // Sinon retourner tel quel
      return dateString;
    } catch {
      return dateString;
    }
  };

  // Composant carte d'offre (modifié)
  const OfferCard = ({ offer }: { offer: JobOffer }) => (
    <div className="bg-blue-night-lighter rounded-lg p-6 shadow-lg hover:shadow-xl transition-all duration-300 border border-gray-700 hover:border-blue-500 relative group">
      {/* Bouton supprimer */}
      <button
        onClick={() => handleDeleteOffer(offer.id)}
        className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity bg-red-600 hover:bg-red-500 text-white p-2 rounded-lg"
        title="Supprimer cette offre"
      >
        <FiTrash2 className="w-4 h-4" />
      </button>

      <div className="flex flex-col h-full">
        {/* En-tête de la carte */}
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-white mb-2 line-clamp-2 pr-8">
            {offer.poste}
          </h3>

          <div className="flex items-center gap-2 mb-3">
            <FiBriefcase className="text-blue-400 flex-shrink-0" />
            <span className="text-gray-300 truncate">{offer.entreprise}</span>
          </div>

          {offer.localisation && (
            <div className="flex items-center gap-2 mb-3">
              <FiMapPin className="text-blue-400 flex-shrink-0" />
              <span className="text-gray-300 truncate">
                {offer.localisation}
              </span>
            </div>
          )}

          <div className="flex items-center gap-2 mb-4">
            <FiCalendar className="text-blue-400 flex-shrink-0" />
            <span className="text-gray-400 text-sm">
              {formatDate(offer.date || "")}
            </span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-2 pt-4 border-t border-gray-600">
          {offer.url && (
            <a
              href={offer.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2"
            >
              <FiExternalLink className="w-4 h-4" />
              Voir l'offre
            </a>
          )}

          <button
            onClick={() => handleApplyToOffer(offer)}
            className="bg-green-600 hover:bg-green-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
            title="Postuler à cette offre"
          >
            <FiPlus className="w-4 h-4" />
            Postuler
          </button>
        </div>
      </div>
    </div>
  );

  // Composant pagination
  const Pagination = () => {
    const totalPages = Math.ceil(totalOffers / ITEMS_PER_PAGE);

    if (totalPages <= 1) return null;

    return (
      <div className="flex justify-center items-center gap-2 mt-8">
        <button
          onClick={() => setCurrentPage((prev) => Math.max(1, prev - 1))}
          disabled={currentPage === 1}
          className="px-4 py-2 rounded-lg bg-blue-night-lighter text-white disabled:opacity-50 disabled:cursor-not-allowed hover:bg-blue-600 transition-colors"
        >
          Précédent
        </button>

        <span className="px-4 py-2 text-gray-300">
          Page {currentPage} sur {totalPages}
        </span>

        <button
          onClick={() =>
            setCurrentPage((prev) => Math.min(totalPages, prev + 1))
          }
          disabled={currentPage === totalPages}
          className="px-4 py-2 rounded-lg bg-blue-night-lighter text-white disabled:opacity-50 disabled:cursor-not-allowed hover:bg-blue-600 transition-colors"
        >
          Suivant
        </button>
      </div>
    );
  };

  // Composant statistiques
  const StatsContent = () => (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 xl:grid-cols-4 gap-6">
      {/* Carte total d'offres */}
      <div className="bg-blue-night-lighter rounded-lg p-6 border border-gray-700">
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="text-gray-400 text-sm">Total des offres</p>
            <p className="text-3xl font-bold text-blue-400">
              {statsLoading
                ? "..."
                : stats?.total_offers?.toLocaleString() || 0}
            </p>
          </div>
          <FiGrid className="w-10 h-10 text-blue-400" />
        </div>
      </div>

      {/* Top websites */}
      <div className="bg-blue-night-lighter rounded-lg p-6 border border-gray-700">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white">Top Sites Web</h3>
          <FiExternalLink className="w-6 h-6 text-green-400" />
        </div>
        {statsLoading ? (
          <div className="animate-pulse space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex justify-between">
                <div className="h-4 bg-gray-600 rounded w-2/3"></div>
                <div className="h-4 bg-gray-600 rounded w-8"></div>
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-3 max-h-48 overflow-y-auto">
            {stats?.top_websites?.slice(0, 8).map((website, index) => (
              <div
                key={website._id}
                className="flex items-center justify-between"
              >
                <span className="text-gray-300 truncate text-sm">
                  {website._id}
                </span>
                <span className="text-green-400 font-medium text-sm">
                  {website.count}
                </span>
              </div>
            )) || <p className="text-gray-400 text-sm">Aucune donnée</p>}
          </div>
        )}
      </div>

      {/* Top companies */}
      <div className="bg-blue-night-lighter rounded-lg p-6 border border-gray-700">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white">Top Entreprises</h3>
          <FiBriefcase className="w-6 h-6 text-purple-400" />
        </div>
        {statsLoading ? (
          <div className="animate-pulse space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex justify-between">
                <div className="h-4 bg-gray-600 rounded w-2/3"></div>
                <div className="h-4 bg-gray-600 rounded w-8"></div>
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-3 max-h-48 overflow-y-auto">
            {stats?.top_companies?.slice(0, 8).map((company, index) => (
              <div
                key={company._id}
                className="flex items-center justify-between"
              >
                <span className="text-gray-300 truncate text-sm">
                  {company._id}
                </span>
                <span className="text-purple-400 font-medium text-sm">
                  {company.count}
                </span>
              </div>
            )) || <p className="text-gray-400 text-sm">Aucune donnée</p>}
          </div>
        )}
      </div>

      {/* Top cities */}
      <div className="bg-blue-night-lighter rounded-lg p-6 border border-gray-700">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white">Top Villes</h3>
          <FiMapPin className="w-6 h-6 text-orange-400" />
        </div>
        {statsLoading ? (
          <div className="animate-pulse space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex justify-between">
                <div className="h-4 bg-gray-600 rounded w-2/3"></div>
                <div className="h-4 bg-gray-600 rounded w-8"></div>
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-3 max-h-48 overflow-y-auto">
            {stats?.top_cities?.slice(0, 8).map((city, index) => (
              <div key={city._id} className="flex items-center justify-between">
                <span className="text-gray-300 truncate text-sm">
                  {city._id}
                </span>
                <span className="text-orange-400 font-medium text-sm">
                  {city.count}
                </span>
              </div>
            )) || <p className="text-gray-400 text-sm">Aucune donnée</p>}
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-blue-night text-white p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center space-x-2">
            <FiSearch className="w-6 h-6 text-blue-400" />
            <h1 className="text-2xl font-semibold">Offres d'emploi</h1>
          </div>

          <button
            onClick={() => setShowFilters(!showFilters)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-night-lighter rounded-lg hover:bg-blue-600 transition-colors"
          >
            <FiFilter className="w-4 h-4" />
            Filtres
          </button>
        </div>

        {/* Onglets */}
        <div className="flex space-x-1 mb-6">
          <button
            onClick={() => setActiveTab("offers")}
            className={`px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2 ${
              activeTab === "offers"
                ? "bg-blue-600 text-white"
                : "bg-blue-night-lighter text-gray-300 hover:text-white"
            }`}
          >
            <FiGrid className="w-4 h-4" />
            Offres
          </button>
          <button
            onClick={() => setActiveTab("stats")}
            className={`px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2 ${
              activeTab === "stats"
                ? "bg-blue-600 text-white"
                : "bg-blue-night-lighter text-gray-300 hover:text-white"
            }`}
          >
            <FiBarChart2 className="w-4 h-4" />
            Statistiques
          </button>
        </div>

        {/* Contenu conditionnel selon l'onglet */}
        {activeTab === "offers" && (
          <>
            {/* Barre de recherche et filtres */}
            <div className="bg-blue-night-lighter rounded-lg p-4 mb-6">
              {/* Recherche principale */}
              <div className="relative mb-4">
                <FiSearch className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  placeholder="Rechercher des offres (poste, compétences...)"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-10 pr-4 py-3 bg-blue-night border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              {/* Filtres détaillés */}
              {showFilters && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-gray-600">
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Localisation
                    </label>
                    <input
                      type="text"
                      placeholder="Ex: Paris, Lyon, Remote..."
                      value={locationFilter}
                      onChange={(e) => setLocationFilter(e.target.value)}
                      className="w-full px-4 py-2 bg-blue-night border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Entreprise
                    </label>
                    <input
                      type="text"
                      placeholder="Nom de l'entreprise..."
                      value={companyFilter}
                      onChange={(e) => setCompanyFilter(e.target.value)}
                      className="w-full px-4 py-2 bg-blue-night border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Statistiques */}
            <div className="flex items-center justify-between mb-6">
              <p className="text-gray-400">
                {loading
                  ? "Chargement..."
                  : `${totalOffers} offres au total • ${offers.length} affichées`}
              </p>

              {(searchTerm || locationFilter || companyFilter) && (
                <button
                  onClick={() => {
                    setSearchTerm("");
                    setLocationFilter("");
                    setCompanyFilter("");
                  }}
                  className="text-blue-400 hover:text-blue-300 text-sm"
                >
                  Effacer les filtres
                </button>
              )}
            </div>

            {/* Contenu principal */}
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-400"></div>
                <span className="ml-3 text-blue-400">
                  Chargement des offres...
                </span>
              </div>
            ) : error ? (
              <div className="text-center py-12">
                <p className="text-red-400 text-lg">{error}</p>
                <button
                  onClick={fetchOffers}
                  className="mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-colors"
                >
                  Réessayer
                </button>
              </div>
            ) : offers.length === 0 ? (
              <div className="text-center py-12">
                <FiSearch className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-400 text-lg">Aucune offre trouvée</p>
                <p className="text-gray-500 text-sm mt-2">
                  Essayez de modifier vos critères de recherche
                </p>
              </div>
            ) : (
              <>
                {/* Grille des offres 4x4 */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                  {offers.map((offer) => (
                    <OfferCard key={offer.id} offer={offer} />
                  ))}
                </div>

                {/* Pagination */}
                <Pagination />
              </>
            )}
          </>
        )}

        {/* Contenu de l'onglet Statistiques */}
        {activeTab === "stats" && <StatsContent />}
      </div>
    </div>
  );
}
