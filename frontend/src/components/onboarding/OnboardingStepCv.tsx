"use client";

import CvDropzone from "@/components/profile/CvDropzone";
import { CandidateProfile } from "@/types/coverLetter";
import {
  FiFileText,
  FiArrowRight,
  FiArrowLeft,
  FiCheckCircle,
  FiBriefcase,
} from "react-icons/fi";

interface OnboardingStepCvProps {
  profile: CandidateProfile | null;
  hasCv: boolean;
  experiencesCount: number;
  skillsCount: number;
  onProfileUpdated: (updated: CandidateProfile) => void;
  onBack: () => void;
  onNext: () => void;
}

export default function OnboardingStepCv({
  profile,
  hasCv,
  experiencesCount,
  skillsCount,
  onProfileUpdated,
  onBack,
  onNext,
}: OnboardingStepCvProps) {
  return (
    <div className="space-y-6">
      <div className="bg-blue-night-lighter/50 border border-gray-800 rounded-xl p-5 sm:p-6 shadow-lg">
        <div className="mb-6 pb-4 border-b border-gray-800">
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <FiFileText className="text-blue-400" />
            <span>Import de votre CV de Référence</span>
          </h2>
          <p className="text-sm text-gray-400 mt-1">
            Chargez votre CV au format PDF. Le parseur multi-modal (Mistral VLM + LLM) extrait
            automatiquement vos expériences, compétences, réalisations et formations.
          </p>
        </div>

        <div className="my-6">
          <CvDropzone onProfileUpdated={onProfileUpdated} hasCvSource={hasCv} />
        </div>

        {profile && (experiencesCount > 0 || skillsCount > 0) && (
          <div className="mt-6 p-4 rounded-lg bg-blue-night/70 border border-blue-500/30">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold uppercase text-blue-400 tracking-wider flex items-center gap-1.5">
                <FiCheckCircle className="text-emerald-400" /> Données extraites avec succès
              </span>
              <span className="text-xs text-gray-400">
                {experiencesCount} expérience(s) • {skillsCount} compétence(s)
              </span>
            </div>
            {profile.headline && (
              <p className="text-sm font-medium text-white mb-2">
                Poste identifié : <span className="text-blue-300">{profile.headline}</span>
              </p>
            )}
            {profile.experiences && profile.experiences.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {profile.experiences.slice(0, 3).map((exp, idx) => (
                  <div
                    key={idx}
                    className="px-2.5 py-1 rounded bg-gray-800/80 border border-gray-700 text-xs text-gray-300 flex items-center gap-1.5"
                  >
                    <FiBriefcase className="text-gray-400" />
                    <span className="font-semibold text-gray-200">{exp.role}</span>
                    <span className="text-gray-500">chez</span>
                    <span className="text-blue-400">{exp.company}</span>
                  </div>
                ))}
                {profile.experiences.length > 3 && (
                  <span className="px-2 py-1 text-xs text-gray-400">
                    +{profile.experiences.length - 3} autre(s)
                  </span>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between pt-2">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg border border-gray-700 text-gray-300 hover:text-white hover:border-gray-600 text-sm font-medium transition-colors"
        >
          <FiArrowLeft />
          <span>Retour au ciblage</span>
        </button>
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={onNext}
            className="text-sm text-gray-400 hover:text-gray-200 transition-colors"
          >
            Passer cette étape
          </button>
          <button
            type="button"
            onClick={onNext}
            className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-semibold text-sm shadow-md hover:from-blue-500 hover:to-indigo-500 transition-all transform hover:-translate-y-0.5"
          >
            <span>Continuer vers les sources web</span>
            <FiArrowRight />
          </button>
        </div>
      </div>
    </div>
  );
}
