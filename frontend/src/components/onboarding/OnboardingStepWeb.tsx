"use client";

import React from "react";
import { CandidateProfile } from "@/types/coverLetter";
import {
  FiGlobe,
  FiGithub,
  FiArrowRight,
  FiArrowLeft,
  FiCheckCircle,
  FiAlertCircle,
  FiCode,
  FiZap,
  FiCheck,
  FiCompass,
} from "react-icons/fi";

interface OnboardingStepWebProps {
  profile: CandidateProfile | null;
  githubUrl: string;
  websiteUrl: string;
  isImportingGithub: boolean;
  isImportingWebsite: boolean;
  isCompleting: boolean;
  sourceMessage: { type: "success" | "error"; text: string } | null;
  hasCv: boolean;
  hasGithub: boolean;
  hasWebsite: boolean;
  experiencesCount: number;
  onGithubUrlChange: (v: string) => void;
  onWebsiteUrlChange: (v: string) => void;
  onImportGithub: (e: React.FormEvent) => void;
  onImportWebsite: (e: React.FormEvent) => void;
  onBack: () => void;
  onComplete: () => void;
}

export default function OnboardingStepWeb({
  profile,
  githubUrl,
  websiteUrl,
  isImportingGithub,
  isImportingWebsite,
  isCompleting,
  sourceMessage,
  hasCv,
  hasGithub,
  hasWebsite,
  experiencesCount,
  onGithubUrlChange,
  onWebsiteUrlChange,
  onImportGithub,
  onImportWebsite,
  onBack,
  onComplete,
}: OnboardingStepWebProps) {
  return (
    <div className="space-y-6">
      <div className="bg-blue-night-lighter/50 border border-gray-800 rounded-xl p-5 sm:p-6 shadow-lg">
        <div className="mb-6 pb-4 border-b border-gray-800">
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <FiGlobe className="text-blue-400" />
            <span>Présence Web &amp; Finalisation</span>
          </h2>
          <p className="text-sm text-gray-400 mt-1">
            Connectez vos profils publics pour consolider vos réalisations concrètes.
          </p>
        </div>

        {sourceMessage && (
          <div
            className={`p-3 rounded-lg text-sm mb-4 flex items-center gap-2 ${
              sourceMessage.type === "success"
                ? "bg-emerald-900/30 border border-emerald-500/40 text-emerald-200"
                : "bg-red-900/30 border border-red-500/40 text-red-200"
            }`}
          >
            {sourceMessage.type === "success" ? (
              <FiCheckCircle className="text-emerald-400 shrink-0" />
            ) : (
              <FiAlertCircle className="text-red-400 shrink-0" />
            )}
            <span>{sourceMessage.text}</span>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <form
            onSubmit={onImportGithub}
            className="bg-blue-night/60 border border-gray-800 rounded-xl p-4 flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2 font-semibold text-white text-sm">
                  <FiGithub className="text-lg text-gray-300" />
                  <span>Profil ou Dépôt GitHub</span>
                </div>
                {hasGithub && (
                  <span className="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    <FiCheck /> Connecté
                  </span>
                )}
              </div>
              <p className="text-xs text-gray-400 mb-3">
                Scrape vos repositories, vos contributions et les technologies utilisées dans vos projets.
              </p>
              <input
                type="text"
                value={githubUrl}
                onChange={(e) => onGithubUrlChange(e.target.value)}
                placeholder="https://github.com/votre-compte"
                className="w-full px-3 py-2 bg-blue-night border border-gray-700 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <button
              type="submit"
              disabled={isImportingGithub || !githubUrl.trim()}
              className="mt-4 w-full py-2 px-4 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-200 font-medium text-xs transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {isImportingGithub ? (
                <span>Collecte en cours...</span>
              ) : (
                <>
                  <FiCode />
                  <span>{hasGithub ? "Ré-importer GitHub" : "Importer GitHub"}</span>
                </>
              )}
            </button>
          </form>

          <form
            onSubmit={onImportWebsite}
            className="bg-blue-night/60 border border-gray-800 rounded-xl p-4 flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2 font-semibold text-white text-sm">
                  <FiGlobe className="text-lg text-blue-400" />
                  <span>Portfolio / Site Personnel</span>
                </div>
                {hasWebsite && (
                  <span className="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    <FiCheck /> Analysé
                  </span>
                )}
              </div>
              <p className="text-xs text-gray-400 mb-3">
                Crawl profond avec navigation interne pour extraire vos projets, articles et réalisations.
              </p>
              <input
                type="url"
                value={websiteUrl}
                onChange={(e) => onWebsiteUrlChange(e.target.value)}
                placeholder="https://mon-portfolio.fr"
                className="w-full px-3 py-2 bg-blue-night border border-gray-700 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <button
              type="submit"
              disabled={isImportingWebsite || !websiteUrl.trim()}
              className="mt-4 w-full py-2 px-4 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-200 font-medium text-xs transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {isImportingWebsite ? (
                <span>Exploration en cours...</span>
              ) : (
                <>
                  <FiCompass />
                  <span>{hasWebsite ? "Ré-analyser le site" : "Analyser le site"}</span>
                </>
              )}
            </button>
          </form>
        </div>

        <div className="mt-8 pt-6 border-t border-gray-800">
          <h3 className="text-sm font-bold uppercase tracking-wider text-gray-300 mb-3">
            Résumé de votre configuration
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="p-3 rounded-lg bg-blue-night/80 border border-gray-800">
              <span className="text-[11px] text-gray-400 block mb-1">Ciblage</span>
              <span className="text-xs font-semibold text-white block truncate">
                {profile?.preferences?.target_roles?.length
                  ? profile.preferences.target_roles.join(", ")
                  : "Postes non renseignés"}
              </span>
            </div>
            <div className="p-3 rounded-lg bg-blue-night/80 border border-gray-800">
              <span className="text-[11px] text-gray-400 block mb-1">CV Numérique</span>
              <span className="text-xs font-semibold text-white block">
                {hasCv ? (
                  <span className="text-emerald-400 flex items-center gap-1">
                    <FiCheck /> Analysé ({experiencesCount} exp.)
                  </span>
                ) : (
                  <span className="text-amber-400">À compléter plus tard</span>
                )}
              </span>
            </div>
            <div className="p-3 rounded-lg bg-blue-night/80 border border-gray-800">
              <span className="text-[11px] text-gray-400 block mb-1">Sources Web</span>
              <span className="text-xs font-semibold text-white block">
                {[hasGithub && "GitHub", hasWebsite && "Website"].filter(Boolean).join(" + ") ||
                  "Aucune connectée"}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between pt-2">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg border border-gray-700 text-gray-300 hover:text-white hover:border-gray-600 text-sm font-medium transition-colors"
        >
          <FiArrowLeft />
          <span>Retour au CV</span>
        </button>
        <button
          type="button"
          onClick={onComplete}
          disabled={isCompleting}
          className="inline-flex items-center gap-2 px-8 py-3 rounded-lg bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold text-sm shadow-lg shadow-emerald-900/30 transition-all transform hover:-translate-y-0.5 disabled:opacity-50"
        >
          <FiZap />
          <span>{isCompleting ? "Finalisation..." : "Lancer mon espace MonSuiviJob"}</span>
          <FiArrowRight />
        </button>
      </div>
    </div>
  );
}
