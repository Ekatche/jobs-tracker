"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { TailoredResume, TailoredCVSchema } from "@/types/resume";
import { resumeApi } from "@/lib/api";
import {
  DEFAULT_ACCENT,
  DEFAULT_TEMPLATE,
  resolveAccentKey,
  resolveTemplateKey,
  type CvAccentKey,
  type CvTemplateKey,
  type ResumeAppearance,
} from "@/lib/cvTemplates";

export type ResumeModalTab = "preview" | "edit" | "ats";

interface UseResumePreviewParams {
  resume: TailoredResume | null;
  isOpen: boolean;
  initialTab: ResumeModalTab;
  onUpdateAppearance?: (resumeId: string, appearance: ResumeAppearance) => Promise<void>;
  onUpdateContent?: (resumeId: string, content: TailoredCVSchema) => Promise<void>;
  onRegenerate?: (resume: TailoredResume) => Promise<void>;
}

/**
 * Manages PDF rendering race protection, theme customization queue, and CV content edits.
 */
export function useResumePreview({
  resume,
  isOpen,
  initialTab,
  onUpdateAppearance,
  onUpdateContent,
  onRegenerate,
}: UseResumePreviewParams) {
  const [activeTab, setActiveTab] = useState<ResumeModalTab>("preview");
  const [atsRefreshKey, setAtsRefreshKey] = useState<number>(0);
  const [selectedTemplate, setSelectedTemplate] = useState<CvTemplateKey>(DEFAULT_TEMPLATE);
  const [selectedAccent, setSelectedAccent] = useState<CvAccentKey>(DEFAULT_ACCENT);
  const [withPhoto, setWithPhoto] = useState<boolean>(false);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [loadingPdf, setLoadingPdf] = useState<boolean>(false);
  const [downloading, setDownloading] = useState<boolean>(false);
  const [savingContent, setSavingContent] = useState<boolean>(false);
  const [regenerating, setRegenerating] = useState<boolean>(false);
  const [saveSuccess, setSaveSuccess] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [editableContent, setEditableContent] = useState<TailoredCVSchema | null>(null);

  const pdfRequestRef = useRef(0);
  const appearanceQueueRef = useRef<Promise<void>>(Promise.resolve());

  const resumeId = resume?.id || resume?._id || "";

  useEffect(() => {
    if (resume) {
      setSelectedTemplate(resolveTemplateKey(resume.template));
      setSelectedAccent(resolveAccentKey(resume.accent));
      setWithPhoto(resume.with_photo || false);
      setEditableContent(resume.content ? JSON.parse(JSON.stringify(resume.content)) : null);
    }
    if (initialTab) {
      setActiveTab(initialTab);
    }
    // Reset only when switching resumes or opening modal to avoid late PUT overwrite
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resume?.id, resume?._id, isOpen, initialTab]);

  const loadPdf = useCallback(async () => {
    if (!resume || !isOpen || !resumeId) return;

    const requestId = ++pdfRequestRef.current;
    setLoadingPdf(true);
    setError(null);
    try {
      const url = await resumeApi.getPdfBlobUrl(resumeId, {
        template: selectedTemplate,
        accent: selectedAccent,
        withPhoto,
      });
      if (requestId !== pdfRequestRef.current) {
        window.URL.revokeObjectURL(url);
        return;
      }
      setPdfUrl((previous) => {
        if (previous) window.URL.revokeObjectURL(previous);
        return url;
      });
    } catch (err: unknown) {
      if (requestId !== pdfRequestRef.current) return;
      console.error("Failed to load CV PDF preview:", err);
      setError("Erreur lors de la génération de l'aperçu PDF.");
    } finally {
      if (requestId === pdfRequestRef.current) setLoadingPdf(false);
    }
  }, [resume, isOpen, resumeId, selectedTemplate, selectedAccent, withPhoto]);

  useEffect(() => {
    if (activeTab === "preview") {
      loadPdf();
    }
  }, [activeTab, loadPdf]);

  const saveAppearance = (appearance: ResumeAppearance) => {
    if (!onUpdateAppearance) return;
    appearanceQueueRef.current = appearanceQueueRef.current
      .then(() => onUpdateAppearance(resumeId, appearance))
      .catch((err) => console.error("Failed to save CV appearance:", err));
  };

  const handleDownload = async () => {
    if (!resume) return;
    setDownloading(true);
    try {
      const filename = `CV_${resume.target_role}_${resume.target_company}.pdf`
        .replace(/\s+/g, "_")
        .replace(/[^\w.-]/g, "");
      await resumeApi.downloadPdf(
        resumeId,
        { template: selectedTemplate, accent: selectedAccent, withPhoto },
        filename
      );
    } catch (err: unknown) {
      console.error("Download error:", err);
      alert("Erreur lors du téléchargement du PDF.");
    } finally {
      setDownloading(false);
    }
  };

  const handleTemplateChange = (template: CvTemplateKey) => {
    setSelectedTemplate(template);
    saveAppearance({ template, accent: selectedAccent, withPhoto });
  };

  const handleAccentChange = (accent: CvAccentKey) => {
    setSelectedAccent(accent);
    saveAppearance({ template: selectedTemplate, accent, withPhoto });
  };

  const handlePhotoToggle = () => {
    const next = !withPhoto;
    setWithPhoto(next);
    saveAppearance({ template: selectedTemplate, accent: selectedAccent, withPhoto: next });
  };

  const handleRegenerateClick = async () => {
    if (!onRegenerate || !resume) return;
    if (
      !confirm(
        `Régénérer une nouvelle version du CV pour "${resume.target_role}" chez ${resume.target_company} ?`
      )
    ) {
      return;
    }
    setRegenerating(true);
    try {
      await onRegenerate(resume);
    } catch (err) {
      console.error("Regeneration failed:", err);
    } finally {
      setRegenerating(false);
    }
  };

  const handleSaveContent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editableContent || !onUpdateContent) return;

    setSavingContent(true);
    setSaveSuccess(false);
    try {
      await onUpdateContent(resumeId, editableContent);
      setSaveSuccess(true);
      setAtsRefreshKey((prev) => prev + 1);
      setTimeout(() => setSaveSuccess(false), 3000);
      setActiveTab("preview");
    } catch (err: unknown) {
      console.error("Failed to save CV content:", err);
      alert("Erreur lors de l'enregistrement des modifications.");
    } finally {
      setSavingContent(false);
    }
  };

  const handleBulletChange = (expIdx: number, bulletIdx: number, val: string) => {
    if (!editableContent) return;
    const next = { ...editableContent };
    next.experiences[expIdx].bullet_points[bulletIdx] = val;
    setEditableContent(next);
  };

  const handleAddBullet = (expIdx: number) => {
    if (!editableContent) return;
    const next = { ...editableContent };
    next.experiences[expIdx].bullet_points.push("Nouvelle réalisation percutante...");
    setEditableContent(next);
  };

  const handleRemoveBullet = (expIdx: number, bulletIdx: number) => {
    if (!editableContent) return;
    const next = { ...editableContent };
    next.experiences[expIdx].bullet_points = next.experiences[expIdx].bullet_points.filter(
      (_, i) => i !== bulletIdx
    );
    setEditableContent(next);
  };

  const handleSkillChange = (groupCategory: string, skillsStr: string) => {
    if (!editableContent) return;
    const next = { ...editableContent };
    const group = next.prioritized_skills.find((g) => g.category === groupCategory);
    if (group) {
      group.skills = skillsStr
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      setEditableContent(next);
    }
  };

  return {
    resumeId,
    activeTab,
    setActiveTab,
    atsRefreshKey,
    selectedTemplate,
    selectedAccent,
    withPhoto,
    pdfUrl,
    loadingPdf,
    downloading,
    savingContent,
    regenerating,
    saveSuccess,
    error,
    editableContent,
    setEditableContent,
    handleDownload,
    handleTemplateChange,
    handleAccentChange,
    handlePhotoToggle,
    handleRegenerateClick,
    handleSaveContent,
    handleBulletChange,
    handleAddBullet,
    handleRemoveBullet,
    handleSkillChange,
  };
}
