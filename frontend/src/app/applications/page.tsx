"use client";

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useNotification } from "@/contexts/NotificationContext";
import {
  Application,
  normalizeApiData,
  STATUS_ORDER,
  getStatusColor,
  calculateDays,
  type PipelineSummary,
} from "@/types/application";
import ApplicationDetails from "@/components/applications/ApplicationDetails";
import NewApplicationModal, {
  PrefilledData,
} from "@/components/dashboard/NewApplicationModal";
import {
  applicationApi,
  jobOffersApi,
  type Application as ApiApplication,
} from "@/lib/api";
import {
  FiBriefcase,
  FiAlertCircle,
  FiTrendingUp,
  FiAward,
  FiArrowRight,
  FiSearch,
  FiPlus,
  FiRefreshCw,
  FiMapPin,
  FiLink,
  FiGrid,
  FiList,
  FiClock,
  FiMail,
  FiStar,
  FiExternalLink,
  FiCheck,
} from "react-icons/fi";

// Sequence standard pour l'avancement en 1 clic
const QUICK_TRANSITIONS: Record<string, { nextStatus: string; label: string }> = {
  "En étude": { nextStatus: "Candidature envoyée", label: "Envoyer" },
  "Candidature envoyée": { nextStatus: "Première sélection", label: "Sélection" },
  "Première sélection": { nextStatus: "Entretien", label: "Entretien" },
  "Entretien": { nextStatus: "Test technique", label: "Test tech" },
  "Test technique": { nextStatus: "Offre reçue", label: "Offre" },
  "Négociation": { nextStatus: "Offre reçue", label: "Offre" },
  "Offre reçue": { nextStatus: "Offre acceptée", label: "Accepter" },
};

