"use client";

import React, { useState, useRef } from "react";
import {
  FiUploadCloud,
  FiFileText,
  FiCheckCircle,
  FiAlertCircle,
  FiRefreshCw,
  FiCpu,
} from "react-icons/fi";
import { coverLetterApi } from "@/lib/api";
import { CandidateProfile } from "@/types/coverLetter";

interface CvDropzoneProps {
  onProfileUpdated: (updatedProfile: CandidateProfile) => void;
  hasCvSource?: boolean;
}

export default function CvDropzone({
  onProfileUpdated,
  hasCvSource = false,
}: CvDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadStep, setUploadStep] = useState<string>("");
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFile = async (file: File) => {
    if (!file) return;

    if (file.type !== "application/pdf" && !file.name.endsWith(".pdf")) {
      setUploadError("Seuls les fichiers PDF sont acceptés pour l'analyse de CV.");
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      setUploadError("Le fichier dépasse la taille maximale autorisée (10 Mo).");
      return;
    }

    setIsUploading(true);
    setUploadError(null);
    setUploadSuccess(null);
    setUploadStep("Lecture et extraction du texte du PDF...");

    try {
      setTimeout(() => {
        setUploadStep("Analyse et structuration des expériences par l'IA...");
      }, 1200);

      const updatedProfile = await coverLetterApi.importCv(file);

      const expCount = updatedProfile.experiences?.length || 0;
      const skillsCount = updatedProfile.skills
        ? Object.values(updatedProfile.skills).flat().length
        : 0;

      setUploadStep("");
      setUploadSuccess(
        `CV « ${file.name} » analysé avec succès ! ${expCount} expérience(s) et ${skillsCount} compétence(s) extraites.`
      );
      onProfileUpdated(updatedProfile);

      setTimeout(() => {
        setUploadSuccess(null);
      }, 6000);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Échec de l'analyse automatique du CV.";
      setUploadError(msg);
    } finally {
      setIsUploading(false);
      setUploadStep("");
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      handleFile(file);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFile(e.target.files[0]);
    }
  };

  return (
    <div className="bg-slate-900/70 backdrop-blur-md rounded-2xl border border-slate-800 p-6 shadow-xl mb-8">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-5">
        <div className="flex items-start gap-3">
          <div className="p-2.5 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-400 shrink-0">
            <FiUploadCloud className="w-5 h-5" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2.5">
              <h2 className="text-lg font-bold text-white">
                Chargement du CV & Analyse Automatique
              </h2>
              {hasCvSource ? (
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-950/80 text-emerald-300 border border-emerald-700/50">
                  <FiCheckCircle className="mr-1 text-emerald-400" /> CV IA Actif
                </span>
              ) : (
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-950/80 text-amber-300 border border-amber-700/50">
                  <FiAlertCircle className="mr-1 text-amber-400" /> En attente de CV
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Déposez votre CV au format PDF. Notre moteur IA extrait automatiquement vos expériences,
              projets et compétences techniques.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={isUploading}
          className="self-start md:self-auto inline-flex items-center px-4 py-2.5 rounded-xl text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-500/20 transition-all disabled:opacity-50 shrink-0"
        >
          <FiUploadCloud className="mr-1.5 w-4 h-4" />
          {hasCvSource ? "Mettre à jour le CV (PDF)" : "Sélectionner un fichier"}
        </button>
      </div>

      <input
        type="file"
        accept="application/pdf"
        ref={fileInputRef}
        onChange={handleFileInputChange}
        className="hidden"
      />

      {/* Zone de Drop */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !isUploading && fileInputRef.current?.click()}
        className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-all cursor-pointer ${
          isDragging
            ? "border-blue-400 bg-blue-500/15 scale-[1.01]"
            : "border-slate-700/80 hover:border-blue-500/50 bg-slate-950/40 hover:bg-slate-900/40"
        } ${isUploading ? "pointer-events-none opacity-80" : ""}`}
      >
        {isUploading ? (
          <div className="flex flex-col items-center justify-center py-4 space-y-3">
            <div className="relative">
              <div className="w-12 h-12 rounded-full border-2 border-blue-500/30 border-t-blue-400 animate-spin"></div>
              <FiCpu className="absolute inset-0 m-auto w-5 h-5 text-blue-400 animate-pulse" />
            </div>
            <div className="text-sm font-medium text-white">{uploadStep}</div>
            <p className="text-xs text-slate-400 max-w-md">
              Traitement par les agents LLM (normalisation des dates, déduplication et mapping de
              la stack technique).
            </p>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-2 space-y-2.5">
            <div className="w-12 h-12 rounded-2xl bg-blue-600/10 border border-blue-500/20 flex items-center justify-center text-blue-400 shadow-inner">
              <FiUploadCloud className="w-6 h-6" />
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-200">
                Glissez-déposez votre CV ici, ou{" "}
                <span className="text-blue-400 hover:underline">parcourez vos fichiers</span>
              </p>
              <p className="text-xs text-slate-500 mt-0.5">
                Format PDF uniquement • Taille max 10 Mo • Vos données restent privées
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Messages de feedback */}
      {uploadSuccess && (
        <div className="mt-4 p-3.5 rounded-xl bg-emerald-950/50 border border-emerald-600/40 text-emerald-200 text-xs flex items-center gap-2.5 shadow-md">
          <FiCheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
          <span className="flex-1">{uploadSuccess}</span>
        </div>
      )}

      {uploadError && (
        <div className="mt-4 p-3.5 rounded-xl bg-red-950/50 border border-red-600/40 text-red-200 text-xs flex items-center gap-2.5 shadow-md">
          <FiAlertCircle className="w-4 h-4 text-red-400 shrink-0" />
          <span className="flex-1">{uploadError}</span>
        </div>
      )}
    </div>
  );
}
