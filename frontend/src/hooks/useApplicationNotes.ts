"use client";

import { useState } from "react";
import { Application } from "@/types/application";
import { mutateApplicationNotes } from "@/lib/applicationsBoard";
import type { NotificationType } from "@/contexts/NotificationContext";

interface UseApplicationNotesParams {
  selectedApplication: Application | null;
  setSelectedApplication: (a: Application | null) => void;
  refreshBoard: () => Promise<void>;
  addNotification: (type: NotificationType, message: string) => void;
}

/**
 * Manages application notes CRUD actions inside the details drawer.
 */
export function useApplicationNotes({
  selectedApplication,
  setSelectedApplication,
  refreshBoard,
  addNotification,
}: UseApplicationNotesParams) {
  const [isAddingNote, setIsAddingNote] = useState(false);
  const [isDeletingNote, setIsDeletingNote] = useState(false);
  const [deletingNoteIndex, setDeletingNoteIndex] = useState<number | null>(null);

  const handleAddNote = async (noteText: string) => {
    if (!selectedApplication || !noteText.trim()) return;
    setIsAddingNote(true);
    try {
      await mutateApplicationNotes(
        selectedApplication,
        [...(selectedApplication.notes || []), noteText],
        "Note ajoutée avec succès",
        "Erreur lors de l'ajout de la note",
        setSelectedApplication,
        refreshBoard,
        addNotification
      );
    } finally {
      setIsAddingNote(false);
    }
  };

  const handleEditNote = async (noteIndex: number, noteText: string) => {
    if (!selectedApplication || !noteText.trim()) return;
    const updatedNotes = [...(selectedApplication.notes || [])];
    updatedNotes[noteIndex] = noteText;
    await mutateApplicationNotes(
      selectedApplication,
      updatedNotes,
      "Note modifiée avec succès",
      "Erreur lors de la modification de la note",
      setSelectedApplication,
      refreshBoard,
      addNotification
    );
  };

  const handleDeleteNote = async (noteIndex: number) => {
    if (!selectedApplication) return;
    setIsDeletingNote(true);
    setDeletingNoteIndex(noteIndex);
    try {
      const updatedNotes = [...(selectedApplication.notes || [])];
      updatedNotes.splice(noteIndex, 1);
      await mutateApplicationNotes(
        selectedApplication,
        updatedNotes,
        "Note supprimée avec succès",
        "Erreur lors de la suppression de la note",
        setSelectedApplication,
        refreshBoard,
        addNotification
      );
    } finally {
      setIsDeletingNote(false);
      setDeletingNoteIndex(null);
    }
  };

  return {
    isAddingNote,
    isDeletingNote,
    deletingNoteIndex,
    handleAddNote,
    handleEditNote,
    handleDeleteNote,
  };
}
