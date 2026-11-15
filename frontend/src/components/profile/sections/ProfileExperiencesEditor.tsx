"use client";

import React from "react";
import { CandidateExperience } from "@/types/coverLetter";
import { FiBriefcase, FiPlus, FiTrash2 } from "react-icons/fi";

interface ProfileExperiencesEditorProps {
  experiences: CandidateExperience[];
  onAdd: () => void;
  onRemove: (index: number) => void;
  onUpdate: (index: number, field: keyof CandidateExperience, value: string) => void;
}

/**
 * Editable list of candidate professional experiences.
 */
export function ProfileExperiencesEditor({
  experiences,
  onAdd,
  onRemove,
  onUpdate,
}: ProfileExperiencesEditorProps) {
  return (
    <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800">
      <div className="flex items-center justify-between mb-3">
        <label className="text-xs font-semibold text-gray-300 uppercase flex items-center">
          <FiBriefcase className="mr-2 text-blue-400" /> Expériences professionnelles ({experiences.length})
        </label>
        <button
          type="button"
          onClick={onAdd}
          className="inline-flex items-center gap-1 text-xs font-medium bg-blue-600/20 text-blue-300 hover:bg-blue-600/30 border border-blue-500/30 px-2.5 py-1 rounded-lg transition-colors cursor-pointer"
        >
          <FiPlus className="w-3.5 h-3.5" />
          <span>Ajouter une expérience</span>
        </button>
      </div>

      <div className="space-y-3 max-h-[380px] overflow-y-auto pr-1.5 custom-scrollbar">
        {experiences.map((exp, idx) => (
          <div key={idx} className="bg-slate-900/90 p-3 rounded-lg border border-slate-800 space-y-2 relative">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wide">
                Expérience #{idx + 1}
              </span>
              <button
                type="button"
                onClick={() => onRemove(idx)}
                className="text-red-400 hover:text-red-300 p-1 rounded hover:bg-red-950/40 transition-colors cursor-pointer"
                title="Supprimer cette expérience"
              >
                <FiTrash2 className="w-3.5 h-3.5" />
              </button>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <div>
                <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Poste / Rôle</label>
                <input
                  type="text"
                  value={exp.role || ""}
                  onChange={(e) => onUpdate(idx, "role", e.target.value)}
                  placeholder="ex: Chef de Projet, Animatrice 2D, Data Engineer"
                  className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Entreprise</label>
                <input
                  type="text"
                  value={exp.company || ""}
                  onChange={(e) => onUpdate(idx, "company", e.target.value)}
                  placeholder="ex: Agence Nile"
                  className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white"
                />
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <div>
                <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Début (ex: 2023-02)</label>
                <input
                  type="text"
                  value={exp.start || ""}
                  onChange={(e) => onUpdate(idx, "start", e.target.value)}
                  placeholder="2023-02"
                  className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Fin (vide = en cours)</label>
                <input
                  type="text"
                  value={exp.end || ""}
                  onChange={(e) => onUpdate(idx, "end", e.target.value)}
                  placeholder="2024-06"
                  className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Localisation</label>
                <input
                  type="text"
                  value={exp.location || ""}
                  onChange={(e) => onUpdate(idx, "location", e.target.value)}
                  placeholder="ex: Lyon, France"
                  className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white"
                />
              </div>
            </div>
            <div>
              <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Outils & compétences (séparés par virgule)</label>
              <input
                type="text"
                value={(exp.stack || []).join(", ")}
                onChange={(e) => onUpdate(idx, "stack", e.target.value)}
                placeholder="Python, Illustrator, Gestion de projet, Anglais courant"
                className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white"
              />
            </div>
            <div>
              <label className="text-[10px] text-slate-400 font-medium block mb-0.5">
                Missions & Réalisations (1 bullet point par ligne)
              </label>
              <textarea
                rows={3}
                value={(exp.missions || []).join("\n")}
                onChange={(e) => onUpdate(idx, "missions", e.target.value)}
                placeholder={"Pilotage d'un projet transverse avec réduction des délais de 30%\nCoordination d'une équipe de 5 personnes\nMise en place d'un nouveau processus qualité"}
                className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white focus:outline-none focus:ring-1 focus:ring-blue-500 custom-scrollbar resize-y"
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
