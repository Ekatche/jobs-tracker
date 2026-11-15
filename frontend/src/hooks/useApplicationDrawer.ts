"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Application } from "@/types/application";
import { applicationApi, type OfferEvaluation } from "@/lib/api";

/**
 * Manages state and side effects for the application details slide-over drawer.
 */
export function useApplicationDrawer(
  application: Application | null,
  onChange: (field: string, value: string) => void,
  onClose: () => void
) {
  const router = useRouter();

  // Local notes state
  const [localNotes, setLocalNotes] = useState<string[]>([]);
  const [newNote, setNewNote] = useState<string>("");
  const [isAddingLocalNote, setIsAddingLocalNote] = useState<boolean>(false);
  const [editingNoteIndex, setEditingNoteIndex] = useState<number | null>(null);
  const [editedNoteText, setEditedNoteText] = useState<string>("");
  const [isRegeneratingDesc, setIsRegeneratingDesc] = useState<boolean>(false);
  const [isLinkingOffer, setIsLinkingOffer] = useState<boolean>(false);
  const [descError, setDescError] = useState<string | null>(null);

  // AI Evaluation state
  const [evaluation, setEvaluation] = useState<OfferEvaluation | null>(null);
  const [loadingEvaluation, setLoadingEvaluation] = useState<boolean>(false);
  const [isScoring, setIsScoring] = useState<boolean>(false);
  const [scoringError, setScoringError] = useState<string | null>(null);
  const [scoreSuccessMessage, setScoreSuccessMessage] = useState<string | null>(null);

  const fetchEvaluation = useCallback(async (appId: string) => {
    setLoadingEvaluation(true);
    setScoringError(null);
    try {
      const evalData = await applicationApi.getEvaluation(appId);
      setEvaluation(evalData);
    } catch (err) {
      console.warn("Could not fetch evaluation for application:", err);
      setEvaluation(null);
    } finally {
      setLoadingEvaluation(false);
    }
  }, []);

  // Sync notes and fetch evaluation whenever application changes
  useEffect(() => {
    if (application?.notes) {
      setLocalNotes([...application.notes]);
    } else {
      setLocalNotes([]);
    }

    if (application?._id) {
      fetchEvaluation(application._id);
    } else {
      setEvaluation(null);
    }
    setScoringError(null);
    setScoreSuccessMessage(null);
  }, [application, fetchEvaluation]);

  // Close drawer on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const handleAddLocalNote = () => {
    if (!newNote.trim()) return;
    const updatedNotes = [...localNotes, newNote.trim()];
    setLocalNotes(updatedNotes);
    setNewNote("");
    setIsAddingLocalNote(false);
    onChange("notes", JSON.stringify(updatedNotes));
  };

  const handleEditLocalNote = (index: number, noteText: string) => {
    setEditingNoteIndex(index);
    setEditedNoteText(noteText);
  };

  const handleSaveEditNote = () => {
    if (editingNoteIndex === null || !editedNoteText.trim()) return;
    const updatedNotes = [...localNotes];
    updatedNotes[editingNoteIndex] = editedNoteText.trim();
    setLocalNotes(updatedNotes);
    setEditingNoteIndex(null);
    setEditedNoteText("");
    onChange("notes", JSON.stringify(updatedNotes));
  };

  const handleDeleteLocalNote = (index: number) => {
    const updatedNotes = [...localNotes];
    updatedNotes.splice(index, 1);
    setLocalNotes(updatedNotes);
    onChange("notes", JSON.stringify(updatedNotes));
  };

  const handleRegenerateDescription = async () => {
    if (!application?._id || !application.url) return;
    try {
      setIsRegeneratingDesc(true);
      setDescError(null);
      const updated = await applicationApi.regenerateDescription(application._id);
      if (updated?.description) {
        onChange("description", updated.description);
      }
      if (updated?.offer_id && !application.offer_id) {
        onChange("offer_id", updated.offer_id);
      }
    } catch (err: unknown) {
      console.error("Erreur régénération description:", err);
      const msg =
        err instanceof Error
          ? err.message
          : "Impossible d'extraire une description exploitable depuis cette offre.";
      setDescError(msg);
    } finally {
      setIsRegeneratingDesc(false);
    }
  };

  const handleLinkOffer = async (): Promise<string | null> => {
    if (!application?._id || isLinkingOffer) return null;
    setIsLinkingOffer(true);
    try {
      const updated = await applicationApi.linkOffer(application._id);
      if (updated?.offer_id) {
        onChange("offer_id", updated.offer_id);
        return updated.offer_id;
      }
      return null;
    } catch (err) {
      console.error("Erreur lors de la liaison de l'offre:", err);
      return null;
    } finally {
      setIsLinkingOffer(false);
    }
  };

  // Link offer before navigating (stored offer_id can point to a deleted offer)
  const handleOpenOffer = async (suffix = "") => {
    const targetOfferId =
      (await handleLinkOffer()) || application?.offer_id || evaluation?.offer_id;
    if (targetOfferId) {
      router.push(`/offers/${targetOfferId}${suffix}`);
    }
  };

  const handleOpenTailoredResumeWithAutoLink = async () => {
    // Open tab synchronously during user click so Safari does not block window.open after await
    const tab = window.open("", "_blank");
    const targetOfferId =
      (await handleLinkOffer()) || application?.offer_id || evaluation?.offer_id;
    if (!tab) return;
    if (targetOfferId) {
      tab.opener = null;
      tab.location.href = `/resumes?generate_offer_id=${targetOfferId}`;
    } else {
      tab.close();
    }
  };

  const handleScoreApplication = async () => {
    if (!application?._id || isScoring) return;
    setIsScoring(true);
    setScoringError(null);
    setScoreSuccessMessage(null);

    try {
      const result = await applicationApi.evaluate(application._id);
      setEvaluation(result);

      const offerJustLinked = Boolean(result.offer_id && !application.offer_id);
      if (offerJustLinked) {
        onChange("offer_id", result.offer_id);
      }
      setScoreSuccessMessage(
        offerJustLinked
          ? "Évaluation terminée ! L'offre est désormais accessible ci-dessus (\"Offre scrapée\")."
          : "Évaluation d'adéquation IA terminée avec succès !"
      );
      setTimeout(() => setScoreSuccessMessage(null), 4000);
    } catch (err: unknown) {
      console.error("Erreur lors du scoring de la candidature:", err);
      let errorMsg = "Impossible de générer le scoring IA pour cette offre.";
      if (err && typeof err === "object" && "response" in err) {
        const responseData = (
          err as { response?: { data?: { detail?: string } } }
        ).response?.data;
        if (responseData?.detail) {
          errorMsg = responseData.detail;
        }
      } else if (err instanceof Error) {
        errorMsg = err.message;
      }
      setScoringError(errorMsg);
    } finally {
      setIsScoring(false);
    }
  };

  return {
    localNotes,
    newNote,
    setNewNote,
    isAddingLocalNote,
    setIsAddingLocalNote,
    editingNoteIndex,
    setEditingNoteIndex,
    editedNoteText,
    setEditedNoteText,
    isRegeneratingDesc,
    isLinkingOffer,
    descError,
    evaluation,
    loadingEvaluation,
    isScoring,
    scoringError,
    scoreSuccessMessage,
    handleAddLocalNote,
    handleEditLocalNote,
    handleSaveEditNote,
    handleDeleteLocalNote,
    handleRegenerateDescription,
    handleLinkOffer,
    handleOpenOffer,
    handleOpenTailoredResumeWithAutoLink,
    handleScoreApplication,
  };
}
