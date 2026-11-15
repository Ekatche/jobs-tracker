"use client";

import React from "react";
import { CandidateProfile } from "@/types/coverLetter";
import { CollapsibleSection } from "./CollapsibleSection";
import { FiBook, FiAward, FiCalendar, FiAlertTriangle } from "react-icons/fi";

/**
 * Renders read-only education history and certifications with duplicate indicators.
 */
export function ProfileCredentialsView({ profile }: { profile: CandidateProfile | null }) {
  return (
    <>
      {profile?.education && profile.education.length > 0 && (
        <CollapsibleSection
          title={`Formations & Diplômes (${profile.education.length})`}
          icon={<FiBook className="mr-2 text-blue-400" />}
        >
          <div className="max-h-[460px] overflow-y-auto pr-1.5 custom-scrollbar">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
              {profile.education.map((edu, idx, educationList) => {
                const eduKey = `${edu.school.trim().toLowerCase()}|${edu.degree.trim().toLowerCase()}`;
                const isDuplicate =
                  educationList.findIndex(
                    (e2) =>
                      `${e2.school.trim().toLowerCase()}|${e2.degree.trim().toLowerCase()}` === eduKey
                  ) !== idx;
                return (
                  <div
                    key={idx}
                    className="bg-slate-900/80 p-4 rounded-xl border border-slate-800/90 hover:border-slate-700/80 transition-all flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex items-start justify-between gap-2">
                        <h4 className="font-bold text-white text-sm sm:text-base leading-snug flex items-center gap-2">
                          {edu.degree}
                          {isDuplicate && (
                            <span className="inline-flex items-center text-[10px] font-semibold text-amber-300 bg-amber-500/10 border border-amber-500/30 px-1.5 py-0.5 rounded-md gap-1">
                              <FiAlertTriangle className="w-3 h-3" /> Doublon à vérifier
                            </span>
                          )}
                        </h4>
                        {edu.years && (
                          <span className="inline-flex items-center text-[11px] font-semibold text-slate-300 bg-slate-800/90 border border-slate-700/60 px-2.5 py-0.5 rounded-lg shrink-0 w-fit">
                            <FiCalendar className="mr-1 text-blue-400" />
                            {edu.years}
                          </span>
                        )}
                      </div>
                      <p className="text-blue-400 text-xs font-semibold mt-1">{edu.school}</p>
                    </div>

                    {edu.topics && edu.topics.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-3 pt-3 border-t border-slate-800/60">
                        {edu.topics.map((t, tIdx) => (
                          <span
                            key={tIdx}
                            className="text-[10px] bg-slate-800/70 text-slate-300 border border-slate-700/40 px-2 py-0.5 rounded-md font-medium"
                          >
                            {t}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </CollapsibleSection>
      )}

      {profile?.certifications && profile.certifications.length > 0 && (
        <CollapsibleSection
          title={`Certifications (${profile.certifications.length})`}
          icon={<FiAward className="mr-2 text-emerald-400" />}
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
            {profile.certifications.map((cert, idx, certList) => {
              const certKey = `${cert.name.trim().toLowerCase()}|${cert.issuer.trim().toLowerCase()}`;
              const isDuplicate =
                certList.findIndex(
                  (c2) =>
                    `${c2.name.trim().toLowerCase()}|${c2.issuer.trim().toLowerCase()}` === certKey
                ) !== idx;
              return (
                <div
                  key={idx}
                  className="bg-slate-900/80 p-3.5 rounded-xl border border-slate-800/90 hover:border-slate-700/80 transition-all"
                >
                  <h4 className="font-bold text-white text-xs sm:text-sm flex items-center gap-1.5 flex-wrap">
                    {cert.name}
                    {isDuplicate && (
                      <span className="inline-flex items-center text-[10px] font-semibold text-amber-300 bg-amber-500/10 border border-amber-500/30 px-1.5 py-0.5 rounded-md gap-1">
                        <FiAlertTriangle className="w-3 h-3" /> Doublon à vérifier
                      </span>
                    )}
                  </h4>
                  <p className="text-emerald-400 text-xs mt-1">{cert.issuer}</p>
                  {cert.year && (
                    <span className="text-[10px] text-slate-400 mt-2 block">{cert.year}</span>
                  )}
                </div>
              );
            })}
          </div>
        </CollapsibleSection>
      )}
    </>
  );
}
