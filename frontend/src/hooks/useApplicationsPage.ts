"use client";

import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useNotification } from "@/contexts/NotificationContext";
import {
  Application,
  normalizeApiData,
  type PipelineSummary,
} from "@/types/application";
import {
  type KanbanColumnData,
  filterBoardApplications,
  buildKanbanColumns,
} from "@/lib/applicationsBoard";
import { useApplicationNotes } from "@/hooks/useApplicationNotes";
import { PrefilledData } from "@/components/dashboard/NewApplicationModal";
import { applicationApi, jobOffersApi } from "@/lib/api";

export type { KanbanColumnData };

/**
 * Manages applications board state, background polling, details drawer mutations, and filtering.
 */
export function useApplicationsPage() {
  const { addNotification } = useNotification();
  const prevDescriptions = useRef<Record<string, string | undefined>>({});
  const isInitialLoad = useRef(true);

  const [applications, setApplications] = useState<Application[]>([]);
  const [summary, setSummary] = useState<PipelineSummary | null>(null);
  const [scoredOffersCount, setScoredOffersCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const [viewMode, setViewMode] = useState<"kanban" | "table">("kanban");
  const [searchTerm, setSearchTerm] = useState("");
  const [filterAlertOnly, setFilterAlertOnly] = useState(false);

  const [selectedApplication, setSelectedApplication] = useState<Application | null>(null);
  const [originalApplication, setOriginalApplication] = useState<Application | null>(null);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState<boolean>(false);

  const [isNewAppModalOpen, setIsNewAppModalOpen] = useState(false);
  const [isCalibrationOpen, setIsCalibrationOpen] = useState(false);
  const [prefilledData, setPrefilledData] = useState<PrefilledData | undefined>(undefined);

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

  useEffect(() => {
    fetchData(true);
  }, [fetchData]);

  // Silent polling every 10s while some applications lack descriptions
  useEffect(() => {
    if (isInitialLoad.current) return;
    if (!applications.some((app) => !app.description)) return;
    const intervalId = setInterval(() => {
      fetchData(false);
    }, 10_000);
    return () => clearInterval(intervalId);
  }, [applications, fetchData]);

  useEffect(() => {
    const handleApplicationCreated = () => fetchData(false);
    window.addEventListener("application-created", handleApplicationCreated);
    return () => window.removeEventListener("application-created", handleApplicationCreated);
  }, [fetchData]);

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

  const handleTransitionStatus = async (
    e: React.MouseEvent,
    appId: string,
    newStatus: string
  ) => {
    e.stopPropagation();
    try {
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

  const {
    isAddingNote,
    isDeletingNote,
    deletingNoteIndex,
    handleAddNote,
    handleEditNote,
    handleDeleteNote,
  } = useApplicationNotes({
    selectedApplication,
    setSelectedApplication,
    refreshBoard: () => fetchData(false),
    addNotification,
  });

  const handleSaveChanges = async () => {
    if (!selectedApplication) return;
    try {
      await applicationApi.update(selectedApplication._id, selectedApplication);
      await fetchData(false);
      setOriginalApplication(JSON.parse(JSON.stringify(selectedApplication)));
      setHasUnsavedChanges(false);
      addNotification("success", "Candidature enregistrée avec succès");
    } catch (err) {
      console.error("Erreur mise à jour candidature:", err);
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
    } catch (err) {
      console.error("Erreur suppression candidature:", err);
      addNotification("error", "Erreur lors de la suppression de la candidature");
    }
  };

  const handleToggleArchive = async () => {
    if (!selectedApplication) return;
    try {
      await applicationApi.update(selectedApplication._id, {
        ...selectedApplication,
        archived: !selectedApplication.archived,
      });
      setSelectedApplication(null);
      await fetchData(false);
      addNotification(
        "success",
        selectedApplication.archived
          ? "Candidature désarchivée avec succès"
          : "Candidature archivée avec succès"
      );
    } catch (err) {
      console.error("Erreur archivage:", err);
      addNotification("error", "Erreur lors de l'archivage de la candidature");
    }
  };

  const filteredApplications = useMemo(
    () => filterBoardApplications(applications, searchTerm, filterAlertOnly),
    [applications, searchTerm, filterAlertOnly]
  );

  const columns: KanbanColumnData[] = useMemo(
    () => buildKanbanColumns(filteredApplications),
    [filteredApplications]
  );

  return {
    applications, summary, scoredOffersCount, loading, refreshing, error, viewMode, setViewMode,
    searchTerm, setSearchTerm, filterAlertOnly, setFilterAlertOnly, selectedApplication,
    originalApplication, hasUnsavedChanges, isAddingNote, isDeletingNote, deletingNoteIndex,
    isNewAppModalOpen, setIsNewAppModalOpen, isCalibrationOpen, setIsCalibrationOpen,
    prefilledData, setPrefilledData, filteredApplications, columns, fetchData, handleCardClick,
    handleBackClick, handleTransitionStatus, handleFieldChange, handleAddNote, handleEditNote,
    handleDeleteNote, handleSaveChanges, handleCancelChanges, handleDeleteApplication,
    handleToggleArchive, addNotification,
  };
}
