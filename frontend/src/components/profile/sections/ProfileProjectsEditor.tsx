"use client";

import React from "react";
import { CandidateProject } from "@/types/coverLetter";
import { projectContextLabel } from "@/lib/profileFormatters";
import { FiLayers, FiPlus, FiTrash2 } from "react-icons/fi";

interface ProfileProjectsEditorProps {
  projects: CandidateProject[];
  onAdd: () => void;
  onRemove: (index: number) => void;
  onUpdate: (index: number, field: keyof CandidateProject, value: string) => void;
}

/**
 * Editable list of candidate projects and achievements.
 */
export function ProfileProjectsEditor({
  projects,
  onAdd,
  onRemove,
  onUpdate,
}: ProfileProjectsEditorProps) {
  return (
    <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800">
      <div className="flex items-center justify-between mb-3">
        <label className="text-xs font-semibold text-gray-300 uppercase flex items-center">
          <FiLayers className="mr-2 text-blue-400" /> Projets & Réalisations ({projects.length})
        </label>
        <button
          type="button"
          onClick={onAdd}
          className="inline-flex items-center gap-1 text-xs font-medium bg-blue-600/20 text-blue-300 hover:bg-blue-600/30 border border-blue-500/30 px-2.5 py-1 rounded-lg transition-colors cursor-pointer"
        >
          <FiPlus className="w-3.5 h-3.5" />
          <span>Ajouter un projet</span>
        </button>
      </div>

      <div className="space-y-3 max-h-[380px] overflow-y-auto pr-1.5 custom-scrollbar">
        {projects.map((proj, idx) => (
          <div key={idx} className="bg-slate-900/90 p-3 rounded-lg border border-slate-800 space-y-2 relative">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wide">
                Projet #{idx + 1}
              </span>
              <button
                type="button"
                onClick={() => onRemove(idx)}
                className="text-red-400 hover:text-red-300 p-1 rounded hover:bg-red-950/40 transition-colors cursor-pointer"
                title="Supprimer ce projet"
              >
                <FiTrash2 className="w-3.5 h-3.5" />
              </button>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <div>
                <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Nom du projet</label>
                <input
                  type="text"
                  value={proj.name || ""}
                  onChange={(e) => onUpdate(idx, "name", e.target.value)}
                  placeholder="ex: WideDocs"
                  className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Contexte</label>
                <input
                  type="text"
                  value={projectContextLabel(proj.context)}
                  onChange={(e) => onUpdate(idx, "context", e.target.value)}
                  placeholder="ex: Client, Perso, Stage, Associatif"
                  className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white"
                />
              </div>
            </div>
            <div>
              <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Description</label>
              <textarea
                rows={2}
                value={proj.description || ""}
                onChange={(e) => onUpdate(idx, "description", e.target.value)}
                placeholder="Description concise du projet et des défis relevés..."
                className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white"
              />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <div>
                <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Lien / Preuve (site, article, portfolio...)</label>
                <input
                  type="text"
                  value={proj.url || ""}
                  onChange={(e) => onUpdate(idx, "url", e.target.value)}
                  placeholder="https://..."
                  className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Code source (optionnel, si applicable)</label>
                <input
                  type="text"
                  value={proj.repo || ""}
                  onChange={(e) => onUpdate(idx, "repo", e.target.value)}
                  placeholder="https://github.com/..."
                  className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white"
                />
              </div>
            </div>
            <div>
              <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Outils & compétences (séparés par virgule)</label>
              <input
                type="text"
                value={(proj.stack || []).join(", ")}
                onChange={(e) => onUpdate(idx, "stack", e.target.value)}
                placeholder="React, FastAPI, PostgreSQL / ou : Storyboard, Animation 2D, After Effects"
                className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white"
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
