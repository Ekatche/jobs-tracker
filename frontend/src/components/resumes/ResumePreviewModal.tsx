"use client";

import { useEffect, useState } from "react";
import { FiX, FiDownload, FiCheck, FiRefreshCw, FiImage, FiFileText } from "react-icons/fi";
import { TailoredResume } from "@/types/resume";
import { resumeApi } from "@/lib/api";

interface ResumePreviewModalProps {
  resume: TailoredResume | null;
  isOpen: boolean;
  onClose: () => void;
  onUpdateTemplate?: (resumeId: string, template: string, withPhoto: boolean) => Promise<void>;
}

export default function ResumePreviewModal({
  resume,
  isOpen,
  onClose,
  onUpdateTemplate,
}: ResumePreviewModalProps) {
  const [selectedTemplate, setSelectedTemplate] = useState<string>("sidebar_elegance");
  const [withPhoto, setWithPhoto] = useState<boolean>(false);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [loadingPdf, setLoadingPdf] = useState<boolean>(false);
  const [downloading, setDownloading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (resume) {
      setSelectedTemplate(resume.template || "sidebar_elegance");
      setWithPhoto(resume.with_photo || false);
    }
  }, [resume]);

  // Re-fetch PDF blob URL when template or withPhoto changes
  useEffect(() => {
    let activeUrl: string | null = null;

    const loadPdf = async () => {
      if (!resume || !isOpen) return;
      const resumeId = resume.id || resume._id;
      if (!resumeId) return;

      setLoadingPdf(true);
      setError(null);
      try {
        const url = await resumeApi.getPdfBlobUrl(resumeId, selectedTemplate, withPhoto);
        activeUrl = url;
        setPdfUrl(url);
      } catch (err: unknown) {
        console.error("Failed to load CV PDF preview:", err);
        setError("Erreur lors de la génération de l'aperçu PDF.");
      } finally {
        setLoadingPdf(false);
      }
    };

    loadPdf();

    return () => {
      if (activeUrl) {
        window.URL.revokeObjectURL(activeUrl);
      }
    };
  }, [resume, selectedTemplate, withPhoto, isOpen]);

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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
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
              Rendu vectoriel A4 ultra-haute fidélité certifié ATS & recruteurs européens
            </p>
          </div>

          {/* Controls */}
          <div className="flex items-center gap-3">
            {/* Template Selector */}
            <div className="flex bg-slate-900/60 p-1 rounded-lg border border-slate-700/60 text-xs">
              <button
                onClick={() => handleTemplateChange("sidebar_elegance")}
                className={`px-3 py-1.5 rounded-md font-medium transition-all ${
                  selectedTemplate === "sidebar_elegance"
                    ? "bg-blue-600 text-white shadow-sm"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Sidebar Elegance
              </button>
              <button
                onClick={() => handleTemplateChange("executive_minimalist")}
                className={`px-3 py-1.5 rounded-md font-medium transition-all ${
                  selectedTemplate === "executive_minimalist"
                    ? "bg-blue-600 text-white shadow-sm"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Executive Minimalist
              </button>
            </div>

            {/* Photo Toggle */}
            <button
              onClick={handlePhotoToggle}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
                withPhoto
                  ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-300"
                  : "bg-slate-800/80 border-slate-700 text-slate-400 hover:text-slate-200"
              }`}
              title="Afficher ou masquer la photo sur le CV"
            >
              <FiImage />
              <span>Photo: {withPhoto ? "Oui" : "Non"}</span>
            </button>

            {/* Download Button */}
            <button
              onClick={handleDownload}
              disabled={downloading || loadingPdf}
              className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white px-4 py-1.5 rounded-lg text-xs font-semibold shadow-md shadow-blue-500/20 transition-colors"
            >
              {downloading ? <FiRefreshCw className="animate-spin" /> : <FiDownload />}
              <span>Télécharger PDF</span>
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

        {/* PDF Viewer Body */}
        <div className="flex-1 bg-slate-950/60 p-4 overflow-hidden relative flex items-center justify-center">
          {loadingPdf && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-[#131d31]/80 z-10 gap-3">
              <FiRefreshCw className="animate-spin text-3xl text-blue-400" />
              <p className="text-sm text-slate-300">Génération du rendu PDF A4 vectoriel en cours...</p>
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
      </div>
    </div>
  );
}
