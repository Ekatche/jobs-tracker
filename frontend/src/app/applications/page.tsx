"use client";

import { useState, useEffect, useRef } from "react";
import { useNotification } from "@/contexts/NotificationContext";
import { useRouter } from "next/navigation";
import { Application, normalizeApiData } from "@/types/application";
import KanbanBoard from "@/components/applications/KanbanBoard";
import ApplicationDetails from "@/components/applications/ApplicationDetails";
import { applicationApi, Application as ApiApplication } from "@/lib/api";

export default function ApplicationsPage() {
  const router = useRouter();
  const { addNotification } = useNotification();
  const prevDescriptions = useRef<Record<string, string | undefined>>({});
  const isInitialLoad = useRef(true);

  const [applications, setApplications] = useState<Application[]>([]);
  const [selectedApplication, setSelectedApplication] =
    useState<Application | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isAddingNote, setIsAddingNote] = useState<boolean>(false);
  const [isDeletingNote, setIsDeletingNote] = useState<boolean>(false);
  const [deletingNoteIndex, setDeletingNoteIndex] = useState<number | null>(
    null,
  );
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState<boolean>(false);
  const [originalApplication, setOriginalApplication] =
    useState<Application | null>(null);

  // on ajoute un flag pour controler le spinner et gérer notifications
  const fetchData = async (showLoading = true) => {
    if (showLoading) setLoading(true);
    try {
      const apiData: ApiApplication[] = await applicationApi.getAll();
      const apps = apiData.map((item) => normalizeApiData(item));

      // Notifications quand la description apparaît
      if (!isInitialLoad.current) {
        apps.forEach((app) => {
          const oldDesc = prevDescriptions.current[app._id];
          if ((!oldDesc || oldDesc === "") && app.description) {
            addNotification(
              "info",
              `Description générée pour "${app.position}" chez "${app.company}"`,
            );
          }
        });
      }
      apps.forEach((app) => {
        prevDescriptions.current[app._id] = app.description;
      });
      isInitialLoad.current = false;

      setApplications(apps);
      setError(null);
    } catch (err) {
      console.error(err);
      setError("Erreur lors du chargement des candidatures");
    } finally {
      if (showLoading) setLoading(false);
    }
  };

  // chargement initial
  useEffect(() => {
    fetchData().catch(console.error);
  }, []);

  // polling SILENCIEUX toutes les 10s tant qu’il manque des descriptions
  useEffect(() => {
    if (isInitialLoad.current) return;
    if (!applications.some((app) => !app.description)) return;
    const intervalId = setInterval(() => {
      fetchData(false); // pas de spinner
    }, 10_000);
    return () => clearInterval(intervalId);
  }, [applications]);

  // polling dédié pour la description en détail
  useEffect(() => {
    let detailInterval: NodeJS.Timeout;
    if (selectedApplication && !selectedApplication.description) {
      detailInterval = setInterval(async () => {
        const updated = await applicationApi.getById(selectedApplication._id);
        if (updated.description) {
          setSelectedApplication(normalizeApiData(updated));
          clearInterval(detailInterval);
        }
      }, 5_000);
    }
    return () => clearInterval(detailInterval);
  }, [selectedApplication]);

  // Handlers pour les interactions utilisateur
  const handleCardClick = (application: Application): void => {
    setSelectedApplication(application);
    setOriginalApplication(JSON.parse(JSON.stringify(application)));
    setHasUnsavedChanges(false);
  };

  const handleBackClick = (): void => {
    if (hasUnsavedChanges) {
      if (
        window.confirm(
          "Vous avez des modifications non enregistrées. Êtes-vous sûr de vouloir quitter sans enregistrer ?",
        )
      ) {
        setSelectedApplication(null);
        setHasUnsavedChanges(false);
      }
    } else {
      setSelectedApplication(null);
    }
  };

  // Gestion des champs de formulaire
  const handleFieldChange = (field: string, value: string) => {
    if (!selectedApplication) return;

    // Gérer spécialement les notes
    if (field === "notes") {
      try {
        const notes = JSON.parse(value);
        setSelectedApplication({
          ...selectedApplication,
          notes: notes,
        });
      } catch {
        // Si ce n'est pas du JSON valide, ignorer
        return;
      }
    } else {
      setSelectedApplication({
        ...selectedApplication,
        [field]: value,
      });
    }
    setHasUnsavedChanges(true);
  };

  // Fonctions pour les notes
  const handleAddNote = async (noteText: string) => {
    if (!selectedApplication || !noteText.trim()) return;

    try {
      setIsAddingNote(true);

      // Mettre à jour localement d'abord
      const updatedNotes = [...(selectedApplication.notes || []), noteText];
      setSelectedApplication({
        ...selectedApplication,
        notes: updatedNotes,
      });

  
      // Rafraîchir en arrière-plan
      await fetchData(false);

      addNotification("success", "Note ajoutée avec succès");
    } catch (error) {
      console.error("Erreur lors de l'ajout de la note:", error);
      addNotification("error", "Erreur lors de l'ajout de la note");

      // Restaurer l'état précédent en cas d'erreur
      if (selectedApplication && originalApplication) {
        setSelectedApplication({
          ...selectedApplication,
          notes: originalApplication.notes,
        });
      }
    } finally {
      setIsAddingNote(false);
    }
  };

  const handleEditNote = async (noteIndex: number, noteText: string) => {
    if (!selectedApplication || !noteText.trim()) return;

    try {
      const updatedNotes = [...(selectedApplication.notes || [])];
      updatedNotes[noteIndex] = noteText;

      await fetchData();
      router.refresh(); // ← rafraîchit la page dès que la note est modifiée
      addNotification("success", "Note modifiée avec succès");
    } catch (error) {
      console.error("Erreur lors de la modification de la note:", error);
      addNotification("error", "Erreur lors de la modification de la note");
    }
  };

  const handleDeleteNote = async (noteIndex: number) => {
    if (!selectedApplication) return;

    try {
      // 1. Mettre à jour les états de suppression
      setIsDeletingNote(true);
      setDeletingNoteIndex(noteIndex);

      // 2. Créer une copie locale des notes et mettre à jour
      const updatedNotes = [...(selectedApplication.notes || [])];
      updatedNotes.splice(noteIndex, 1);

      // 3. Mettre à jour d'abord l'application sélectionnée localement
      setSelectedApplication({
        ...selectedApplication,
        notes: updatedNotes,
      });

      // 5. Rafraîchir les données en arrière-plan
      await fetchData(false); // silent refresh

      addNotification("success", "Note supprimée avec succès");
    } catch (error) {
      console.error("Erreur lors de la suppression de la note:", error);
      addNotification("error", "Erreur lors de la suppression de la note");

      // En cas d'erreur, restaurer l'état précédent
      if (selectedApplication && originalApplication) {
        setSelectedApplication({
          ...selectedApplication,
          notes: originalApplication.notes,
        });
      }
    } finally {
      setIsDeletingNote(false);
      setDeletingNoteIndex(null);
    }
  };

  // Fonctions pour sauvegarder / annuler / supprimer
  const handleSaveChanges = async () => {
    try {
      if (!selectedApplication) return;

      await applicationApi.update(selectedApplication._id, selectedApplication);
      await fetchData();
      router.refresh(); // ← rafraîchit la page dès que la candidature est enregistrée
      setOriginalApplication(JSON.parse(JSON.stringify(selectedApplication)));
      setHasUnsavedChanges(false);
      addNotification("success", "Candidature mise à jour avec succès");
    } catch (error) {
      console.error("Erreur lors de la mise à jour de la candidature:", error);
      addNotification(
        "error",
        "Erreur lors de la mise à jour de la candidature",
      );
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
        "Êtes-vous sûr de vouloir supprimer cette candidature ? Cette action est irréversible.",
      )
    ) {
      return;
    }

    try {
      await applicationApi.delete(selectedApplication._id);
      setSelectedApplication(null);
      await fetchData();
      router.refresh(); // ← rafraîchit la page après suppression
      addNotification("success", "Candidature supprimée avec succès");
    } catch (error) {
      console.error("Erreur lors de la suppression de la candidature:", error);
      addNotification(
        "error",
        "Erreur lors de la suppression de la candidature",
      );
    }
  };

  // Fonction pour archiver/désarchiver une candidature
  const handleToggleArchive = async () => {
    if (!selectedApplication) return;

    try {
      const updatedApplication = {
        ...selectedApplication,
        archived: !selectedApplication.archived,
      };

      await applicationApi.update(selectedApplication._id, updatedApplication);

      // rafraîchissement immédiat de la page
      addNotification(
        "success",
        selectedApplication.archived
          ? "Candidature désarchivée avec succès"
          : "Candidature archivée avec succès",
      );
      setSelectedApplication(null);
      await fetchData();
      router.refresh(); // ← rafraîchit la page après archivage/désarchivage
    } catch (error) {
      console.error("Erreur lors de l'archivage/désarchivage:", error);
      addNotification("error", "Erreur lors de l'archivage de la candidature");
    }
  };

  // Groupe les applications par statut en excluant les archivées
  const groupedApplications = applications
    .filter((app) => !app.archived) // Filtre pour exclure les candidatures archivées
    .reduce(
      (acc, app) => {
        if (!acc[app.status]) {
          acc[app.status] = [];
        }
        acc[app.status].push(app);
        return acc;
      },
      {} as Record<string, Application[]>,
    );

  // États de chargement et d'erreur
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900 text-white">
        <p className="text-xl">Chargement des données...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900 text-white">
        <p className="text-xl">Erreur: {error}</p>
      </div>
    );
  }

  return (
    // Forcer l'absence de défilement sur tous les éléments parents
    <div className="h-screen overflow-hidden fixed inset-0 w-full bg-blue-night text-white pt-16">
      {" "}
      {/* Ajout du pt-16 */}
      <div className="max-w-7xl mx-auto p-6 h-full flex flex-col">
        <div className="flex items-center space-x-2 mb-4">
          <svg
            className="w-6 h-6"
            fill="currentColor"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path d="M3.5 18.49l6-6.01 4 4L22 6.92l-1.41-1.41-7.09 7.97-4-4L2 16.99z" />
          </svg>
          <h1 className="text-2xl font-semibold">Suivi des candidatures</h1>
        </div>

        {/* Tableau Kanban sans défilement horizontal mais avec défilement vertical par colonne */}
        <div className="flex-grow overflow-x-auto overflow-y-hidden custom-scrollbar">
          <KanbanBoard
            groupedApplications={groupedApplications}
            onCardClick={handleCardClick}
          />
        </div>

        {/* Détails de la candidature */}
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
      </div>
    </div>
  );
}
