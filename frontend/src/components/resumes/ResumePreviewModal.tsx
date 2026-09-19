"use client";

import { useEffect, useState } from "react";
import {
  FiX,
  FiDownload,
  FiCheck,
  FiRefreshCw,
  FiImage,
  FiFileText,
  FiEdit3,
  FiEye,
  FiPlus,
  FiTrash2,
  FiSave,
} from "react-icons/fi";
import { TailoredResume, TailoredCVSchema } from "@/types/resume";
import { resumeApi } from "@/lib/api";

interface ResumePreviewModalProps {
  resume: TailoredResume | null;
  isOpen: boolean;
  onClose: () => void;
  onUpdateTemplate?: (resumeId: string, template: string, withPhoto: boolean) => Promise<void>;
  onUpdateContent?: (resumeId: string, content: TailoredCVSchema) => Promise<void>;
  onRegenerate?: (resume: TailoredResume) => Promise<void>;
  initialTab?: "preview" | "edit";
}

export default function ResumePreviewModal({
  resume,
  isOpen,
  onClose,
  onUpdateTemplate,
  onUpdateContent,
  onRegenerate,
  initialTab = "preview",
}: ResumePreviewModalProps) {
  const [activeTab, setActiveTab] = useState<"preview" | "edit">("preview");
  const [selectedTemplate, setSelectedTemplate] = useState<string>("sidebar_elegance");
  const [withPhoto, setWithPhoto] = useState<boolean>(false);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [loadingPdf, setLoadingPdf] = useState<boolean>(false);
  const [downloading, setDownloading] = useState<boolean>(false);
  const [savingContent, setSavingContent] = useState<boolean>(false);
  const [regenerating, setRegenerating] = useState<boolean>(false);
  const [saveSuccess, setSaveSuccess] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Editable copy of CV content
  const [editableContent, setEditableContent] = useState<TailoredCVSchema | null>(null);

  useEffect(() => {
    if (resume) {
      setSelectedTemplate(resume.template || "sidebar_elegance");
      setWithPhoto(resume.with_photo || false);
      setEditableContent(resume.content ? JSON.parse(JSON.stringify(resume.content)) : null);
    }
    if (initialTab) {
      setActiveTab(initialTab);
    }
  }, [resume, initialTab, isOpen]);

  // Re-fetch PDF blob URL when template, withPhoto or resume changes
  const loadPdf = async () => {
    if (!resume || !isOpen) return;
    const resumeId = resume.id || resume._id;
    if (!resumeId) return;

    setLoadingPdf(true);
    setError(null);
    try {
      const url = await resumeApi.getPdfBlobUrl(resumeId, selectedTemplate, withPhoto);
      setPdfUrl(url);
    } catch (err: unknown) {
      console.error("Failed to load CV PDF preview:", err);
      setError("Erreur lors de la génération de l'aperçu PDF.");
    } finally {
      setLoadingPdf(false);
    }
  };

  useEffect(() => {
    if (activeTab === "preview") {
      loadPdf();
    }
  }, [resume?.id, resume?._id, resume?.updated_at, selectedTemplate, withPhoto, isOpen, activeTab]);

  if (!isOpen || !resume) return null;

  const resumeId = resume.id || resume._id || "";

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const filename = `CV_${resume.target_role}_${resume.target_company}.pdf`
        .replace(/\s+/g, "_")
        .replace(/[^\w.-]/g, "");
      await resumeApi.downloadPdf(resumeId, selectedTemplate, withPhoto, filename);
    } catch (err: unknown) {
      console.error("Download error:", err);
      alert("Erreur lors du téléchargement du PDF.");
    } finally {
      setDownloading(false);
    }
  };

  const handleTemplateChange = async (tmpl: string) => {
    setSelectedTemplate(tmpl);
    if (onUpdateTemplate) {
      await onUpdateTemplate(resumeId, tmpl, withPhoto);
    }
  };

  const handlePhotoToggle = async () => {
    const newVal = !withPhoto;
    setWithPhoto(newVal);
    if (onUpdateTemplate) {
      await onUpdateTemplate(resumeId, selectedTemplate, newVal);
    }
  };

  const handleRegenerateClick = async () => {
    if (!onRegenerate) return;
    if (!confirm(`Régénérer une nouvelle version du CV pour "${resume.target_role}" chez ${resume.target_company} ?`)) {
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
      setTimeout(() => setSaveSuccess(false), 3000);
      // Reload preview
      await loadPdf();
      setActiveTab("preview");
    } catch (err: unknown) {
      console.error("Failed to save CV content:", err);
      alert("Erreur lors de l'enregistrement des modifications.");
    } finally {
      setSavingContent(false);
    }
  };

  // Helpers for editing experiences
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
    next.experiences[expIdx].bullet_points = next.experiences[expIdx].bullet_points.filter((_, i) => i !== bulletIdx);
    setEditableContent(next);
  };

  // Helpers for editing skills
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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="bg-[#131d31] border border-slate-700/60 rounded-xl shadow-2xl flex flex-col w-full max-w-5xl h-[92vh] overflow-hidden text-slate-100 animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between px-6 py-4 border-b border-slate-800 bg-[#16233b] gap-4">
          <div className="flex flex-col">
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <FiFileText className="text-blue-400" />
              <span>{resume.target_role}</span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300 font-normal">
                {resume.target_company}
              </span>
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              CV vectoriel A4 certifié ATS • Modèle {selectedTemplate === "executive_minimalist" ? "Executive Minimalist" : "Sidebar Elegance"}
            </p>
          </div>

          {/* Mode Switch Tabs & Controls */}
          <div className="flex flex-wrap items-center gap-2.5">
            {/* View / Edit Mode Switcher */}
            <div className="flex bg-slate-900/80 p-1 rounded-lg border border-slate-700/70 text-xs">
              <button
                onClick={() => setActiveTab("preview")}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-medium transition-all ${
                  activeTab === "preview"
                    ? "bg-blue-600 text-white shadow-sm"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                <FiEye className="text-xs" />
                <span>Aperçu PDF</span>
              </button>
              <button
                onClick={() => setActiveTab("edit")}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-medium transition-all ${
                  activeTab === "edit"
                    ? "bg-blue-600 text-white shadow-sm"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                <FiEdit3 className="text-xs" />
                <span>Éditer le contenu</span>
              </button>
            </div>

            {/* Template Selector (in preview mode) */}
            {activeTab === "preview" && (
              <div className="flex bg-slate-900/60 p-1 rounded-lg border border-slate-700/60 text-xs">
                <button
                  onClick={() => handleTemplateChange("sidebar_elegance")}
                  className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                    selectedTemplate === "sidebar_elegance"
                      ? "bg-blue-600 text-white shadow-sm"
                      : "text-slate-400 hover:text-white"
                  }`}
                  title="Sidebar à 2 colonnes"
                >
                  Sidebar
                </button>
                <button
                  onClick={() => handleTemplateChange("executive_minimalist")}
                  className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                    selectedTemplate === "executive_minimalist"
                      ? "bg-blue-600 text-white shadow-sm"
                      : "text-slate-400 hover:text-white"
                  }`}
                  title="Mono-colonne Minimalist"
                >
                  Minimalist
                </button>
              </div>
            )}

            {/* Photo Toggle */}
            {activeTab === "preview" && (
              <button
                onClick={handlePhotoToggle}
                className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
                  withPhoto
                    ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-300"
                    : "bg-slate-800/80 border-slate-700 text-slate-400 hover:text-slate-200"
                }`}
                title="Afficher ou masquer la photo"
              >
                <FiImage />
                <span>Photo: {withPhoto ? "Oui" : "Non"}</span>
              </button>
            )}

            {/* Regenerate Button */}
            {onRegenerate && (
              <button
                onClick={handleRegenerateClick}
                disabled={regenerating}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-emerald-600/40 bg-emerald-900/30 hover:bg-emerald-800/40 text-emerald-300 text-xs font-medium transition-colors disabled:opacity-50"
                title="Relancer l'adaptation IA sur l'offre"
              >
                <FiRefreshCw className={`text-xs ${regenerating ? "animate-spin" : ""}`} />
                <span>{regenerating ? "Génération..." : "Régénérer"}</span>
              </button>
            )}

            {/* Download Button */}
            <button
              onClick={handleDownload}
              disabled={downloading || loadingPdf}
              className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white px-3.5 py-1.5 rounded-lg text-xs font-semibold shadow-md shadow-blue-500/20 transition-colors"
            >
              {downloading ? <FiRefreshCw className="animate-spin" /> : <FiDownload />}
              <span>Télécharger</span>
            </button>

            {/* Close Button */}
            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
              aria-label="Fermer"
            >
              <FiX className="text-xl" />
            </button>
          </div>
        </div>

        {/* Modal Body */}
        {activeTab === "preview" ? (
          /* PDF Viewer Body */
          <div className="flex-1 bg-slate-950/60 p-4 overflow-hidden relative flex items-center justify-center">
            {loadingPdf && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-[#131d31]/80 z-10 gap-3">
                <FiRefreshCw className="animate-spin text-3xl text-blue-400" />
                <p className="text-sm text-slate-300">Rendu du CV vectoriel en cours...</p>
              </div>
            )}

            {error && (
              <div className="text-center p-6 bg-red-950/40 border border-red-800/50 rounded-lg text-red-200 text-sm max-w-md">
                <p className="font-semibold mb-1">Échec de l'aperçu</p>
                <p className="text-xs text-red-300/80">{error}</p>
              </div>
            )}

            {!error && pdfUrl && (
              <iframe
                src={`${pdfUrl}#toolbar=0&navpanes=0`}
                className="w-full h-full rounded-lg shadow-2xl border border-slate-800 bg-white"
                title="Aperçu du CV"
              />
            )}
          </div>
        ) : (
          /* Content Editor Body */
          <div className="flex-1 bg-[#101827] p-6 overflow-y-auto">
            {editableContent ? (
              <form onSubmit={handleSaveContent} className="max-w-4xl mx-auto space-y-6 pb-8">
                <div className="flex items-center justify-between border-b border-slate-800 pb-4">
                  <div>
                    <h3 className="text-base font-bold text-white">Personnalisation du contenu</h3>
                    <p className="text-xs text-slate-400">
                      Modifiez les formulations et puces d'impact générées pour les ajuster selon vos préférences.
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    {saveSuccess && (
                      <span className="flex items-center gap-1 text-xs text-emerald-400 bg-emerald-950/60 px-2.5 py-1 rounded-md border border-emerald-800/50">
                        <FiCheck /> Modifications enregistrées !
                      </span>
                    )}
                    <button
                      type="submit"
                      disabled={savingContent}
                      className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-xs font-bold shadow-md transition-colors"
                    >
                      {savingContent ? <FiRefreshCw className="animate-spin" /> : <FiSave />}
                      <span>Enregistrer et voir l'aperçu</span>
                    </button>
                  </div>
                </div>

                {/* Target Role Title */}
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-2">
                  <label className="block text-xs font-semibold text-slate-300">
                    Intitulé du poste affiché en haut du CV
                  </label>
                  <input
                    type="text"
                    value={editableContent.target_role_title}
                    onChange={(e) =>
                      setEditableContent({ ...editableContent, target_role_title: e.target.value })
                    }
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
                    placeholder="Ex: Ingénieur IA"
                    required
                  />
                  <p className="text-[11px] text-slate-400">
                    Astuce ATS : Conservez l'intitulé exact de l'annonce pour maximiser le score de pertinence.
                  </p>
                </div>

                {/* Summary */}
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-2">
                  <label className="block text-xs font-semibold text-slate-300">
                    Accroche professionnelle (Summary)
                  </label>
                  <textarea
                    rows={3}
                    value={editableContent.professional_summary}
                    onChange={(e) =>
                      setEditableContent({ ...editableContent, professional_summary: e.target.value })
                    }
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-blue-500 leading-relaxed"
                    placeholder="3 à 4 lignes d'impact..."
                    required
                  />
                </div>

                {/* Prioritized Skills */}
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-3">
                  <h4 className="text-xs font-semibold text-slate-300">Compétences clés par catégorie</h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {editableContent.prioritized_skills.map((group, idx) => (
                      <div key={idx} className="bg-slate-950/80 p-3 rounded-lg border border-slate-800 space-y-1.5">
                        <span className="text-xs font-medium text-blue-300 block">{group.category}</span>
                        <input
                          type="text"
                          value={group.skills.join(", ")}
                          onChange={(e) => handleSkillChange(group.category, e.target.value)}
                          className="w-full px-2.5 py-1.5 bg-slate-900 border border-slate-700/80 rounded-md text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                          placeholder="Compétences séparées par des virgules"
                        />
                      </div>
                    ))}
                  </div>
                </div>

                {/* Experiences */}
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-4">
                  <h4 className="text-xs font-semibold text-slate-300">Expériences professionnelles & Puces d'impact</h4>
                  <div className="space-y-4">
                    {editableContent.experiences.map((exp, expIdx) => (
                      <div key={expIdx} className="bg-slate-950/70 border border-slate-800/90 rounded-lg p-3.5 space-y-3">
                        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/80 pb-2">
                          <div className="font-semibold text-xs text-white">
                            <span>{exp.title}</span> • <span className="text-blue-400">{exp.company}</span>
                          </div>
                          <span className="text-[11px] text-slate-400">
                            {exp.start_date} – {exp.end_date || "Présent"}
                          </span>
                        </div>

                        {/* Bullet points */}
                        <div className="space-y-2">
                          <label className="text-[11px] font-medium text-slate-400 block">Puces de réalisations :</label>
                          {exp.bullet_points.map((bullet, bIdx) => (
                            <div key={bIdx} className="flex items-start gap-2">
                              <textarea
                                rows={2}
                                value={bullet}
                                onChange={(e) => handleBulletChange(expIdx, bIdx, e.target.value)}
                                className="flex-1 px-2.5 py-1 bg-slate-900 border border-slate-700/70 rounded text-xs text-slate-200 focus:outline-none focus:border-blue-500 leading-relaxed"
                              />
                              <button
                                type="button"
                                onClick={() => handleRemoveBullet(expIdx, bIdx)}
                                className="p-1 text-slate-500 hover:text-red-400 transition-colors mt-1"
                                title="Supprimer cette puce"
                              >
                                <FiTrash2 className="text-xs" />
                              </button>
                            </div>
                          ))}
                          <button
                            type="button"
                            onClick={() => handleAddBullet(expIdx)}
                            className="flex items-center gap-1 text-[11px] text-blue-400 hover:text-blue-300 font-medium pt-1"
                          >
                            <FiPlus className="text-xs" />
                            <span>Ajouter une puce d'impact</span>
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Submit Action bottom */}
                <div className="flex justify-end pt-4">
                  <button
                    type="submit"
                    disabled={savingContent}
                    className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white px-5 py-2 rounded-lg text-xs font-bold shadow-md transition-colors"
                  >
                    {savingContent ? <FiRefreshCw className="animate-spin" /> : <FiSave />}
                    <span>Enregistrer et générer le PDF</span>
                  </button>
                </div>
              </form>
            ) : (
              <div className="text-center py-12 text-slate-400 text-xs">
                Aucun contenu disponible pour l'édition.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
