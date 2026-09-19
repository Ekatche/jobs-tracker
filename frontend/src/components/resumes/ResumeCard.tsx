"use client";

import { useState } from "react";
import { FiDownload, FiEye, FiTrash2, FiCalendar, FiBriefcase, FiLayers, FiRefreshCw, FiEdit3 } from "react-icons/fi";
import { TailoredResume } from "@/types/resume";
import { resumeApi } from "@/lib/api";

interface ResumeCardProps {
  resume: TailoredResume;
  onPreview: (resume: TailoredResume) => void;
  onDelete: (id: string) => Promise<void>;
  onRegenerate?: (resume: TailoredResume) => Promise<void>;
  onEdit?: (resume: TailoredResume) => void;
}

export default function ResumeCard({ resume, onPreview, onDelete, onRegenerate, onEdit }: ResumeCardProps) {
  const [downloading, setDownloading] = useState<boolean>(false);
  const [deleting, setDeleting] = useState<boolean>(false);
  const [regenerating, setRegenerating] = useState<boolean>(false);

  const resumeId = resume.id || resume._id || "";

  const handleRegenerateClick = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!onRegenerate) return;
    if (!confirm(`Régénérer une nouvelle version du CV pour "${resume.target_role}" chez ${resume.target_company} ?`)) {
      return;
    }
    setRegenerating(true);
    try {
      await onRegenerate(resume);
    } catch (err) {
      console.error("Regenerate failed:", err);
    } finally {
      setRegenerating(false);
    }
  };

  const handleDirectDownload = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setDownloading(true);
    try {
      const filename = `CV_${resume.target_role}_${resume.target_company}.pdf`
        .replace(/\s+/g, "_")
        .replace(/[^\w.-]/g, "");
      await resumeApi.downloadPdf(resumeId, resume.template, resume.with_photo, filename);
    } catch (err) {
      console.error("Download failed:", err);
      alert("Erreur lors du téléchargement du PDF.");
    } finally {
      setDownloading(false);
    }
  };

  const handleDeleteClick = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm(`Confirmer la suppression du CV adapté pour "${resume.target_role}" chez ${resume.target_company} ?`)) {
      return;
    }
    setDeleting(true);
    try {
      await onDelete(resumeId);
    } catch (err) {
      console.error("Delete failed:", err);
      setDeleting(false);
    }
  };

  const formattedDate = new Date(resume.updated_at || resume.created_at).toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });

  const allSkills = resume.content?.prioritized_skills?.flatMap((g) => g.skills) || [];

  return (
    <div
      onClick={() => onPreview(resume)}
      className="group bg-[#152238] hover:bg-[#1a2b47] border border-slate-700/60 hover:border-blue-500/50 rounded-xl p-5 shadow-lg hover:shadow-xl transition-all duration-200 cursor-pointer flex flex-col justify-between"
    >
      <div>
        {/* Header Badges */}
        <div className="flex items-center justify-between gap-2 mb-3">
          <span className="inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-md bg-blue-900/40 text-blue-300 border border-blue-700/40 font-medium">
            <FiLayers className="text-xs" />
            {resume.template === "executive_minimalist" ? "Executive Minimalist" : "Sidebar Elegance"}
          </span>
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <FiCalendar />
            <span>{formattedDate}</span>
          </div>
        </div>

        {/* Role & Company */}
        <h3 className="text-lg font-bold text-white group-hover:text-blue-200 transition-colors line-clamp-1 mb-1">
          {resume.target_role}
        </h3>
        <div className="flex items-center gap-1.5 text-sm text-slate-300 font-medium mb-3">
          <FiBriefcase className="text-blue-400" />
          <span>{resume.target_company}</span>
        </div>

        {/* Summary Snippet */}
        {resume.content?.professional_summary && (
          <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed mb-4 bg-slate-900/40 p-2.5 rounded-lg border border-slate-800">
            {resume.content.professional_summary}
          </p>
        )}

        {/* Highlighted Skills */}
        {allSkills.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-4">
            {allSkills.slice(0, 5).map((skill, idx) => (
              <span
                key={idx}
                className="text-[11px] px-2 py-0.5 rounded-md bg-slate-800 text-slate-300 border border-slate-700/70"
              >
                {skill}
              </span>
            ))}
            {allSkills.length > 5 && (
              <span className="text-[11px] px-2 py-0.5 rounded-md bg-slate-800/50 text-slate-400">
                +{allSkills.length - 5}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Action Footer */}
      <div className="flex items-center justify-between pt-4 border-t border-slate-800/80 mt-2">
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onPreview(resume);
            }}
            className="flex items-center gap-1 text-xs font-semibold text-blue-400 hover:text-blue-300 transition-colors"
          >
            <FiEye />
            <span>Aperçu</span>
          </button>

          {onEdit && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onEdit(resume);
              }}
              className="flex items-center gap-1 text-xs text-slate-300 hover:text-white px-2 py-1 rounded-md hover:bg-slate-800/80 transition-colors"
              title="Modifier les textes du CV"
            >
              <FiEdit3 className="text-xs text-amber-400" />
              <span>Éditer</span>
            </button>
          )}

          {onRegenerate && (
            <button
              onClick={handleRegenerateClick}
              disabled={regenerating}
              className="flex items-center gap-1 text-xs text-slate-300 hover:text-white px-2 py-1 rounded-md hover:bg-slate-800/80 disabled:opacity-50 transition-colors"
              title="Régénérer une nouvelle version adaptée"
            >
              <FiRefreshCw className={`text-xs text-emerald-400 ${regenerating ? "animate-spin" : ""}`} />
              <span>{regenerating ? "Génération..." : "Régénérer"}</span>
            </button>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleDirectDownload}
            disabled={downloading}
            className="flex items-center gap-1 text-xs bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white px-3 py-1.5 rounded-lg font-medium shadow-sm transition-colors"
            title="Télécharger directement le PDF A4"
          >
            {downloading ? <FiRefreshCw className="animate-spin" /> : <FiDownload />}
            <span>PDF</span>
          </button>

          <button
            onClick={handleDeleteClick}
            disabled={deleting}
            className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
            title="Supprimer ce CV"
            aria-label="Supprimer ce CV"
          >
            <FiTrash2 />
          </button>
        </div>
      </div>
    </div>
  );
}