export default function ApplicationsPage() {
  const router = useRouter();
  const { addNotification } = useNotification();
  const prevDescriptions = useRef<Record<string, string | undefined>>({});
  const isInitialLoad = useRef(true);

  // Applications & Résumé Pipeline
  const [applications, setApplications] = useState<Application[]>([]);
  const [summary, setSummary] = useState<PipelineSummary | null>(null);
  const [scoredOffersCount, setScoredOffersCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Vue & Filtres
  const [viewMode, setViewMode] = useState<"kanban" | "table">("kanban");
  const [searchTerm, setSearchTerm] = useState("");
  const [filterAlertOnly, setFilterAlertOnly] = useState(false);

  // Modal Détails de Candidature
  const [selectedApplication, setSelectedApplication] = useState<Application | null>(null);
  const [originalApplication, setOriginalApplication] = useState<Application | null>(null);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState<boolean>(false);
  const [isAddingNote, setIsAddingNote] = useState<boolean>(false);
  const [isDeletingNote, setIsDeletingNote] = useState<boolean>(false);
  const [deletingNoteIndex, setDeletingNoteIndex] = useState<number | null>(null);

  // Modal Nouvelle Candidature
  const [isNewAppModalOpen, setIsNewAppModalOpen] = useState(false);
  const [prefilledData, setPrefilledData] = useState<PrefilledData | undefined>(undefined);

  // Chargement des données (applications + résumé)
  const fetchData = useCallback(
    async (showLoading = true) => {
      if (showLoading) setLoading(true);
      else setRefreshing(true);

      try {
        const [apiApps, summaryData, offersData] = await Promise.all([
          applicationApi.getAll(),
          applicationApi.getPipelineSummary().catch(() => null),
          jobOffersApi.getAll({ limit: 50 }).catch(() => []),
        ]);

        const apps = (apiApps || []).map((item) => normalizeApiData(item));

        // Notifications de description générée en arrière-plan
        if (!isInitialLoad.current) {
          apps.forEach((app) => {
            const oldDesc = prevDescriptions.current[app._id];
            if ((!oldDesc || oldDesc === "") && app.description) {
              addNotification(
                "info",
                `Description générée pour "${app.position}" chez "${app.company}"`
              );
            }
          });
        }
        apps.forEach((app) => {
          prevDescriptions.current[app._id] = app.description;
        });
        isInitialLoad.current = false;

        setApplications(apps);
        setSummary(summaryData);

        const highMatches = (offersData || []).filter(
          (o) => (o.evaluation_score && o.evaluation_score >= 3.5) || o.pipeline_stage === "evaluated"
        );
        setScoredOffersCount(highMatches.length);
        setError(null);
      } catch (err) {
        console.error("Erreur chargement applications:", err);
        setError("Erreur lors du chargement des candidatures");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [addNotification]
  );

  // Chargement initial
  useEffect(() => {
    fetchData(true);
  }, [fetchData]);

  // Polling silencieux toutes les 10s tant qu'il manque des descriptions
  useEffect(() => {
    if (isInitialLoad.current) return;
    if (!applications.some((app) => !app.description)) return;
    const intervalId = setInterval(() => {
      fetchData(false);
    }, 10_000);
    return () => clearInterval(intervalId);
  }, [applications, fetchData]);

  // Écoute de l'événement global pour ouvrir la modale
  useEffect(() => {
    const handleOpenModal = (event: CustomEvent<PrefilledData>) => {
      setPrefilledData(event.detail);
      setIsNewAppModalOpen(true);
    };
    window.addEventListener("open-application-modal", handleOpenModal as EventListener);
    return () => {
      window.removeEventListener("open-application-modal", handleOpenModal as EventListener);
    };
  }, []);

  // Handlers pour la sélection / ouverture de la fiche détails
  const handleCardClick = (application: Application): void => {
    setSelectedApplication(application);
    setOriginalApplication(JSON.parse(JSON.stringify(application)));
    setHasUnsavedChanges(false);
  };

  const handleBackClick = (): void => {
    if (hasUnsavedChanges) {
      if (
        window.confirm(
          "Vous avez des modifications non enregistrées. Êtes-vous sûr de vouloir quitter sans enregistrer ?"
        )
      ) {
        setSelectedApplication(null);
        setHasUnsavedChanges(false);
      }
    } else {
      setSelectedApplication(null);
    }
  };

  // Transition d'état rapide (1 clic)
  const handleTransitionStatus = async (
    e: React.MouseEvent,
    appId: string,
    newStatus: string
  ) => {
    e.stopPropagation();
    try {
      // Optimistic update
      setApplications((prev) =>
        prev.map((app) => (app._id === appId ? { ...app, status: newStatus } : app))
      );
      await applicationApi.update(appId, { status: newStatus });
      addNotification("success", `Statut mis à jour : ${newStatus}`);
      fetchData(false);
    } catch (err) {
      console.error("Erreur transition de statut:", err);
      addNotification("error", "Erreur lors de la mise à jour du statut");
      fetchData(false);
    }
  };

  // Gestion des modifications de formulaire dans le volet Détails
  const handleFieldChange = (field: string, value: string) => {
    if (!selectedApplication) return;
    if (field === "notes") {
      try {
        const notes = JSON.parse(value);
        setSelectedApplication({ ...selectedApplication, notes });
      } catch {
        return;
      }
    } else {
      setSelectedApplication({ ...selectedApplication, [field]: value });
    }
    setHasUnsavedChanges(true);
  };

  const handleAddNote = async (noteText: string) => {
    if (!selectedApplication || !noteText.trim()) return;
    try {
      setIsAddingNote(true);
      const updatedNotes = [...(selectedApplication.notes || []), noteText];
      setSelectedApplication({ ...selectedApplication, notes: updatedNotes });
      await applicationApi.update(selectedApplication._id, { notes: updatedNotes });
      await fetchData(false);
      addNotification("success", "Note ajoutée avec succès");
    } catch (error) {
      console.error("Erreur ajout note:", error);
      addNotification("error", "Erreur lors de l'ajout de la note");
    } finally {
      setIsAddingNote(false);
    }
  };

  const handleEditNote = async (noteIndex: number, noteText: string) => {
    if (!selectedApplication || !noteText.trim()) return;
    try {
      const updatedNotes = [...(selectedApplication.notes || [])];
      updatedNotes[noteIndex] = noteText;
      setSelectedApplication({ ...selectedApplication, notes: updatedNotes });
      await applicationApi.update(selectedApplication._id, { notes: updatedNotes });
      await fetchData(false);
      addNotification("success", "Note modifiée avec succès");
    } catch (error) {
      console.error("Erreur modification note:", error);
      addNotification("error", "Erreur lors de la modification de la note");
    }
  };

  const handleDeleteNote = async (noteIndex: number) => {
    if (!selectedApplication) return;
    try {
      setIsDeletingNote(true);
      setDeletingNoteIndex(noteIndex);
      const updatedNotes = [...(selectedApplication.notes || [])];
      updatedNotes.splice(noteIndex, 1);
      setSelectedApplication({ ...selectedApplication, notes: updatedNotes });
      await applicationApi.update(selectedApplication._id, { notes: updatedNotes });
      await fetchData(false);
      addNotification("success", "Note supprimée avec succès");
    } catch (error) {
      console.error("Erreur suppression note:", error);
      addNotification("error", "Erreur lors de la suppression de la note");
    } finally {
      setIsDeletingNote(false);
      setDeletingNoteIndex(null);
    }
  };

  const handleSaveChanges = async () => {
    if (!selectedApplication) return;
    try {
      await applicationApi.update(selectedApplication._id, selectedApplication);
      await fetchData(false);
      setOriginalApplication(JSON.parse(JSON.stringify(selectedApplication)));
      setHasUnsavedChanges(false);
      addNotification("success", "Candidature enregistrée avec succès");
    } catch (error) {
      console.error("Erreur mise à jour candidature:", error);
      addNotification("error", "Erreur lors de l'enregistrement de la candidature");
    }
  };

  const handleCancelChanges = () => {
    if (originalApplication) {
      setSelectedApplication(JSON.parse(JSON.stringify(originalApplication)));
      setHasUnsavedChanges(false);
      addNotification("info", "Modifications annulées");
    }
  };

  const handleDeleteApplication = async () => {
    if (!selectedApplication) return;
    if (
      !window.confirm(
        "Êtes-vous sûr de vouloir supprimer cette candidature ? Cette action est irréversible."
      )
    ) {
      return;
    }
    try {
      await applicationApi.delete(selectedApplication._id);
      setSelectedApplication(null);
      await fetchData(false);
      addNotification("success", "Candidature supprimée avec succès");
    } catch (error) {
      console.error("Erreur suppression candidature:", error);
      addNotification("error", "Erreur lors de la suppression de la candidature");
    }
  };

  const handleToggleArchive = async () => {
    if (!selectedApplication) return;
    try {
      const updatedApplication = {
        ...selectedApplication,
        archived: !selectedApplication.archived,
      };
      await applicationApi.update(selectedApplication._id, updatedApplication);
      setSelectedApplication(null);
      await fetchData(false);
      addNotification(
        "success",
        selectedApplication.archived
          ? "Candidature désarchivée avec succès"
          : "Candidature archivée avec succès"
      );
    } catch (error) {
      console.error("Erreur archivage:", error);
      addNotification("error", "Erreur lors de l'archivage de la candidature");
    }
  };

  // Filtrage des candidatures selon recherche et alertes
  const filteredApplications = useMemo(() => {
    return applications.filter((app) => {
      const matchesSearch =
        !searchTerm.trim() ||
        app.company.toLowerCase().includes(searchTerm.toLowerCase()) ||
        app.position.toLowerCase().includes(searchTerm.toLowerCase());

      const days = app.days_since_application ?? calculateDays(app.application_date);
      const isRelanceDue =
        app.follow_up_alert === "relance_due" ||
        (app.status === "Candidature envoyée" && days >= 7);
      const isRemerciementDue =
        app.follow_up_alert === "remerciement_due" ||
        (app.status === "Entretien" && days >= 1);
      const hasAlert = isRelanceDue || isRemerciementDue;

      const matchesAlert = !filterAlertOnly || hasAlert;
      return matchesSearch && matchesAlert;
    });
  }, [applications, searchTerm, filterAlertOnly]);

  // Groupement des colonnes du Kanban (hauteurs égales et statut "En étude" dédié)
  const columns = useMemo(() => {
    const getAppsFor = (statuses: string[]) =>
      filteredApplications.filter((a) => !a.archived && statuses.includes(a.status));

    return [
      {
        id: "etude",
        title: "En étude / À préparer",
        dotColor: "bg-amber-400",
        badgeBg: "bg-amber-500/20 text-amber-300 border-amber-500/30",
        apps: getAppsFor(["En étude"]),
      },
      {
        id: "applied",
        title: "Candidatures envoyées",
        dotColor: "bg-blue-500",
        badgeBg: "bg-blue-500/20 text-blue-300 border-blue-500/30",
        apps: getAppsFor(["Candidature envoyée"]),
      },
      {
        id: "screening",
        title: "1ère Sélection / RH",
        dotColor: "bg-cyan-400",
        badgeBg: "bg-cyan-500/20 text-cyan-300 border-cyan-500/30",
        apps: getAppsFor(["Première sélection"]),
      },
      {
        id: "interview",
        title: "Entretiens & Tests",
        dotColor: "bg-purple-400",
        badgeBg: "bg-purple-500/20 text-purple-300 border-purple-500/30",
        apps: getAppsFor(["Entretien", "Test technique"]),
      },
      {
        id: "offer",
        title: "Offres reçues",
        dotColor: "bg-emerald-400",
        badgeBg: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
        apps: getAppsFor(["Offre reçue", "Négociation", "Offre acceptée"]),
      },
      {
        id: "closed",
        title: "Clôturées",
        dotColor: "bg-rose-500",
        badgeBg: "bg-rose-500/20 text-rose-300 border-rose-500/30",
        apps: filteredApplications.filter(
          (a) => a.archived || a.status === "Refusée" || a.status === "Retirée"
        ),
      },
    ];
  }, [filteredApplications]);

  return (
    <div className="h-[calc(100dvh-64px)] flex flex-col overflow-hidden bg-blue-night text-white">
      {/* Barre supérieure : Titre, Recherche, Filtres, KPIs */}
      <div className="border-b border-gray-800 bg-blue-night-lighter/40 px-4 py-3 flex-shrink-0">
        <div className="max-w-[1700px] mx-auto">
          {/* Ligne 1 : Titre et Actions principales */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 mb-3">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white shadow-md">
                <FiBriefcase className="text-lg" />
              </div>
              <div>
                <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                  Suivi des Candidatures
                  <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/30">
                    {applications.filter((a) => !a.archived).length} actives
                  </span>
                </h1>
              </div>
            </div>

            {/* Actions : Recherche, Relances, Vue, Bouton Ajout */}
            <div className="flex flex-wrap items-center gap-2.5">
              {/* Recherche */}
              <div className="relative">
                <FiSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-xs" />
                <input
                  type="text"
                  placeholder="Filtrer entreprise ou poste..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-8 pr-3 py-1.5 bg-gray-900/80 border border-gray-700 rounded-lg text-xs text-white placeholder-gray-400 focus:outline-none focus:border-blue-500 w-48 sm:w-60 transition-colors"
                />
              </div>

              {/* Filtre Relances */}
              <button
                onClick={() => setFilterAlertOnly(!filterAlertOnly)}
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

              {/* Basculeur de vue Kanban / Tableau */}
              <div className="flex items-center bg-gray-900 border border-gray-700 rounded-lg p-0.5">
                <button
                  onClick={() => setViewMode("kanban")}
                  className={`px-2.5 py-1 rounded text-xs font-semibold flex items-center gap-1 transition-colors ${
                    viewMode === "kanban"
                      ? "bg-blue-600 text-white shadow-sm"
                      : "text-gray-400 hover:text-white"
                  }`}
                  title="Vue Kanban"
                >
                  <FiGrid className="text-xs" /> Kanban
                </button>
                <button
                  onClick={() => setViewMode("table")}
                  className={`px-2.5 py-1 rounded text-xs font-semibold flex items-center gap-1 transition-colors ${
                    viewMode === "table"
                      ? "bg-blue-600 text-white shadow-sm"
                      : "text-gray-400 hover:text-white"
                  }`}
                  title="Vue Tableau"
                >
                  <FiList className="text-xs" /> Tableau
                </button>
              </div>

              {/* Actualiser */}
              <button
                onClick={() => fetchData(false)}
                disabled={refreshing}
                className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors border border-gray-700"
                title="Actualiser les données"
              >
                <FiRefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
              </button>

              {/* Nouvelle Candidature */}
              <button
                onClick={() => {
                  setPrefilledData(undefined);
                  setIsNewAppModalOpen(true);
                }}
                className="px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-sm"
              >
                <FiPlus className="w-3.5 h-3.5" />
                <span>Nouvelle candidature</span>
              </button>
            </div>
          </div>

          {/* Ligne 2 : Mini-bandeau KPI Analytiques (Career-Ops Conversion) */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5 pt-2 border-t border-gray-800/80">
            <div className="bg-gray-900/60 px-3 py-1.5 rounded-lg border border-gray-800 flex items-center justify-between">
              <span className="text-[11px] text-gray-400">Actives</span>
              <span className="text-sm font-bold text-white">
                {summary ? summary.total_active : applications.filter((a) => !a.archived).length}
              </span>
            </div>

            <div className="bg-gray-900/60 px-3 py-1.5 rounded-lg border border-gray-800 flex items-center justify-between">
              <span className="text-[11px] text-gray-400 flex items-center gap-1">
                <FiTrendingUp className="text-blue-400 text-xs" /> Taux d'entretien
              </span>
              <span className="text-sm font-bold text-blue-400">
                {summary ? `${summary.interview_conversion_rate}%` : "0%"}
              </span>
            </div>

            <div className="bg-gray-900/60 px-3 py-1.5 rounded-lg border border-gray-800 flex items-center justify-between">
              <span className="text-[11px] text-gray-400 flex items-center gap-1">
                <FiAward className="text-emerald-400 text-xs" /> Taux d'offres
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

      {/* Corps Principal : Kanban pleine hauteur ou Tableau */}
      <div className="flex-1 min-h-0 flex flex-col p-4 overflow-hidden">
        {loading ? (
          <div className="flex-1 flex items-center justify-center py-24 text-gray-400 gap-3">
            <FiRefreshCw className="w-6 h-6 animate-spin text-blue-400" />
            <span className="text-sm font-medium">Chargement des candidatures...</span>
          </div>
        ) : error ? (
          <div className="flex-1 flex items-center justify-center py-24 text-rose-400 gap-2">
            <FiAlertCircle className="w-5 h-5" />
            <span className="text-sm">{error}</span>
          </div>
        ) : viewMode === "kanban" ? (
          /* ========================================================= */
          /* VUE KANBAN : COLONNES DE HAUTEUR ÉGALE STRICTE            */
          /* ========================================================= */
          <div className="flex-1 min-h-0 flex flex-row gap-4 overflow-x-auto overflow-y-hidden pb-2 custom-scrollbar">
            {columns.map((col) => (
              <div
                key={col.id}
                className="flex-1 min-w-[280px] max-w-[340px] flex flex-col h-full min-h-0 bg-gray-900/50 rounded-xl border border-gray-800/80 shadow-sm"
              >
                {/* En-tête de la colonne (toujours visible, ne défile jamais) */}
                <div className="p-3 border-b border-gray-800 flex items-center justify-between flex-shrink-0 bg-gray-900/60 rounded-t-xl">
                  <div className="flex items-center gap-2">
                    <span className={`w-2.5 h-2.5 rounded-full ${col.dotColor}`} />
                    <span className="text-xs font-bold text-gray-200">{col.title}</span>
                  </div>
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full font-semibold border ${col.badgeBg}`}
                  >
                    {col.apps.length}
                  </span>
                </div>

                {/* Cartes de candidature (défilement vertical interne exclusif) */}
                <div className="flex-1 min-h-0 overflow-y-auto p-2.5 space-y-2.5 custom-scrollbar">
                  {col.apps.length === 0 ? (
                    <div className="h-32 flex items-center justify-center text-xs text-gray-500 italic text-center px-4">
                      Aucune candidature dans cette étape
                    </div>
                  ) : (
                    col.apps.map((app) => {
                      const days =
                        app.days_since_application ?? calculateDays(app.application_date);
                      const isRelanceDue =
                        app.follow_up_alert === "relance_due" ||
                        (app.status === "Candidature envoyée" && days >= 7);
                      const isRemerciementDue =
                        app.follow_up_alert === "remerciement_due" ||
                        (app.status === "Entretien" && days >= 1);
                      const quickTransition = QUICK_TRANSITIONS[app.status];

                      return (
                        <div
                          key={app._id}
                          onClick={() => handleCardClick(app)}
                          className="bg-blue-night-lighter/90 hover:bg-blue-night-lighter border border-gray-700/80 hover:border-blue-500/60 rounded-xl p-3 shadow-sm hover:shadow-md transition-all cursor-pointer group"
                        >
                          {/* En-tête de la carte : Poste et Badge Délai */}
                          <div className="flex items-start justify-between gap-2 mb-1.5">
                            <h3 className="font-semibold text-xs text-white group-hover:text-blue-200 transition-colors line-clamp-2 leading-tight">
                              {app.position}
                            </h3>
                            <span className="flex-shrink-0 text-[10px] text-gray-400 bg-gray-800/80 px-1.5 py-0.5 rounded border border-gray-700 flex items-center gap-1">
                              <FiClock className="text-[9px]" />
                              {days}j
                            </span>
                          </div>

                          {/* Entreprise et Localisation */}
                          <div className="text-[11px] text-gray-300 font-medium truncate mb-1">
                            {app.company}
                          </div>

                          {app.location && (
                            <div className="text-[10px] text-gray-400 flex items-center gap-1 mb-2 truncate">
                              <FiMapPin className="text-[10px] shrink-0" />
                              <span>{app.location}</span>
                            </div>
                          )}

                          {/* Alertes de Cadence Automatisées */}
                          {isRelanceDue && (
                            <div className="mb-2 px-2 py-1 rounded text-[10px] font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/40 flex items-center gap-1.5">
                              <FiAlertCircle className="text-xs shrink-0 text-amber-400" />
                              <span>Relance J+7 due ({days}j)</span>
                            </div>
                          )}

                          {isRemerciementDue && (
                            <div className="mb-2 px-2 py-1 rounded text-[10px] font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 flex items-center gap-1.5">
                              <FiMail className="text-xs shrink-0 text-indigo-400" />
                              <span>Remerciement J+1 à faire</span>
                            </div>
                          )}

                          {/* Lien vers Offre d'origine si présente */}
                          {app.offer_id && (
                            <div className="mb-2 flex items-center gap-1 text-[10px] text-blue-300 bg-blue-900/30 px-2 py-0.5 rounded border border-blue-500/30 w-fit">
                              <FiLink className="text-[9px] shrink-0" />
                              <span className="truncate">Offre liée</span>
                            </div>
                          )}

                          {/* Actions Rapides en bas de carte */}
                          <div className="flex items-center gap-1.5 pt-2 border-t border-gray-800/80 mt-1">
                            {quickTransition && (
                              <button
                                onClick={(e) =>
                                  handleTransitionStatus(e, app._id, quickTransition.nextStatus)
                                }
                                className="flex-1 py-1 px-2 rounded bg-blue-600 hover:bg-blue-500 text-white text-[11px] font-medium flex items-center justify-center gap-1 transition-colors"
                                title={`Passer à l'étape : ${quickTransition.nextStatus}`}
                              >
                                <span>{quickTransition.label}</span>
                                <FiArrowRight className="text-[10px]" />
                              </button>
                            )}

                            {app.status !== "Refusée" && app.status !== "Retirée" && (
                              <button
                                onClick={(e) => handleTransitionStatus(e, app._id, "Refusée")}
                                className="py-1 px-2 rounded bg-rose-950/40 hover:bg-rose-900/60 text-rose-300 text-[11px] font-medium border border-rose-800/40 transition-colors"
                                title="Déclarer la candidature refusée"
                              >
                                Refus
                              </button>
                            )}

                            {(app.status === "Refusée" || app.status === "Retirée") && (
                              <button
                                onClick={(e) =>
                                  handleTransitionStatus(e, app._id, "Candidature envoyée")
                                }
                                className="flex-1 py-1 px-2 rounded bg-gray-800 hover:bg-gray-700 text-blue-300 text-[11px] font-medium border border-gray-700 transition-colors"
                                title="Réactiver la candidature"
                              >
                                Réactiver
                              </button>
                            )}
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          /* ========================================================= */
          /* VUE TABLEAU : LISTE TABULAIRE COMPLÈTE & FILTRABLE        */
          /* ========================================================= */
          <div className="flex-1 min-h-0 bg-gray-900/50 rounded-xl border border-gray-800 overflow-hidden flex flex-col">
            <div className="overflow-x-auto flex-1 custom-scrollbar">
              <table className="w-full text-left text-xs">
                <thead className="bg-gray-900/80 text-gray-400 font-semibold border-b border-gray-800 sticky top-0">
                  <tr>
                    <th className="py-3 px-4">Poste & Entreprise</th>
                    <th className="py-3 px-4">Localisation</th>
                    <th className="py-3 px-4">Date de dépôt</th>
                    <th className="py-3 px-4">Statut</th>
                    <th className="py-3 px-4">Alertes / Suivi</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {filteredApplications.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-12 text-center text-gray-500 italic">
                        Aucune candidature trouvée.
                      </td>
                    </tr>
                  ) : (
                    filteredApplications.map((app) => {
                      const days =
                        app.days_since_application ?? calculateDays(app.application_date);
                      const isRelanceDue =
                        app.follow_up_alert === "relance_due" ||
                        (app.status === "Candidature envoyée" && days >= 7);
                      const isRemerciementDue =
                        app.follow_up_alert === "remerciement_due" ||
                        (app.status === "Entretien" && days >= 1);

                      return (
                        <tr
                          key={app._id}
                          onClick={() => handleCardClick(app)}
                          className="hover:bg-gray-800/40 cursor-pointer transition-colors"
                        >
                          <td className="py-3 px-4">
                            <div className="font-semibold text-white">{app.position}</div>
                            <div className="text-gray-400 text-[11px]">{app.company}</div>
                          </td>
                          <td className="py-3 px-4 text-gray-300">{app.location || "—"}</td>
                          <td className="py-3 px-4 text-gray-300">
                            <div>{app.application_date.substring(0, 10)}</div>
                            <div className="text-[10px] text-gray-500">il y a {days} jours</div>
                          </td>
                          <td className="py-3 px-4">
                            <span
                              className={`px-2.5 py-1 rounded-full text-[11px] font-semibold text-white ${getStatusColor(
                                app.status
                              )}`}
                            >
                              {app.status}
                            </span>
                          </td>
                          <td className="py-3 px-4">
                            {isRelanceDue && (
                              <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                                ⚠️ Relance J+7 due
                              </span>
                            )}
                            {isRemerciementDue && (
                              <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                                💌 Remerciement J+1
                              </span>
                            )}
                            {!isRelanceDue && !isRemerciementDue && (
                              <span className="text-gray-500 text-[11px]">—</span>
                            )}
                          </td>
                          <td className="py-3 px-4 text-right">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleCardClick(app);
                              }}
                              className="px-2.5 py-1 rounded bg-gray-800 hover:bg-gray-700 text-blue-400 hover:text-blue-300 text-xs font-medium border border-gray-700 transition-colors"
                            >
                              Voir détails
                            </button>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Modale Fiche Détails Complète (visualisation, modification libre du statut via liste déroulante) */}
      <ApplicationDetails
        application={selectedApplication}
        originalApplication={originalApplication}
        onClose={handleBackClick}
        onChange={handleFieldChange}
        onSave={handleSaveChanges}
        onCancel={handleCancelChanges}
        onDelete={handleDeleteApplication}
        onArchive={handleToggleArchive}
        onAddNote={handleAddNote}
        onEditNote={handleEditNote}
        onDeleteNote={handleDeleteNote}
        hasUnsavedChanges={hasUnsavedChanges}
        isAddingNote={isAddingNote}
        isDeletingNote={isDeletingNote}
        deletingNoteIndex={deletingNoteIndex}
      />

      {/* Modale Nouvelle Candidature */}
      <NewApplicationModal
        isOpen={isNewAppModalOpen}
        onClose={() => {
          setIsNewAppModalOpen(false);
          setPrefilledData(undefined);
        }}
        onSuccess={() => {
          fetchData(false);
          addNotification("success", "Candidature ajoutée avec succès");
        }}
        prefilledData={prefilledData}
      />
    </div>
  );
}
