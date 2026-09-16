"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
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
  FiRefreshCw,
  FiEye,
  FiZap,
  FiX,
  FiBookmark,
  FiEyeOff,
} from "react-icons/fi";
import { PrefilledData } from "@/components/dashboard/NewApplicationModal";

function cleanDescriptionPreview(text: string | undefined): string {
  if (!text || text === "Non spécifié") return "";
  return text
    // Strip numbered list markers with bold like "1. **RÉSUMÉ :**"
    .replace(/^\s*\d+\.\s*\*\*.*?\*\*\s*:?/gim, "")
    // Strip bold headers like "**RÉSUMÉ :**" or "**MISSIONS :**"
    .replace(/\*\*.*?\*\*\s*:?/gi, "")
    // Strip leading bullets
    .replace(/^\s*[•\-\*]\s+/gm, "")
    // Strip consecutive empty lines
    .replace(/\n\s*\n/g, "\n")
    .trim();
}

const ITEMS_PER_PAGE = 16; // 4x4 grille

export default function OffersPage() {
  const [offers, setOffers] = useState<JobOffer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filtres et recherche
  const [searchTerm, setSearchTerm] = useState("");
  const [locationFilter, setLocationFilter] = useState("");
  const [companyFilter, setCompanyFilter] = useState("");
  const [onlySaved, setOnlySaved] = useState(false);
  const [minScoreFilter, setMinScoreFilter] = useState<number | undefined>(undefined);

  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const [totalOffers, setTotalOffers] = useState(0);

  // UI
  const [showFilters, setShowFilters] = useState(false);
  const [activeTab, setActiveTab] = useState<"offers" | "stats">("offers");
  const [regeneratingId, setRegeneratingId] = useState<string | null>(null);

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
        only_saved: onlySaved || undefined,
        min_score: minScoreFilter,
      };

      const countData = await jobOffersApi.getCount(filters);
      setTotalOffers(countData.total);
    } catch (err) {
      console.error("Erreur lors du comptage des offres:", err);
      setTotalOffers(0);
    }
  }, [searchTerm, locationFilter, companyFilter, onlySaved, minScoreFilter]);

  // Fonction pour charger les offres
  const fetchOffers = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const filters: JobOfferFilter = {
        keywords: searchTerm || undefined,
        location: locationFilter || undefined,
        company: companyFilter || undefined,
        only_saved: onlySaved || undefined,
        min_score: minScoreFilter,
        limit: ITEMS_PER_PAGE,
        skip: (currentPage - 1) * ITEMS_PER_PAGE,
      };

      const data = await jobOffersApi.getAll(filters);
      setOffers(data);
    } catch (err) {
      setError("Erreur lors du chargement des offres d'emploi");
      console.error("💥 Erreur:", err);
    } finally {
      setLoading(false);
    }
  }, [searchTerm, locationFilter, companyFilter, onlySaved, minScoreFilter, currentPage]);

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

  // ✅ Multi-tenant hide: masque l'offre pour le compte candidat sans impacter la plateforme
  const handleHideOffer = async (offerId: string) => {
    try {
      await jobOffersApi.setInteraction(offerId, "hidden");

      // Supprimer l'offre de la vue locale immédiatement
      setOffers((prevOffers) =>
        prevOffers.filter((offer) => offer.id !== offerId)
      );

      // Recharger le total pour avoir le bon compte
      await fetchTotalCount();
    } catch (err) {
      console.error("💥 Erreur lors du masquage de l'offre:", err);
      alert("Erreur lors du masquage de l'offre");
    }
  };

  // ✅ Multi-tenant save / bookmark toggle
  const handleToggleSaveOffer = async (offerId: string, currentInteraction?: string | null) => {
    const isCurrentlySaved = currentInteraction === "saved";
    const nextStatus = isCurrentlySaved ? "none" : "saved";

    try {
      await jobOffersApi.setInteraction(offerId, nextStatus);
      setOffers((prevOffers) =>
        prevOffers.map((offer) =>
          offer.id === offerId
            ? { ...offer, user_interaction: nextStatus === "none" ? null : "saved" }
            : offer
        )
      );
      if (onlySaved && isCurrentlySaved) {
        setOffers((prevOffers) => prevOffers.filter((offer) => offer.id !== offerId));
        await fetchTotalCount();
      }
    } catch (err) {
      console.error("💥 Erreur lors de la mise à jour des favoris:", err);
    }
  };

  // 🔄 Régénération de description sur demande
  const handleRegenerateDescription = async (offerId: string) => {
    try {
      setRegeneratingId(offerId);
      const res = await jobOffersApi.regenerateDescription(offerId);
      setOffers((prevOffers) =>
        prevOffers.map((offer) => {
          if (offer.id === offerId) {
            return {
              ...offer,
              ...(res.offer || {}),
              description: res.description || offer.description,
              is_active: res.is_active,
            };
          }
          return offer;
        })
      );
    } catch (err: unknown) {
      console.error("💥 Erreur lors de la régénération:", err);
      const msg =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : null;
      alert(msg || "Erreur lors de la régénération de la description");
    } finally {
      setRegeneratingId(null);
    }
  };

  // Fonction pour ouvrir la modal de candidature avec des données pré-remplies
  const handleApplyToOffer = (offer: JobOffer) => {
    const prefilledData: PrefilledData = {
      company: offer.entreprise,
      position: offer.poste,
      location: offer.localisation,
      url: offer.url,
      description: offer.description && offer.description !== "Non spécifié" ? offer.description : undefined,
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

  // Composant carte d'offre enrichie avec description lisible, tags et actions
  const OfferCard = ({ offer }: { offer: JobOffer }) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const cleanedDescription = cleanDescriptionPreview(offer.description);

    const isSaved = offer.user_interaction === "saved";

    return (
      <div className="bg-slate-900/80 hover:bg-slate-900/95 rounded-2xl p-5 shadow-lg hover:shadow-xl transition-all duration-200 border border-slate-800 hover:border-blue-500/40 relative group flex flex-col justify-between backdrop-blur-sm">
        {/* Quick action buttons */}
        <div className="absolute top-3 right-3 flex items-center gap-1 z-10">
          <button
            onClick={() => handleToggleSaveOffer(offer.id, offer.user_interaction)}
            className={`p-1.5 rounded-lg border transition-all ${
              isSaved
                ? "bg-amber-500/20 text-amber-300 border-amber-500/40 opacity-100"
                : "bg-slate-800 hover:bg-amber-500/20 text-slate-400 hover:text-amber-300 border-slate-700 opacity-0 group-hover:opacity-100"
            }`}
            title={isSaved ? "Retirer des favoris" : "Sauvegarder cette offre"}
          >
            <FiBookmark className={`w-3.5 h-3.5 ${isSaved ? "fill-amber-400 text-amber-400" : ""}`} />
          </button>
          <button
            onClick={() => handleRegenerateDescription(offer.id)}
            disabled={regeneratingId === offer.id}
            className="opacity-0 group-hover:opacity-100 bg-slate-800 hover:bg-blue-600 text-slate-300 hover:text-white p-1.5 rounded-lg border border-slate-700 transition-all disabled:opacity-50"
            title="Régénérer la description par IA"
          >
            <FiRefreshCw className={`w-3.5 h-3.5 ${regeneratingId === offer.id ? "animate-spin" : ""}`} />
          </button>
          <button
            onClick={() => handleHideOffer(offer.id)}
            className="opacity-0 group-hover:opacity-100 bg-slate-800 hover:bg-rose-600 text-slate-300 hover:text-white p-1.5 rounded-lg border border-slate-700 transition-all"
            title="Masquer cette offre pour mon compte"
          >
            <FiEyeOff className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="flex flex-col h-full">
          <div className="flex-1">
            {/* Header: Company Avatar + Company Name + Location */}
            <div className="flex items-center gap-3 pr-12">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600/80 to-indigo-600/80 border border-white/10 flex items-center justify-center font-bold text-white text-sm shrink-0 shadow-sm shadow-blue-500/10">
                {offer.entreprise ? offer.entreprise.charAt(0).toUpperCase() : "?"}
              </div>
              <div className="min-w-0 flex-1">
                <h4 className="text-xs font-semibold text-slate-300 truncate">
                  {offer.entreprise}
                </h4>
                {offer.localisation && offer.localisation !== "Non spécifié" && (
                  <div className="flex items-center gap-1 text-slate-400 text-[11px] truncate mt-0.5">
                    <FiMapPin className="w-3 h-3 text-blue-400 shrink-0" />
                    <span className="truncate">{offer.localisation}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Title */}
            <Link href={`/offers/${offer.id}`} className="group/title block">
              <h3 className="text-base font-bold text-white group-hover/title:text-blue-400 transition-colors line-clamp-2 mt-3 mb-2.5 leading-snug">
                {offer.poste}
              </h3>
            </Link>

            {/* Badges: Match Score, Contrat, Mode de travail, Salaire */}
            <div className="flex flex-wrap gap-1.5 mb-3 items-center">
              {offer.evaluation_score !== undefined && offer.evaluation_score !== null ? (
                <span
                  className={`px-2.5 py-0.5 text-xs font-bold rounded-lg border flex items-center gap-1.5 shadow-sm ${
                    offer.evaluation_score >= 4.0
                      ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/35"
                      : offer.evaluation_score >= 3.0
                      ? "bg-amber-500/15 text-amber-300 border-amber-500/35"
                      : "bg-rose-500/15 text-rose-300 border-rose-500/35"
                  }`}
                  title="Score d'adéquation calculé par IA"
                >
                  <FiZap className="w-3 h-3 fill-current" />
                  <span>Match {offer.evaluation_score.toFixed(1)}/5</span>
                </span>
              ) : offer.pipeline_stage === "evaluated" ? (
                <span className="px-2.5 py-0.5 bg-blue-500/15 text-blue-300 text-xs font-semibold rounded-lg border border-blue-500/30 flex items-center gap-1">
                  <FiZap className="w-3 h-3" />
                  <span>Évaluée</span>
                </span>
              ) : null}

              {offer.type_contrat && offer.type_contrat !== "Non spécifié" && (
                <span className="px-2 py-0.5 bg-slate-800 text-slate-300 text-[11px] font-medium rounded-md border border-slate-700/60">
                  {offer.type_contrat}
                </span>
              )}

              {offer.mode_travail && offer.mode_travail !== "Non spécifié" && (
                <span className="px-2 py-0.5 bg-purple-500/10 text-purple-300 text-[11px] font-medium rounded-md border border-purple-500/20">
                  {offer.mode_travail}
                </span>
              )}

              {offer.salaire && offer.salaire !== "Non spécifié" && (
                <span className="px-2 py-0.5 bg-emerald-500/10 text-emerald-300 text-[11px] font-medium rounded-md border border-emerald-500/20">
                  {offer.salaire}
                </span>
              )}

              {offer.is_active === false && (
                <span className="px-2 py-0.5 bg-rose-500/15 text-rose-300 text-[11px] font-medium rounded-md border border-rose-500/30">
                  Expirée
                </span>
              )}
            </div>

            {/* Description nettoyée */}
            {!cleanedDescription ? (
              <div className="mb-3 bg-slate-950/40 p-2.5 rounded-xl border border-dashed border-slate-800 flex items-center justify-between">
                <span className="text-slate-500 text-xs italic">Description non générée</span>
                <button
                  type="button"
                  onClick={() => handleRegenerateDescription(offer.id)}
                  disabled={regeneratingId === offer.id}
                  className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 font-medium disabled:opacity-50"
                >
                  <FiRefreshCw className={`w-3 h-3 ${regeneratingId === offer.id ? "animate-spin" : ""}`} />
                  <span>{regeneratingId === offer.id ? "Génération..." : "Régénérer"}</span>
                </button>
              </div>
            ) : (
              <div className="mb-3 bg-slate-950/40 p-3 rounded-xl border border-slate-800/80">
                <p
                  className={`text-slate-300 text-xs leading-relaxed whitespace-pre-line ${
                    !isExpanded ? "line-clamp-3" : ""
                  }`}
                >
                  {cleanedDescription}
                </p>
                {cleanedDescription.length > 150 && (
                  <button
                    type="button"
                    onClick={() => setIsExpanded(!isExpanded)}
                    className="mt-2 text-[11px] text-blue-400 hover:text-blue-300 font-semibold focus:outline-none flex items-center gap-1 transition-colors"
                  >
                    {isExpanded ? "Voir moins ▲" : "Voir plus ▼"}
                  </button>
                )}
              </div>
            )}

            {/* Compétences clés */}
            {offer.competences_cles && offer.competences_cles.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mb-3">
                {offer.competences_cles.slice(0, 3).map((comp, idx) => (
                  <span
                    key={idx}
                    className="px-2 py-0.5 bg-slate-800/80 text-slate-300 text-[11px] rounded border border-slate-700/50"
                  >
                    {comp}
                  </span>
                ))}
                {offer.competences_cles.length > 3 && (
                  <span className="text-[11px] text-slate-400 self-center">
                    +{offer.competences_cles.length - 3}
                  </span>
                )}
              </div>
            )}

            <div className="flex items-center gap-1.5 mb-4">
              <FiCalendar className="text-slate-400 flex-shrink-0 text-xs" />
              <span className="text-slate-400 text-xs">
                {formatDate(offer.date || "")}
              </span>
            </div>
          </div>

          {/* Action buttons (sans étoiles) */}
          <div className="flex items-center gap-2 pt-3 border-t border-slate-800">
            <Link
              href={`/offers/${offer.id}`}
              className="bg-slate-800/90 hover:bg-slate-700 text-slate-200 hover:text-white px-3 py-2 rounded-xl text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 border border-slate-700/80 hover:border-slate-600 shadow-sm"
              title="Consulter l'évaluation détaillée"
            >
              <FiEye className="w-3.5 h-3.5 text-blue-400" />
              <span>Détails</span>
            </Link>

            {offer.url && (
              <a
                href={offer.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-1 bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 hover:text-white px-3 py-2 rounded-xl text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 border border-blue-500/30"
              >
                <FiExternalLink className="w-3.5 h-3.5" />
                <span>Offre</span>
              </a>
            )}

            <button
              onClick={() => handleApplyToOffer(offer)}
              className="bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white px-3.5 py-2 rounded-xl text-xs font-semibold transition-all shadow-sm shadow-emerald-500/20 flex items-center justify-center gap-1.5"
              title="Postuler à cette offre"
            >
              <FiPlus className="w-3.5 h-3.5" />
              <span>Postuler</span>
            </button>
          </div>
        </div>
      </div>
    );
  };


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

  // Composant statistiques (inchangé)
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
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20">
              <FiSearch className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-white">Offres d'emploi</h1>
              <p className="text-xs text-slate-400 mt-0.5">
                Explorez les opportunités scrapées et mesurez votre adéquation
              </p>
            </div>
          </div>

          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all border shadow-sm ${
              showFilters || locationFilter || companyFilter
                ? "bg-blue-600 text-white border-blue-500 shadow-blue-500/20"
                : "bg-slate-800/90 text-slate-300 hover:text-white border-slate-700 hover:bg-slate-700"
            }`}
          >
            <FiFilter className="w-3.5 h-3.5" />
            <span>Filtres</span>
            {(locationFilter || companyFilter) && (
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            )}
          </button>
        </div>

        {/* Onglets */}
        <div className="flex space-x-2 mb-6">
          <button
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

        {/* Contenu conditionnel selon l'onglet */}
        {activeTab === "offers" && (
          <>
            {/* Barre de recherche et filtres */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 mb-6 shadow-md backdrop-blur-sm">
              {/* Recherche principale */}
              <div className="relative">
                <FiSearch className="absolute left-3.5 top-1/2 transform -translate-y-1/2 text-slate-400 w-4 h-4" />
                <input
                  type="text"
                  placeholder="Rechercher des offres (poste, compétences, mots-clés...)"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-10 pr-10 py-2.5 bg-slate-800/80 border border-slate-700/80 rounded-xl text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 text-sm transition-all"
                />
                {searchTerm && (
                  <button
                    onClick={() => setSearchTerm("")}
                    className="absolute right-3.5 top-1/2 transform -translate-y-1/2 text-slate-400 hover:text-white"
                  >
                    <FiX className="w-4 h-4" />
                  </button>
                )}
              </div>

              {/* Quick filter pills */}
              <div className="flex flex-wrap items-center gap-2 mt-3 pt-3 border-t border-slate-800/80">
                <button
                  type="button"
                  onClick={() => {
                    setOnlySaved(!onlySaved);
                    setCurrentPage(1);
                  }}
                  className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 border ${
                    onlySaved
                      ? "bg-amber-500/20 text-amber-300 border-amber-500/40 shadow-sm shadow-amber-500/10"
                      : "bg-slate-800/70 text-slate-400 hover:text-white border-slate-700/60 hover:bg-slate-800"
                  }`}
                >
                  <FiBookmark className={`w-3.5 h-3.5 ${onlySaved ? "fill-amber-400 text-amber-400" : ""}`} />
                  <span>Favoris uniquement</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setMinScoreFilter(minScoreFilter === 4.0 ? undefined : 4.0);
                    setCurrentPage(1);
                  }}
                  className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 border ${
                    minScoreFilter === 4.0
                      ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40 shadow-sm shadow-emerald-500/10"
                      : "bg-slate-800/70 text-slate-400 hover:text-white border-slate-700/60 hover:bg-slate-800"
                  }`}
                >
                  <FiZap className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Score IA ≥ 4.0</span>
                </button>
              </div>

              {/* Filtres détaillés */}
              {showFilters && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 mt-4 border-t border-slate-800">
                  <div>
                    <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                      Localisation
                    </label>
                    <input
                      type="text"
                      placeholder="Paris, Lyon, Télétravail..."
                      value={locationFilter}
                      onChange={(e) => setLocationFilter(e.target.value)}
                      className="w-full px-3.5 py-2 bg-slate-800/80 border border-slate-700/80 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 text-sm"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                      Entreprise
                    </label>
                    <input
                      type="text"
                      placeholder="Google, Alan, Doctolib..."
                      value={companyFilter}
                      onChange={(e) => setCompanyFilter(e.target.value)}
                      className="w-full px-3.5 py-2 bg-slate-800/80 border border-slate-700/80 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 text-sm"
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Statistiques & compteur */}
            <div className="flex items-center justify-between mb-5 px-1">
              <p className="text-xs font-medium text-slate-400">
                {loading
                  ? "Chargement des offres..."
                  : `${totalOffers} offres au total • ${offers.length} affichées`}
              </p>

              {(searchTerm || locationFilter || companyFilter || onlySaved || minScoreFilter !== undefined) && (
                <button
                  onClick={() => {
                    setSearchTerm("");
                    setLocationFilter("");
                    setCompanyFilter("");
                    setOnlySaved(false);
                    setMinScoreFilter(undefined);
                  }}
                  className="text-xs font-semibold text-blue-400 hover:text-blue-300 transition-colors"
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
                    <OfferCard
                      key={offer.id}
                      offer={offer}
                    />
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
