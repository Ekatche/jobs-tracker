"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { coverLetterApi } from "@/lib/api";
import { CoverLetter } from "@/types/coverLetter";

export interface RewriteProposal {
  start: number;
  end: number;
  originalPassage: string;
  rewritten: string;
  warnings: string[];
}

interface TextSelection {
  start: number;
  end: number;
  letter: string;
}

/**
 * Manages cover letter fetching, polling, editing, PDF export, and partial passage rewrites.
 */
export function useCoverLetter(applicationId: string) {
  const [letterData, setLetterData] = useState<CoverLetter | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [generating, setGenerating] = useState<boolean>(false);
  const [textBody, setTextBody] = useState<string>("");
  const [saving, setSaving] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);
  const [viewMode, setViewMode] = useState<"preview" | "edit">("preview");
  const [showReport, setShowReport] = useState<boolean>(false);
  const [pollingTimeout, setPollingTimeout] = useState<boolean>(false);
  const [downloadingPdf, setDownloadingPdf] = useState<boolean>(false);
  const [confirmingExport, setConfirmingExport] = useState<boolean>(false);
  const [exportError, setExportError] = useState<string | null>(null);

  // Partial rewrite states
  const [selection, setSelection] = useState<TextSelection | null>(null);
  const [customInstruction, setCustomInstruction] = useState<string>("");
  const [proposal, setProposal] = useState<RewriteProposal | null>(null);
  const [rewriting, setRewriting] = useState<boolean>(false);
  const [rewriteError, setRewriteError] = useState<string | null>(null);
  const [staleError, setStaleError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const startTimeRef = useRef<number>(Date.now());

  const fetchLetter = useCallback(async () => {
    try {
      const data = await coverLetterApi.getByApplicationId(applicationId);
      setLetterData(data);
      if (data && data.versions && data.versions.length > 0) {
        const current =
          data.versions.find((v) => v.n === data.current_version) ||
          data.versions[data.versions.length - 1];
        setTextBody(current.body);
      }
      return data;
    } catch (err) {
      console.error("Erreur chargement lettre:", err);
      return null;
    } finally {
      setLoading(false);
    }
  }, [applicationId]);

  useEffect(() => {
    fetchLetter();
  }, [fetchLetter]);

  // Automatic polling while status is pending (3s interval, 3min timeout)
  useEffect(() => {
    if (letterData?.status === "pending") {
      startTimeRef.current = Date.now();
      setPollingTimeout(false);
      pollIntervalRef.current = setInterval(async () => {
        if (Date.now() - startTimeRef.current > 180000) {
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
          setPollingTimeout(true);
          return;
        }
        const updated = await fetchLetter();
        if (
          updated?.status === "ready" ||
          updated?.status === "needs_review" ||
          updated?.status === "failed"
        ) {
          setGenerating(false);
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
        }
      }, 3000);
    } else if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
    }

    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, [letterData?.status, fetchLetter]);

  const handleRegenerate = async () => {
    setGenerating(true);
    setExportError(null);
    setProposal(null);
    setSelection(null);
    // Immediate optimistic update to show the spinner
    setLetterData((prev) =>
      prev
        ? { ...prev, status: "pending" }
        : ({
            application_id: applicationId,
            user_id: "",
            status: "pending",
            current_version: 0,
            versions: [],
          } as unknown as CoverLetter)
    );
    try {
      await coverLetterApi.regenerate(applicationId);
      await fetchLetter();
    } catch (err) {
      console.error("Erreur lors de la régénération:", err);
    }
  };

  const handleSaveEdit = async () => {
    setSaving(true);
    setProposal(null);
    setSelection(null);
    setStaleError(null);
    setCustomInstruction("");
    setRewriteError(null);
    setConfirmingExport(false);
    setExportError(null);
    try {
      const updated = await coverLetterApi.edit(applicationId, textBody);
      setLetterData(updated);
      setViewMode("preview");
    } finally {
      setSaving(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(textBody);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadPdf = async (acknowledgeReview = false) => {
    if (downloadingPdf) return;
    setConfirmingExport(false);
    setExportError(null);
    setDownloadingPdf(true);
    try {
      await coverLetterApi.downloadPdf(applicationId, undefined, acknowledgeReview);
    } catch (err) {
      console.error("Erreur téléchargement PDF:", err);
      if ((err as { status?: number }).status === 409) {
        // Letter was re-evaluated elsewhere: reload and ask for confirmation if needed
        const reloaded = await fetchLetter();
        if (reloaded?.status === "needs_review") {
          setConfirmingExport(true);
        } else {
          setExportError("La lettre a changé : rechargez-la puis réessayez l'export.");
        }
      } else {
        setExportError("Le téléchargement du PDF a échoué. Réessayez dans un instant.");
      }
    } finally {
      setDownloadingPdf(false);
    }
  };

  // Offsets remain valid only for the exact text snapshot at selection time
  const selectedPassage =
    selection && selection.letter === textBody
      ? textBody.slice(selection.start, selection.end)
      : "";

  const handleTextareaSelect = (e: React.SyntheticEvent<HTMLTextAreaElement>) => {
    const { selectionStart, selectionEnd, value } = e.currentTarget;
    setSelection(
      selectionStart !== selectionEnd
        ? { start: selectionStart, end: selectionEnd, letter: value }
        : null
    );
  };

  const handleRewrite = async (instructionToUse: string) => {
    if (!selection || !selectedPassage.trim()) return;
    const passage = selectedPassage;
    setRewriting(true);
    setRewriteError(null);
    setStaleError(null);
    try {
      const res = await coverLetterApi.rewritePassage(applicationId, {
        letter: textBody,
        passage,
        instruction: instructionToUse,
      });
      setProposal({
        start: selection.start,
        end: selection.end,
        originalPassage: passage,
        rewritten: res.rewritten,
        warnings: res.warnings || [],
      });
    } catch (err: unknown) {
      console.error("Erreur réécriture passage:", err);
      setRewriteError(
        err instanceof Error ? err.message : "Erreur lors de la réécriture du passage"
      );
    } finally {
      setRewriting(false);
    }
  };

  const handleAcceptProposal = () => {
    if (!proposal) return;
    if (textBody.slice(proposal.start, proposal.end) !== proposal.originalPassage) {
      setStaleError("Le texte a changé depuis la proposition, relancez-la.");
      return;
    }
    setTextBody(
      textBody.slice(0, proposal.start) + proposal.rewritten + textBody.slice(proposal.end)
    );
    setProposal(null);
    setSelection(null);
    setStaleError(null);
    setCustomInstruction("");
    setRewriteError(null);
  };

  const handleRejectProposal = () => {
    setProposal(null);
    setStaleError(null);
  };

  const isPending = generating || letterData?.status === "pending";
  const currentVersionData = letterData?.versions?.find(
    (v) => v.n === letterData.current_version
  );
  const savedBody = currentVersionData?.body || "";
  const isDirty = textBody !== savedBody;
  const needsReview = letterData?.status === "needs_review";
  const reviewViolations = currentVersionData?.guard_report?.violations ?? [];
  const wordCount = textBody.trim() ? textBody.trim().split(/\s+/).length : 0;

  return {
    letterData,
    loading,
    textBody,
    setTextBody,
    saving,
    copied,
    viewMode,
    setViewMode,
    showReport,
    setShowReport,
    pollingTimeout,
    downloadingPdf,
    confirmingExport,
    setConfirmingExport,
    exportError,
    setExportError,
    setSelection,
    customInstruction,
    setCustomInstruction,
    proposal,
    setProposal,
    rewriting,
    rewriteError,
    staleError,
    setStaleError,
    textareaRef,
    selectedPassage,
    isPending,
    currentVersionData,
    isDirty,
    needsReview,
    reviewViolations,
    wordCount,
    handleRegenerate,
    handleSaveEdit,
    handleCopy,
    handleDownloadPdf,
    handleTextareaSelect,
    handleRewrite,
    handleAcceptProposal,
    handleRejectProposal,
  };
}
