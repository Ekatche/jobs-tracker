"use client";

import React from "react";
import { CandidateProfile } from "@/types/coverLetter";
import { CollapsibleSection } from "./CollapsibleSection";
import { isLikelyBrokenLink, projectContextLabel } from "@/lib/profileFormatters";
import { FiLayers, FiAlertTriangle, FiExternalLink, FiGithub } from "react-icons/fi";

/**
 * Renders read-only candidate personal projects and achievements grid.
 */
export function ProfileProjectsView({ profile }: { profile: CandidateProfile | null }) {
  if (!profile?.projects || profile.projects.length === 0) return null;

  return (
    <CollapsibleSection
      title={`Projets personnels & réalisations (${profile.projects.length})`}
      icon={<FiLayers className="mr-2 text-blue-400" />}
      badge={
        profile.projects.length > 4 ? (
          <span className="text-[10px] text-slate-500 italic">Défilement actif</span>
        ) : undefined
      }
    >
      <div className="max-h-[520px] overflow-y-auto pr-1.5 custom-scrollbar">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
          {profile.projects.map((proj, idx) => (
            <div
              key={idx}
              className="bg-slate-900/80 p-4 rounded-xl border border-slate-800/90 flex flex-col justify-between hover:border-slate-700/80 transition-all"
            >
              <div>
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <div className="font-bold text-white text-sm flex items-center gap-2">
                    <span>{proj.name}</span>
                    {proj.context && (
                      <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                        {projectContextLabel(proj.context)}
                      </span>
                    )}
                  </div>
                  {proj.sources && proj.sources.length > 0 && (
                    <div className="flex gap-1">
                      {proj.sources.map((s, sIdx) => (
                        <span
                          key={sIdx}
                          className="text-[9px] bg-emerald-950/60 text-emerald-300 border border-emerald-800/40 px-1.5 py-0.5 rounded"
                        >
                          {s}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <p className="text-xs text-slate-300 leading-relaxed mt-1">{proj.description}</p>
                {proj.highlights && proj.highlights.length > 0 && (
                  <ul className="mt-2 space-y-1 text-xs text-slate-400">
                    {proj.highlights.map((h, hIdx) => (
                      <li key={hIdx} className="flex items-start gap-1.5">
                        <span className="text-blue-400 mt-0.5">•</span>
                        <span>{h}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="mt-4 pt-3 border-t border-slate-800/60 space-y-3">
                {proj.stack && proj.stack.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {proj.stack.map((s, sIdx) => (
                      <span
                        key={sIdx}
                        className="text-[10px] bg-blue-950/60 text-blue-300 border border-blue-800/40 px-2 py-0.5 rounded-md font-medium"
                      >
                        {s}
                      </span>
                    ))}
                  </div>
                )}
                <div className="flex flex-wrap items-center gap-2">
                  {proj.url &&
                    (isLikelyBrokenLink(proj.url) ? (
                      <span
                        className="inline-flex items-center text-xs font-semibold text-amber-400 gap-1"
                        title={proj.url}
                      >
                        <FiAlertTriangle className="w-3.5 h-3.5" />
                        <span>Lien à vérifier</span>
                      </span>
                    ) : (
                      <a
                        href={proj.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center text-xs font-semibold text-blue-400 hover:text-blue-300 hover:underline gap-1"
                      >
                        <span>Consulter</span>
                        <FiExternalLink className="w-3.5 h-3.5" />
                      </a>
                    ))}
                  {proj.repo &&
                    (isLikelyBrokenLink(proj.repo) ? (
                      <span
                        className="inline-flex items-center text-xs font-semibold text-amber-400 gap-1 ml-auto"
                        title={proj.repo}
                      >
                        <FiAlertTriangle className="w-3.5 h-3.5" />
                        <span>Lien à vérifier</span>
                      </span>
                    ) : (
                      <a
                        href={proj.repo}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center text-xs font-semibold text-slate-300 hover:text-white hover:underline gap-1 ml-auto"
                      >
                        <FiGithub className="w-3.5 h-3.5" />
                        <span>Code</span>
                      </a>
                    ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </CollapsibleSection>
  );
}
