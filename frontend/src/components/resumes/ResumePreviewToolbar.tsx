"use client";

import {
  FiX,
  FiDownload,
  FiRefreshCw,
  FiImage,
  FiFileText,
  FiEdit3,
  FiEye,
  FiShield,
} from "react-icons/fi";
import { TailoredResume } from "@/types/resume";
import {
  CV_TEMPLATES,
  getTemplate,
  type CvAccentKey,
  type CvTemplateKey,
} from "@/lib/cvTemplates";
import AccentSwatches from "@/components/resumes/AccentSwatches";
import type { ResumeModalTab } from "@/hooks/useResumePreview";

interface ResumePreviewToolbarProps {
  resume: TailoredResume;
  activeTab: ResumeModalTab;
  selectedTemplate: CvTemplateKey;
  selectedAccent: CvAccentKey;
  withPhoto: boolean;
  loadingPdf: boolean;
  downloading: boolean;
  regenerating: boolean;
  hasRegenerate: boolean;
  onTabChange: (tab: ResumeModalTab) => void;
  onTemplateChange: (t: CvTemplateKey) => void;
  onAccentChange: (a: CvAccentKey) => void;
  onPhotoToggle: () => void;
  onRegenerate: () => void;
  onDownload: () => void;
  onClose: () => void;
}

export default function ResumePreviewToolbar({
  resume,
  activeTab,
  selectedTemplate,
  selectedAccent,
  withPhoto,
  loadingPdf,
  downloading,
  regenerating,
  hasRegenerate,
  onTabChange,
  onTemplateChange,
  onAccentChange,
  onPhotoToggle,
  onRegenerate,
  onDownload,
  onClose,
}: ResumePreviewToolbarProps) {
  const supportsPhoto = getTemplate(selectedTemplate).supportsPhoto;

  return (
    <>
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
            CV vectoriel A4 certifié ATS • Modèle {getTemplate(selectedTemplate).label}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <div className="flex bg-slate-900/80 p-1 rounded-lg border border-slate-700/70 text-xs">
            <button
              onClick={() => onTabChange("preview")}
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
              onClick={() => onTabChange("edit")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-medium transition-all ${
                activeTab === "edit"
                  ? "bg-blue-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <FiEdit3 className="text-xs" />
              <span>Éditer le contenu</span>
            </button>
            <button
              onClick={() => onTabChange("ats")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-medium transition-all ${
                activeTab === "ats"
                  ? "bg-blue-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <FiShield className="text-xs" />
              <span>Score ATS &amp; Export</span>
            </button>
          </div>

          {hasRegenerate && (
            <button
              onClick={onRegenerate}
              disabled={regenerating}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-emerald-600/40 bg-emerald-900/30 hover:bg-emerald-800/40 text-emerald-300 text-xs font-medium transition-colors disabled:opacity-50"
              title="Relancer l'adaptation IA sur l'offre"
            >
              <FiRefreshCw className={`text-xs ${regenerating ? "animate-spin" : ""}`} />
              <span>{regenerating ? "Génération..." : "Régénérer"}</span>
            </button>
          )}

          <button
            onClick={onDownload}
            disabled={downloading || loadingPdf}
            className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white px-3.5 py-1.5 rounded-lg text-xs font-semibold shadow-md shadow-blue-500/20 transition-colors"
          >
            {downloading ? <FiRefreshCw className="animate-spin" /> : <FiDownload />}
            <span>Télécharger</span>
          </button>

          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
            aria-label="Fermer"
          >
            <FiX className="text-xl" />
          </button>
        </div>
      </div>

      {activeTab === "preview" && (
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 px-6 py-2.5 border-b border-slate-800 bg-[#131d31] text-xs">
          <div className="flex items-center gap-2">
            <span className="text-slate-400">Modèle</span>
            <div className="flex bg-slate-900/60 p-1 rounded-lg border border-slate-700/60">
              {CV_TEMPLATES.map((tmpl) => (
                <button
                  key={tmpl.key}
                  type="button"
                  onClick={() => onTemplateChange(tmpl.key)}
                  aria-pressed={selectedTemplate === tmpl.key}
                  title={tmpl.hint}
                  className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                    selectedTemplate === tmpl.key
                      ? "bg-blue-600 text-white shadow-sm"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  {tmpl.label}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-slate-400">Couleur</span>
            <AccentSwatches value={selectedAccent} onChange={onAccentChange} />
          </div>

          {supportsPhoto && (
            <button
              type="button"
              onClick={onPhotoToggle}
              aria-pressed={withPhoto}
              className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg border font-medium transition-colors ${
                withPhoto
                  ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-300"
                  : "bg-slate-800/80 border-slate-700 text-slate-400 hover:text-slate-200"
              }`}
              title="Afficher ou masquer la photo"
            >
              <FiImage />
              <span>Photo : {withPhoto ? "Oui" : "Non"}</span>
            </button>
          )}
        </div>
      )}
    </>
  );
}
