"use client";

import React, { useEffect, useState, useCallback, useRef } from "react";
import { interviewPrepApi } from "@/lib/api";
import { InterviewPrep } from "@/types/interview";
import InterviewPrepSections from "./InterviewPrepSections";
import InterviewPrepHeader, {
  type InterviewPrepSection,
} from "./InterviewPrepHeader";
import { FiRefreshCw } from "react-icons/fi";

interface InterviewPrepTabProps {
  offerId: string;
  targetRole?: string;
  targetCompany?: string;
}

export default function InterviewPrepTab({
  offerId,
  targetCompany,
}: InterviewPrepTabProps) {
  const [prep, setPrep] = useState<InterviewPrep | null>(null);
  const [loading, setLoading] = useState(true);
  const [generatingModule, setGeneratingModule] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [activeSection, setActiveSection] = useState<InterviewPrepSection>("stories");
  const [bankOpen, setBankOpen] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const loadPrep = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await interviewPrepApi.get(offerId);
      setPrep(data);
    } catch (err: unknown) {
      console.error("Error loading interview prep:", err);
      setError(
        err instanceof Error ? err.message : "Impossible de charger la préparation d'entretien."
      );
    } finally {
      setLoading(false);
    }
  }, [offerId]);

  useEffect(() => {
    loadPrep();
  }, [loadPrep]);

  const storiesCount = prep?.story_slots?.length ?? 0;
  const hasAudience = !!(prep?.recruiter_pack || prep?.hm_pack || prep?.tech_pack);
  const questionsCount = prep?.anticipated_questions?.length || 0;
  const reverseCount = prep?.reverse_questions?.length || 0;
  const practiceCount = prep?.practice_attempts?.length || 0;
  const totalCompleted =
    (storiesCount > 0 ? 1 : 0) +
    (hasAudience ? 1 : 0) +
    (questionsCount > 0 ? 1 : 0) +
    (reverseCount > 0 ? 1 : 0);

  const handleGenerateModule = async (
    moduleType: "stories" | "audience-packs" | "questions" | "reverse-questions" | "all"
  ) => {
    const hasContent = {
      stories: storiesCount > 0,
      "audience-packs": hasAudience,
      questions: questionsCount > 0,
      "reverse-questions": reverseCount > 0,
      all: totalCompleted > 0,
    }[moduleType];

    if (hasContent) {
      let message =
        moduleType === "all"
          ? "Tout régénérer ? Le contenu actuel des 4 sections, y compris vos corrections, sera remplacé."
          : "Régénérer cette section ? Son contenu actuel, y compris vos corrections, sera remplacé.";
      if ((moduleType === "questions" || moduleType === "all") && practiceCount > 0) {
        message += ` Votre historique d'entraînement (${practiceCount} essai${practiceCount > 1 ? "s" : ""}) sera effacé.`;
      }
      if (moduleType === "stories" || moduleType === "all") {
        const edited = (prep?.story_slots ?? [])
          .filter((slot) => slot.angle_edited)
          .map((slot) => slot.requirement);
        if (edited.length > 0) {
          message += ` Les angles rédigés à la main pour : ${edited.join(", ")} seront perdus si la même histoire n'est pas reprise.`;
        }
      }
      if (!confirm(message)) return;
    }

    const controller = new AbortController();
    abortRef.current = controller;
    try {
      setGeneratingModule(moduleType);
      setError(null);
      const loaders = {
        stories: () => interviewPrepApi.generateStories(offerId, controller.signal),
        "audience-packs": () =>
          interviewPrepApi.generateAudiencePacks(offerId, controller.signal),
        questions: () => interviewPrepApi.generateQuestions(offerId, controller.signal),
        "reverse-questions": () =>
          interviewPrepApi.generateReverseQuestions(offerId, controller.signal),
        all: () => interviewPrepApi.generateAll(offerId, controller.signal),
      };
      setPrep(await loaders[moduleType]());
    } catch (err: unknown) {
      if (controller.signal.aborted) return;
      console.error(`Error generating ${moduleType}:`, err);
      setError(
        err instanceof Error ? err.message : `Erreur lors de la génération du module ${moduleType}`
      );
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
        setGeneratingModule(null);
      }
    }
  };

  const handleCopyMarkdown = async () => {
    try {
      const md = await interviewPrepApi.exportMarkdown(offerId);
      await navigator.clipboard.writeText(md);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Error copying markdown:", err);
    }
  };

  const handleDownloadMarkdown = async () => {
    try {
      const compSlug = targetCompany ? targetCompany.replace(/[^\w]/g, "_").toLowerCase() : "company";
      await interviewPrepApi.downloadMarkdown(offerId, `prep_${compSlug}_${offerId.slice(0, 6)}.md`);
    } catch (err) {
      console.error("Error downloading markdown:", err);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-slate-400 space-y-3">
        <FiRefreshCw className="w-8 h-8 animate-spin text-indigo-400" />
        <p className="text-sm">Chargement du kit de préparation d&apos;entretien...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <InterviewPrepHeader
        targetCompany={targetCompany}
        totalCompleted={totalCompleted}
        generatingModule={generatingModule}
        copied={copied}
        error={error}
        activeSection={activeSection}
        storiesCount={storiesCount}
        hasAudience={hasAudience}
        questionsCount={questionsCount}
        reverseCount={reverseCount}
        onGenerateAll={() => handleGenerateModule("all")}
        onCancelGeneration={() => abortRef.current?.abort()}
        onCopyMarkdown={handleCopyMarkdown}
        onDownloadMarkdown={handleDownloadMarkdown}
        onSelectSection={setActiveSection}
      />

      <InterviewPrepSections
        activeSection={activeSection}
        offerId={offerId}
        prep={prep}
        generatingModule={generatingModule}
        storiesCount={storiesCount}
        hasAudience={hasAudience}
        questionsCount={questionsCount}
        reverseCount={reverseCount}
        bankOpen={bankOpen}
        onSetBankOpen={setBankOpen}
        onPrepUpdated={setPrep}
        onGenerateModule={handleGenerateModule}
        onCancel={() => abortRef.current?.abort()}
      />
    </div>
  );
}
