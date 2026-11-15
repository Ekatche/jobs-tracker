"use client";

import React from "react";
import { CandidateProfile } from "@/types/coverLetter";
import { FiAward, FiGlobe, FiGithub, FiLinkedin, FiMail, FiHeart } from "react-icons/fi";

interface ProfileSummaryViewProps {
  profile: CandidateProfile | null;
  writingStyle: string;
  writingSamples: string;
}

/**
 * Renders the read-only headline, summary, Voice DNA, web links, and languages/interests cards.
 */
export function ProfileSummaryView({
  profile,
  writingStyle,
  writingSamples,
}: ProfileSummaryViewProps) {
  const activeStyle = profile?.writing_style || writingStyle;
  const activeSamples = profile?.writing_samples || writingSamples;

  return (
    <>
      {/* Headline, Summary & Voice DNA */}
      <div className="bg-slate-950/40 p-5 rounded-xl border border-slate-800/80">
        <div className="flex items-center justify-between mb-2.5">
          <h3 className="text-xs uppercase tracking-wider font-semibold text-slate-400 flex items-center gap-1.5">
            <FiAward className="text-blue-400" /> Titre professionnel & Résumé
          </h3>
          {profile?.headline && (
            <span className="text-[11px] font-semibold px-2 py-0.5 rounded-md bg-blue-500/10 text-blue-400 border border-blue-500/20">
              Titre actif
            </span>
          )}
        </div>
        <div className="text-lg font-bold text-white mb-2 tracking-tight">
          {profile?.headline || "Titre professionnel non renseigné"}
        </div>
        <p className="text-slate-300 leading-relaxed whitespace-pre-line text-xs sm:text-sm">
          {profile?.summary || "Aucun résumé professionnel enregistré."}
        </p>

        <div className="mt-3 pt-3 border-t border-slate-800/80">
          <div className="text-[11px] font-semibold text-purple-400 uppercase tracking-wider flex items-center gap-1.5 mb-1.5">
            <span>✍️</span> Style d&apos;écriture (Voice DNA)
          </div>
          <p className="text-slate-300 italic text-xs leading-relaxed whitespace-pre-line min-h-[1.5rem]">
            {activeStyle ? (
              <>&ldquo;{activeStyle}&rdquo;</>
            ) : (
              <span className="text-slate-500 not-italic">
                Non défini — cliquez &ldquo;Modifier manuellement&rdquo; pour décrire votre style d&apos;écriture.
              </span>
            )}
          </p>
          <p className="text-[11px] text-slate-500 mt-1">
            Lettres d&apos;exemple :{" "}
            {activeSamples ? `${activeSamples.length} caractères` : "aucune"}
          </p>
        </div>
      </div>

      {/* Contact & Web Links */}
      <div className="bg-slate-950/40 p-5 rounded-xl border border-slate-800/80">
        <h3 className="text-xs uppercase tracking-wider font-semibold text-slate-400 mb-3.5">
          Coordonnées & Liens web
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {[
            { label: "Site Web", icon: <FiGlobe className="mr-2.5 text-blue-400 shrink-0 w-4 h-4" />, val: profile?.contact?.website },
            { label: "GitHub", icon: <FiGithub className="mr-2.5 text-slate-300 shrink-0 w-4 h-4" />, val: profile?.contact?.github },
            { label: "LinkedIn", icon: <FiLinkedin className="mr-2.5 text-blue-500 shrink-0 w-4 h-4" />, val: profile?.contact?.linkedin },
          ].map((link) => (
            <div key={link.label} className="bg-slate-900/80 p-3 rounded-xl border border-slate-800/90 flex items-center">
              {link.icon}
              <div className="min-w-0">
                <div className="text-[10px] text-slate-400 uppercase font-semibold">{link.label}</div>
                {link.val ? (
                  <a
                    href={link.val.startsWith("http") ? link.val : `https://${link.val}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-blue-400 hover:underline truncate block"
                  >
                    {link.val.replace(/^https?:\/\//, "")}
                  </a>
                ) : (
                  <span className="text-xs text-slate-500 italic">Non renseigné</span>
                )}
              </div>
            </div>
          ))}

          <div className="bg-slate-900/80 p-3 rounded-xl border border-slate-800/90 flex items-center">
            <FiMail className="mr-2.5 text-emerald-400 shrink-0 w-4 h-4" />
            <div className="min-w-0">
              <div className="text-[10px] text-slate-400 uppercase font-semibold">Email</div>
              <span className="text-xs text-slate-200 truncate block">
                {profile?.contact?.email || "Non renseigné"}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Languages & Interests (shown at bottom of view when exported or imported below credentials) */}
    </>
  );
}

export function ProfileLanguagesInterestsView({ profile }: { profile: CandidateProfile | null }) {
  if (
    (!profile?.languages || profile.languages.length === 0) &&
    (!profile?.interests || profile.interests.length === 0)
  ) {
    return null;
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {profile?.languages && profile.languages.length > 0 && (
        <div className="bg-slate-950/40 p-5 rounded-xl border border-slate-800/80">
          <h3 className="text-xs uppercase tracking-wider font-semibold text-slate-400 mb-3 flex items-center">
            <FiGlobe className="mr-2 text-cyan-400" /> Langues ({profile.languages.length})
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {profile.languages.map((lang, idx) => (
              <span
                key={idx}
                className="px-3 py-1 rounded-lg text-xs bg-slate-900 text-cyan-300 border border-cyan-800/40 font-medium"
              >
                {lang}
              </span>
            ))}
          </div>
        </div>
      )}

      {profile?.interests && profile.interests.length > 0 && (
        <div className="bg-slate-950/40 p-5 rounded-xl border border-slate-800/80">
          <h3 className="text-xs uppercase tracking-wider font-semibold text-slate-400 mb-3 flex items-center">
            <FiHeart className="mr-2 text-rose-400" /> Centres d&apos;intérêt ({profile.interests.length})
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {profile.interests.map((item, idx) => (
              <span
                key={idx}
                className="px-3 py-1 rounded-lg text-xs bg-slate-900 text-rose-300 border border-rose-800/40 font-medium"
              >
                {item}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
