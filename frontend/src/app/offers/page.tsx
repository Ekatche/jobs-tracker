"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import {
  jobOffersApi,
  coverLetterApi,
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
  FiClock,
  FiStar,
  FiLayers,
  FiCheckCircle,
  FiTarget,
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

function getRecentBadgeInfo(createdAtStr?: string) {
  if (!createdAtStr) return null;
  const createdDate = new Date(createdAtStr);
  if (isNaN(createdDate.getTime())) return null;

  const now = new Date();
  const diffMs = now.getTime() - createdDate.getTime();
  const diffHours = diffMs / (1000 * 60 * 60);

  if (diffHours <= 24) {
    return { label: "Nouveau (< 24h)", isFresh: true };
  } else if (diffHours <= 48) {
    return { label: "Nouveau (< 48h)", isFresh: false };
  } else if (diffHours <= 7 * 24) {
    return { label: "Récent (< 7j)", isFresh: false };
  }
  return null;
}

function formatAddedDate(createdAtStr?: string): string | null {
  if (!createdAtStr) return null;
  try {
    const d = new Date(createdAtStr);
    if (isNaN(d.getTime())) return null;
    const now = new Date();
    const diffHours = (now.getTime() - d.getTime()) / (1000 * 60 * 60);
    if (diffHours < 1) {
      return "Ajoutée à l'instant";
    }
    if (diffHours < 24) {
      return `Ajoutée il y a ${Math.max(1, Math.round(diffHours))}h`;
    }
    if (diffHours < 48) {
      return "Ajoutée hier";
    }
    return `Ajoutée le ${d.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit" })}`;
  } catch {
    return null;
  }
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
  const [contractTypeFilter, setContractTypeFilter] = useState("");
  const [workModeFilter, setWorkModeFilter] = useState("");
  const [daysRecentFilter, setDaysRecentFilter] = useState<number | undefined>(undefined);
  const [onlySaved, setOnlySaved] = useState(false);
  const [interactionStatus, setInteractionStatus] = useState<"saved" | "applied" | "hidden" | undefined>(undefined);
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

  // Filtres normalisés et mémorisés
  const currentFilters = useMemo((): JobOfferFilter => {
    const f: JobOfferFilter = {};
    if (searchTerm) f.keywords = searchTerm;
    if (locationFilter) f.location = locationFilter;
    if (companyFilter) f.company = companyFilter;
    if (contractTypeFilter) f.contract_type = contractTypeFilter;
    if (workModeFilter) f.work_mode = workModeFilter;
    if (daysRecentFilter !== undefined) f.days_recent = daysRecentFilter;
    if (onlySaved) f.only_saved = true;
    if (interactionStatus) f.interaction_status = interactionStatus;
    if (minScoreFilter !== undefined) f.min_score = minScoreFilter;
    return f;
  }, [
    searchTerm,
    locationFilter,
    companyFilter,
    contractTypeFilter,
    workModeFilter,
    daysRecentFilter,
    onlySaved,
    interactionStatus,
    minScoreFilter,
  ]);

  // Fonction pour charger le nombre total d'offres
  const fetchTotalCount = useCallback(async () => {
    try {
      const countData = await jobOffersApi.getCount(currentFilters);
      setTotalOffers(countData.total);
    } catch (err) {
      console.error("Erreur lors du comptage des offres:", err);
      setTotalOffers(0);
    }
  }, [currentFilters]);

  // Fonction pour charger les offres avec pagination
  const fetchOffers = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const filters: JobOfferFilter = {
        ...currentFilters,
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
  }, [currentFilters, currentPage]);

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

  const [profileRoles, setProfileRoles] = useState<string[]>([]);
  const [profileLocations, setProfileLocations] = useState<string[]>([]);
  const [isProfileFilterActive, setIsProfileFilterActive] = useState(false);

  // Appliquer automatiquement les critères enregistrés dans le profil du candidat.
  // Priorise les rôles cibles explicites (préférences) ; à défaut, se rabat sur les
  // suggestions canonicalisées (headline + expériences passées par normalize_role),
  // et combine tous les rôles en OR (`|`) pour maximiser la couverture de recherche.
  const handleApplyProfileCriteria = useCallback(async () => {
    try {
      const [profile, suggested] = await Promise.all([
        coverLetterApi.getCandidateProfile(),
        coverLetterApi.getSuggestedRoles().catch(() => ({ roles: [] })),
      ]);
      if (!profile) return;

      const prefs = profile.preferences || {};
      const targetRoles = prefs.target_roles || [];
      const allRoles = targetRoles.length > 0 ? targetRoles : suggested.roles || [];
      const locs = prefs.locations || [];

      setProfileRoles(allRoles);
      setProfileLocations(locs);
      setIsProfileFilterActive(true);

      setSearchTerm(allRoles.length > 0 ? allRoles.join("|") : "");
      setLocationFilter(locs.length > 0 ? locs.join("|") : "");

      // Réinitialiser les filtres annexes trop restrictifs
      setContractTypeFilter("");
      setCompanyFilter("");
      setWorkModeFilter("");
      setDaysRecentFilter(undefined);
      setMinScoreFilter(undefined);
      setOnlySaved(false);
      setInteractionStatus(undefined);
    } catch (err) {
      console.error("Erreur lors de la récupération des critères du profil:", err);
    }
  }, []);

  // Applique automatiquement le filtrage "selon mon profil" dès le premier
  // chargement de la page, sans exiger de clic — l'utilisateur voit d'emblée
  // les offres correspondant à son profil.
  useEffect(() => {
    handleApplyProfileCriteria();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Charger le total au montage et quand les filtres changent
  useEffect(() => {
    if (activeTab === "offers") {
      fetchTotalCount();
    }
  }, [fetchTotalCount, activeTab]);

  // Charger les offres au montage, quand les filtres OU currentPage changent
  useEffect(() => {
    if (activeTab === "offers") {
      fetchOffers();
    } else if (activeTab === "stats") {
      fetchStats();
    }
  }, [fetchOffers, fetchStats, activeTab]);

  // Reset pagination sur modification des filtres
  useEffect(() => {
    setCurrentPage(1);
  }, [
    searchTerm,
    locationFilter,
    companyFilter,
    contractTypeFilter,
    workModeFilter,
    daysRecentFilter,
    onlySaved,
    interactionStatus,
    minScoreFilter,
  ]);

  // Clamping automatique si currentPage dépasse totalPages (ex: filtre restreignant les résultats)
  useEffect(() => {
    const totalPages = Math.ceil(totalOffers / ITEMS_PER_PAGE);
    if (totalPages > 0 && currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [totalOffers, currentPage]);

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
    const recentBadge = getRecentBadgeInfo(offer.created_at);
    const addedDateText = formatAddedDate(offer.created_at);

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

            {/* Badges: Nouveau (<24h / <48h), Match Score, Contrat, Mode de travail, Salaire */}
            <div className="flex flex-wrap gap-1.5 mb-3 items-center">
              {recentBadge && (
                <span
                  className={`px-2 py-0.5 text-xs font-bold rounded-lg border flex items-center gap-1 shadow-sm ${
                    recentBadge.isFresh
                      ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40 shadow-emerald-500/10"
                      : "bg-cyan-500/20 text-cyan-300 border-cyan-500/40 shadow-cyan-500/10"
                  }`}
                  title={`Offre ajoutée en base récemment (${recentBadge.label})`}
                >
                  <FiZap className="w-3 h-3 fill-current text-emerald-400" />
                  <span>{recentBadge.label}</span>
                </span>
              )}

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

            {/* Dates: Ajout en base + Date publication */}
            <div className="flex flex-col gap-1 mb-4 text-xs text-slate-400">
              {addedDateText && (
                <div className="flex items-center gap-1.5 text-emerald-400 font-medium">
                  <FiClock className="w-3.5 h-3.5 shrink-0 text-emerald-400" />
                  <span>{addedDateText}</span>
                </div>
              )}
              <div className="flex items-center gap-1.5 text-slate-400">
                <FiCalendar className="w-3.5 h-3.5 shrink-0" />
                <span>Publication : {formatDate(offer.date || "")}</span>
              </div>
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

  // Composant pagination enrichi et déterministe
  const Pagination = () => {
    const totalPages = Math.ceil(totalOffers / ITEMS_PER_PAGE);

    if (totalPages <= 1) return null;

    const handlePageClick = (page: number) => {
      setCurrentPage(page);
      window.scrollTo({ top: 0, behavior: "smooth" });
    };

    // Générer les numéros de page avec ellipses
    const getPageNumbers = () => {
      const delta = 1;
      const range: number[] = [];
      for (
        let i = Math.max(2, currentPage - delta);
        i <= Math.min(totalPages - 1, currentPage + delta);
        i++
      ) {
        range.push(i);
      }

      const pages: (number | string)[] = [1];
      if (currentPage - delta > 2) {
        pages.push("...");
      }
      pages.push(...range);
      if (currentPage + delta < totalPages - 1) {
        pages.push("...");
      }
      if (totalPages > 1 && !pages.includes(totalPages)) {
        pages.push(totalPages);
      }
      return pages;
    };

    return (
      <div className="flex flex-wrap justify-center items-center gap-1.5 mt-8 pb-10">
        <button
          onClick={() => handlePageClick(Math.max(1, currentPage - 1))}
          disabled={currentPage === 1}
          className="px-3.5 py-2 rounded-xl bg-slate-800/80 border border-slate-700/70 text-slate-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-700 hover:text-white transition-all text-xs font-semibold shadow-sm"
        >
          Précédent
        </button>

        {getPageNumbers().map((p, idx) =>
          typeof p === "string" ? (
            <span key={idx} className="px-2 py-1 text-slate-500 text-xs select-none">
              •••
            </span>
          ) : (
            <button
              key={idx}
              onClick={() => handlePageClick(p)}
              className={`min-w-[34px] h-[34px] px-2 rounded-xl text-xs font-semibold transition-all border shadow-sm ${
                currentPage === p
                  ? "bg-blue-600 text-white border-blue-500 shadow-blue-500/20"
                  : "bg-slate-800/80 text-slate-300 border-slate-700/60 hover:bg-slate-700 hover:text-white"
              }`}
            >
              {p}
            </button>
          )
        )}

        <button
          onClick={() => handlePageClick(Math.min(totalPages, currentPage + 1))}
          disabled={currentPage === totalPages}
          className="px-3.5 py-2 rounded-xl bg-slate-800/80 border border-slate-700/70 text-slate-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-700 hover:text-white transition-all text-xs font-semibold shadow-sm"
        >
          Suivant
        </button>

        <span className="ml-2 text-xs text-slate-400">
          Page {currentPage} sur {totalPages}
        </span>
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
        {/* Filtres & Barre d'action */}
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

              {/* Pilules de filtres rapides */}
              <div className="flex flex-wrap items-center gap-2 mt-3 pt-3 border-t border-slate-800/80">
                {/* Toutes */}
                <button
                  type="button"
                  onClick={() => {
                    setOnlySaved(false);
                    setInteractionStatus(undefined);
                    setDaysRecentFilter(undefined);
                    setMinScoreFilter(undefined);
                  }}
                  className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 border ${
                    !onlySaved && !interactionStatus && !daysRecentFilter && minScoreFilter === undefined
                      ? "bg-blue-600 text-white border-blue-500 shadow-sm shadow-blue-500/20"
                      : "bg-slate-800/70 text-slate-400 hover:text-white border-slate-700/60 hover:bg-slate-800"
                  }`}
                >
                  <FiLayers className="w-3.5 h-3.5" />
                  <span>Toutes</span>
                </button>

                {/* Mon profil */}
                <button
                  type="button"
                  onClick={handleApplyProfileCriteria}
                  className="px-3 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 border bg-indigo-600/20 text-indigo-300 hover:text-white border-indigo-500/40 hover:bg-indigo-600/30 shadow-sm"
                  title="Appliquer automatiquement mes critères de profil"
                >
                  <FiTarget className="w-3.5 h-3.5 text-indigo-400" />
                  <span>🎯 Selon mon profil</span>
                </button>

                {/* Favoris */}
                <button
                  type="button"
                  onClick={() => {
                    setOnlySaved(!onlySaved);
                    setInteractionStatus(undefined);
                  }}
                  className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 border ${
                    onlySaved
                      ? "bg-amber-500/20 text-amber-300 border-amber-500/40 shadow-sm shadow-amber-500/10"
                      : "bg-slate-800/70 text-slate-400 hover:text-white border-slate-700/60 hover:bg-slate-800"
                  }`}
                >
                  <FiBookmark className={`w-3.5 h-3.5 ${onlySaved ? "fill-amber-400 text-amber-400" : ""}`} />
                  <span>⭐ Favoris</span>
                </button>

                {/* Nouvelles (< 48h) */}
                <button
                  type="button"
                  onClick={() => {
                    setDaysRecentFilter(daysRecentFilter === 2 ? undefined : 2);
                  }}
                  className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 border ${
                    daysRecentFilter === 2
                      ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40 shadow-sm shadow-emerald-500/10"
                      : "bg-slate-800/70 text-slate-400 hover:text-white border-slate-700/60 hover:bg-slate-800"
                  }`}
                  title="Offres ajoutées dans votre base au cours des dernières 48 heures"
                >
                  <FiZap className="w-3.5 h-3.5 text-emerald-400" />
                  <span>✨ Nouvelles (&lt; 48h)</span>
                </button>

                {/* Score IA >= 4.0 */}
                <button
                  type="button"
                  onClick={() => {
                    setMinScoreFilter(minScoreFilter === 4.0 ? undefined : 4.0);
                  }}
                  className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 border ${
                    minScoreFilter === 4.0
                      ? "bg-indigo-500/20 text-indigo-300 border-indigo-500/40 shadow-sm shadow-indigo-500/10"
                      : "bg-slate-800/70 text-slate-400 hover:text-white border-slate-700/60 hover:bg-slate-800"
                  }`}
                >
                  <FiStar className="w-3.5 h-3.5 text-indigo-400" />
                  <span>Match IA ≥ 4.0</span>
                </button>

                {/* Postulées */}
                <button
                  type="button"
                  onClick={() => {
                    setInteractionStatus(interactionStatus === "applied" ? undefined : "applied");
                    setOnlySaved(false);
                  }}
                  className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 border ${
                    interactionStatus === "applied"
                      ? "bg-teal-500/20 text-teal-300 border-teal-500/40 shadow-sm shadow-teal-500/10"
                      : "bg-slate-800/70 text-slate-400 hover:text-white border-slate-700/60 hover:bg-slate-800"
                  }`}
                >
                  <FiCheckCircle className="w-3.5 h-3.5 text-teal-400" />
                  <span>Postulées</span>
                </button>
              </div>

              {/* Rôles et critères issus du profil candidat */}
              {profileRoles.length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5 mt-3 pt-3 border-t border-slate-800/80">
                  <span className="text-[11px] text-slate-400 flex items-center gap-1 font-medium mr-1">
                    <FiTarget className="w-3 h-3 text-indigo-400" /> Postes cibles de votre profil :
                  </span>
                  {profileRoles.map((role, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => setSearchTerm(role)}
                      className={`px-2.5 py-1 rounded-lg text-xs transition-all border ${
                        searchTerm.toLowerCase() === role.toLowerCase()
                          ? "bg-indigo-600 text-white border-indigo-500 font-semibold shadow-sm shadow-indigo-500/30"
                          : "bg-slate-800/80 text-slate-300 hover:text-white hover:bg-slate-700 border-slate-700/60"
                      }`}
                    >
                      {role}
                    </button>
                  ))}
                  {profileLocations.length > 0 && (
                    <div className="flex items-center gap-1 ml-2">
                      <span className="text-[11px] text-slate-500">|</span>
                      {profileLocations.map((loc, idx) => (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => setLocationFilter(locationFilter.toLowerCase() === loc.toLowerCase() ? "" : loc)}
                          className={`px-2 py-0.5 rounded-md text-[11px] transition-all border flex items-center gap-1 ${
                            locationFilter.toLowerCase() === loc.toLowerCase()
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

              {/* Filtres détaillés */}
              {showFilters && (
                <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-3 pt-4 mt-4 border-t border-slate-800 text-xs">
                  <div>
                    <label className="block font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
                      Localisation
                    </label>
                    <input
                      type="text"
                      placeholder="Paris, Lyon, Distanciel..."
                      value={locationFilter}
                      onChange={(e) => setLocationFilter(e.target.value)}
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
                      value={companyFilter}
                      onChange={(e) => setCompanyFilter(e.target.value)}
                      className="w-full px-3 py-2 bg-slate-800/80 border border-slate-700/80 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                    />
                  </div>

                  <div>
                    <label className="block font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
                      Contrat
                    </label>
                    <select
                      value={contractTypeFilter}
                      onChange={(e) => setContractTypeFilter(e.target.value)}
                      className="w-full px-3 py-2 bg-slate-800/80 border border-slate-700/80 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                    >
                      <option value="">Tous les contrats</option>
                      <option value="CDI">CDI</option>
                      <option value="CDD">CDD</option>
                      <option value="Freelance">Freelance</option>
                      <option value="Stage">Stage</option>
                      <option value="Alternance">Alternance</option>
                    </select>
                  </div>

                  <div>
                    <label className="block font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
                      Mode de travail
                    </label>
                    <select
                      value={workModeFilter}
                      onChange={(e) => setWorkModeFilter(e.target.value)}
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
                      value={daysRecentFilter ?? ""}
                      onChange={(e) =>
                        setDaysRecentFilter(e.target.value ? Number(e.target.value) : undefined)
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
                </div>
              )}
            </div>

            {/* Statistiques & compteur */}
            <div className="flex items-center justify-between mb-5 px-1">
              <p className="text-xs font-medium text-slate-400">
                {loading
                  ? "Chargement des offres..."
                  : `${totalOffers.toLocaleString()} offre${totalOffers > 1 ? "s" : ""} au total • ${offers.length} affichée${offers.length > 1 ? "s" : ""}`}
              </p>

              {(searchTerm ||
                locationFilter ||
                companyFilter ||
                contractTypeFilter ||
                workModeFilter ||
                daysRecentFilter !== undefined ||
                onlySaved ||
                interactionStatus ||
                minScoreFilter !== undefined) && (
                <button
                  onClick={() => {
                    setSearchTerm("");
                    setLocationFilter("");
                    setCompanyFilter("");
                    setContractTypeFilter("");
                    setWorkModeFilter("");
                    setDaysRecentFilter(undefined);
                    setOnlySaved(false);
                    setInteractionStatus(undefined);
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
