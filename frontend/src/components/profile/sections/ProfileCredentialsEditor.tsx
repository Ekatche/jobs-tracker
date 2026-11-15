"use client";

import React from "react";
import { CandidateEducation, CandidateCertification } from "@/types/coverLetter";
import { FiBook, FiAward, FiPlus, FiTrash2 } from "react-icons/fi";

interface ProfileCredentialsEditorProps {
  education: CandidateEducation[];
  certifications: CandidateCertification[];
  onAddEducation: () => void;
  onRemoveEducation: (index: number) => void;
  onUpdateEducation: (index: number, field: keyof CandidateEducation, value: string) => void;
  onAddCertification: () => void;
  onRemoveCertification: (index: number) => void;
  onUpdateCertification: (
    index: number,
    field: keyof CandidateCertification,
    value: string
  ) => void;
}

/**
 * Editable lists for education entries and professional certifications.
 */
export function ProfileCredentialsEditor({
  education,
  certifications,
  onAddEducation,
  onRemoveEducation,
  onUpdateEducation,
  onAddCertification,
  onRemoveCertification,
  onUpdateCertification,
}: ProfileCredentialsEditorProps) {
  return (
    <>
      <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800">
        <div className="flex items-center justify-between mb-3">
          <label className="text-xs font-semibold text-gray-300 uppercase flex items-center">
            <FiBook className="mr-2 text-blue-400" /> Formations & Diplômes ({education.length})
          </label>
          <button
            type="button"
            onClick={onAddEducation}
            className="inline-flex items-center gap-1 text-xs font-medium bg-blue-600/20 text-blue-300 hover:bg-blue-600/30 border border-blue-500/30 px-2.5 py-1 rounded-lg transition-colors cursor-pointer"
          >
            <FiPlus className="w-3.5 h-3.5" />
            <span>Ajouter une formation</span>
          </button>
        </div>

        <div className="space-y-3 max-h-[380px] overflow-y-auto pr-1.5 custom-scrollbar">
          {education.map((edu, idx) => (
            <div key={idx} className="bg-slate-900/90 p-3 rounded-lg border border-slate-800 space-y-2 relative">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wide">
                  Formation #{idx + 1}
                </span>
                <button
                  type="button"
                  onClick={() => onRemoveEducation(idx)}
                  className="text-red-400 hover:text-red-300 p-1 rounded hover:bg-red-950/40 transition-colors cursor-pointer"
                  title="Supprimer cette formation"
                >
                  <FiTrash2 className="w-3.5 h-3.5" />
                </button>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <div>
                  <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Diplôme / Formation</label>
                  <input
                    type="text"
                    value={edu.degree || ""}
                    onChange={(e) => onUpdateEducation(idx, "degree", e.target.value)}
                    placeholder="ex: DEUST AGAPSC, Master Informatique"
                    className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-400 font-medium block mb-0.5">École / Université</label>
                  <input
                    type="text"
                    value={edu.school || ""}
                    onChange={(e) => onUpdateEducation(idx, "school", e.target.value)}
                    placeholder="ex: Université de Lyon 1"
                    className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white"
                  />
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <div>
                  <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Période</label>
                  <input
                    type="text"
                    value={edu.years || ""}
                    onChange={(e) => onUpdateEducation(idx, "years", e.target.value)}
                    placeholder="ex: septembre 2016 - juin 2018"
                    className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Spécialités / Sujets (séparés par virgule)</label>
                  <input
                    type="text"
                    value={(edu.topics || []).join(", ")}
                    onChange={(e) => onUpdateEducation(idx, "topics", e.target.value)}
                    placeholder="ex: Parcours Animation et PSC1"
                    className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white"
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800">
        <div className="flex items-center justify-between mb-3">
          <label className="text-xs font-semibold text-gray-300 uppercase flex items-center">
            <FiAward className="mr-2 text-emerald-400" /> Certifications ({certifications.length})
          </label>
          <button
            type="button"
            onClick={onAddCertification}
            className="inline-flex items-center gap-1 text-xs font-medium bg-blue-600/20 text-blue-300 hover:bg-blue-600/30 border border-blue-500/30 px-2.5 py-1 rounded-lg transition-colors cursor-pointer"
          >
            <FiPlus className="w-3.5 h-3.5" />
            <span>Ajouter une certification</span>
          </button>
        </div>

        <div className="space-y-3 max-h-[380px] overflow-y-auto pr-1.5 custom-scrollbar">
          {certifications.map((cert, idx) => (
            <div key={idx} className="bg-slate-900/90 p-3 rounded-lg border border-slate-800 space-y-2 relative">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wide">
                  Certification #{idx + 1}
                </span>
                <button
                  type="button"
                  onClick={() => onRemoveCertification(idx)}
                  className="text-red-400 hover:text-red-300 p-1 rounded hover:bg-red-950/40 transition-colors cursor-pointer"
                  title="Supprimer cette certification"
                >
                  <FiTrash2 className="w-3.5 h-3.5" />
                </button>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <div>
                  <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Nom</label>
                  <input
                    type="text"
                    value={cert.name || ""}
                    onChange={(e) => onUpdateCertification(idx, "name", e.target.value)}
                    placeholder="ex: BAFA, AWS Certified Solutions Architect"
                    className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Organisme</label>
                  <input
                    type="text"
                    value={cert.issuer || ""}
                    onChange={(e) => onUpdateCertification(idx, "issuer", e.target.value)}
                    placeholder="ex: Familles Rurales Rhône Alpes"
                    className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white"
                  />
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <div>
                  <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Année</label>
                  <input
                    type="text"
                    value={cert.year || ""}
                    onChange={(e) => onUpdateCertification(idx, "year", e.target.value)}
                    placeholder="ex: 2015"
                    className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Détails (séparés par virgule)</label>
                  <input
                    type="text"
                    value={(cert.topics || []).join(", ")}
                    onChange={(e) => onUpdateCertification(idx, "topics", e.target.value)}
                    placeholder="ex: Secourisme, Encadrement de groupe"
                    className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white"
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
