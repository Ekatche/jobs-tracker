"use client";

import React from "react";
import { CandidateProfile, CandidateConflict } from "@/types/coverLetter";
import { CollapsibleSection } from "./CollapsibleSection";
import { formatPeriod } from "@/lib/profileFormatters";
import {
  FiBriefcase,
  FiCode,
  FiCalendar,
  FiAlertCircle,
  FiX,
  FiEye,
} from "react-icons/fi";

interface ProfileWorkViewProps {
  profile: CandidateProfile | null;
  dismissedConflicts: boolean;
  onSetDismissedConflicts: (dismissed: boolean) => void;
}

/**
 * Renders read-only structured skills and experiences (with source conflicts).
 */
export function ProfileWorkView({
  profile,
  dismissedConflicts,
  onSetDismissedConflicts,
}: ProfileWorkViewProps) {
  const nonEmptySkills = Object.entries(profile?.skills || {}).filter(
    ([, items]) => items && items.length > 0
  );

  return (
    <>
      {nonEmptySkills.length > 0 && (
        <CollapsibleSection
          title="Compétences structurées"
          icon={<FiCode className="mr-2 text-blue-400" />}
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {nonEmptySkills.map(([category, items]) => (
              <div
                key={category}
                className="bg-slate-900/80 p-3.5 rounded-xl border border-slate-800/90"
              >
                <span className="text-xs font-bold uppercase tracking-wider text-blue-400">
                  {category.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                </span>
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {items.map((skill, i) => (
                    <span
                      key={i}
                      className="px-2.5 py-0.5 rounded-lg text-xs bg-slate-800 text-slate-200 border border-slate-700/70 font-medium"
                    >
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </CollapsibleSection>
      )}

      {profile?.experiences && profile.experiences.length > 0 && (
        <CollapsibleSection
          title={`Expériences clés (${profile.experiences.length})`}
          icon={<FiBriefcase className="mr-2 text-blue-400" />}
          defaultOpen
        >
          {profile.conflicts && profile.conflicts.length > 0 && !dismissedConflicts && (
            <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3.5 text-xs text-amber-200 mb-4 transition-all">
              <div className="flex items-center justify-between mb-2">
                <p className="font-semibold flex items-center gap-1.5 text-amber-300">
                  <FiAlertCircle className="w-4 h-4 text-amber-400 shrink-0" />
                  Divergences détectées entre vos sources ({profile.conflicts.length})
                </p>
                <button
                  type="button"
                  onClick={() => onSetDismissedConflicts(true)}
                  className="text-amber-400 hover:text-amber-100 hover:bg-amber-500/20 px-2 py-0.5 rounded-md transition-colors flex items-center gap-1 text-[11px] font-medium"
                  title="Masquer ces divergences de la vue"
                >
                  <span>Masquer</span>
                  <FiX className="w-3.5 h-3.5" />
                </button>
              </div>
              <ul className="space-y-1.5 pl-1">
                {profile.conflicts.map((c: CandidateConflict, i) => (
                  <li key={i} className="text-slate-300">
                    <span className="font-medium text-amber-300">{c.company}</span> — {c.field} : «{" "}
                    <span className="text-white">{String(c.kept)}</span> » retenu depuis{" "}
                    <span className="text-blue-300 font-mono text-[11px]">{c.kept_source}</span>, «{" "}
                    <span className="line-through text-slate-400">{String(c.discarded)}</span> » écarté depuis{" "}
                    <span className="text-slate-400 font-mono text-[11px]">{c.discarded_source}</span>.
                  </li>
                ))}
              </ul>
            </div>
          )}

          {profile.conflicts && profile.conflicts.length > 0 && dismissedConflicts && (
            <div className="flex justify-end mb-3">
              <button
                type="button"
                onClick={() => onSetDismissedConflicts(false)}
                className="text-[11px] text-amber-400/80 hover:text-amber-300 hover:underline flex items-center gap-1.5 py-1 px-2 rounded hover:bg-amber-500/10 transition-colors"
              >
                <FiEye className="w-3.5 h-3.5" />
                <span>Afficher les {profile.conflicts.length} divergences masquées</span>
              </button>
            </div>
          )}

          <div className="max-h-[560px] overflow-y-auto pr-1.5 custom-scrollbar space-y-3.5">
            {profile.experiences.map((exp, idx) => (
              <div
                key={idx}
                className="bg-slate-900/80 p-4 rounded-xl border border-slate-800/90 hover:border-slate-700/80 transition-all"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <span className="font-bold text-white text-sm sm:text-base">{exp.role}</span>
                    <span className="text-blue-400 mx-1.5 font-semibold">@</span>
                    <span className="text-slate-200 font-semibold">{exp.company}</span>
                    {exp.location && (
                      <span className="text-xs text-slate-400 ml-2">({exp.location})</span>
                    )}
                  </div>
                  <span className="inline-flex items-center text-xs font-semibold text-slate-300 bg-slate-800/90 border border-slate-700/60 px-2.5 py-1 rounded-lg shrink-0 w-fit">
                    <FiCalendar className="mr-1.5 text-blue-400" />
                    {formatPeriod(exp.start, exp.end)}
                  </span>
                </div>

                {exp.missions && exp.missions.length > 0 && (
                  <ul className="mt-3 space-y-1.5 text-xs text-slate-300">
                    {exp.missions.map((m, mIdx) => (
                      <li key={mIdx} className="flex items-start gap-2">
                        <span className="text-blue-400 mt-1 leading-none">•</span>
                        <span className="leading-relaxed">{m}</span>
                      </li>
                    ))}
                  </ul>
                )}

                <div className="flex flex-wrap items-center gap-1.5 mt-3 pt-3 border-t border-slate-800/60">
                  {exp.stack && exp.stack.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {exp.stack.map((s, sIdx) => (
                        <span
                          key={sIdx}
                          className="text-[10px] bg-blue-950/60 text-blue-300 border border-blue-800/40 px-2 py-0.5 rounded-md font-medium"
                        >
                          {s}
                        </span>
                      ))}
                    </div>
                  )}
                  {exp.sources && exp.sources.length > 0 && (
                    <div className="flex flex-wrap gap-1 ml-auto">
                      {exp.sources.map((s, sIdx) => (
                        <span
                          key={sIdx}
                          className="text-[10px] bg-emerald-950/60 text-emerald-300 border border-emerald-800/40 px-2 py-0.5 rounded-md font-medium"
                        >
                          {s}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </CollapsibleSection>
      )}
    </>
  );
}
