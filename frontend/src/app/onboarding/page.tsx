"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import TargetingPreferencesSection from "@/components/profile/TargetingPreferencesSection";
import OnboardingStepper from "@/components/onboarding/OnboardingStepper";
import OnboardingStepCv from "@/components/onboarding/OnboardingStepCv";
import OnboardingStepWeb from "@/components/onboarding/OnboardingStepWeb";
import { coverLetterApi, userApi } from "@/lib/api";
import { CandidatePreferences, CandidateProfile } from "@/types/coverLetter";
import { FiTarget, FiArrowRight, FiZap } from "react-icons/fi";

function OnboardingContent() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState<1 | 2 | 3>(1);
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [isCompleting, setIsCompleting] = useState(false);

  const [githubUrl, setGithubUrl] = useState("");
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [isImportingGithub, setIsImportingGithub] = useState(false);
  const [isImportingWebsite, setIsImportingWebsite] = useState(false);
  const [sourceMessage, setSourceMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        const data = await coverLetterApi.getCandidateProfile();
        if (data) {
          setProfile(data);
          if (data.contact?.github) setGithubUrl(data.contact.github);
          if (data.contact?.website) setWebsiteUrl(data.contact.website);
        }
      } catch (err) {
        console.error("Impossible de charger le profil existant:", err);
      }
    }
    loadData();
  }, []);

  const handlePreferencesSaved = async (newPrefs: CandidatePreferences) => {
    try {
      const updated = await coverLetterApi.updateCandidatePreferences(newPrefs);
      setProfile(updated);
    } catch (err) {
      console.error("Erreur lors de la sauvegarde des préférences:", err);
    }
  };

  const handleImportGithub = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!githubUrl.trim()) return;
    setIsImportingGithub(true);
    setSourceMessage(null);
    try {
      const updated = await coverLetterApi.importGithub(githubUrl.trim());
      setProfile(updated);
      setSourceMessage({
        type: "success",
        text: "Dépôts et compétences GitHub importés avec succès !",
      });
    } catch (err: unknown) {
      setSourceMessage({
        type: "error",
        text: err instanceof Error ? err.message : "Échec de l'import GitHub",
      });
    } finally {
      setIsImportingGithub(false);
    }
  };

  const handleImportWebsite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!websiteUrl.trim()) return;
    setIsImportingWebsite(true);
    setSourceMessage(null);
    try {
      const updated = await coverLetterApi.importWebsite(websiteUrl.trim());
      setProfile(updated);
      setSourceMessage({
        type: "success",
        text: "Portfolio/Site personnel exploré et analysé avec succès !",
      });
    } catch (err: unknown) {
      setSourceMessage({
        type: "error",
        text: err instanceof Error ? err.message : "Échec de l'exploration du site",
      });
    } finally {
      setIsImportingWebsite(false);
    }
  };

  const handleCompleteOnboarding = async () => {
    setIsCompleting(true);
    try {
      await userApi.completeOnboarding();
      router.push("/applications");
    } catch (err) {
      console.error("Erreur finalisation onboarding:", err);
      router.push("/applications");
    } finally {
      setIsCompleting(false);
    }
  };

  const experiencesCount = profile?.experiences?.length || 0;
  const skillsCount = profile?.skills
    ? Object.values(profile.skills).flat().length
    : 0;
  const hasCv = Boolean(profile?.sources && "cv" in profile.sources);
  const hasGithub = Boolean(profile?.sources && "github" in profile.sources);
  const hasWebsite = Boolean(profile?.sources && "website" in profile.sources);

  return (
    <div className="min-h-screen bg-blue-night text-gray-100 py-10 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto">
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-blue-500/10 border border-blue-500/20 text-blue-400 mb-3">
            <FiZap className="text-sm animate-pulse" />
            <span>Configuration Initiale de votre Espace Candidat</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
            Bienvenue sur MonSuiviJob
          </h1>
          <p className="mt-2 text-sm sm:text-base text-gray-400 max-w-2xl mx-auto">
            Configurez votre profil numérique en 3 étapes clés pour activer l&apos;analyse
            prédictive, le matching d&apos;offres et la rédaction automatisée de candidatures.
          </p>
        </div>

        <OnboardingStepper currentStep={currentStep} onSelectStep={setCurrentStep} />

        {currentStep === 1 && (
          <div className="space-y-6">
            <div className="bg-blue-night-lighter/50 border border-gray-800 rounded-xl p-5 sm:p-6 shadow-lg">
              <div className="mb-6 pb-4 border-b border-gray-800">
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  <FiTarget className="text-blue-400" />
                  <span>Vos Critères &amp; Préférences de Recherche</span>
                </h2>
                <p className="text-sm text-gray-400 mt-1">
                  Définissez précisément les rôles, les modalités de travail et vos attentes pour
                  que l&apos;IA filtre les offres et calcule des scores de pertinence adaptés.
                </p>
              </div>

              <TargetingPreferencesSection
                initialPreferences={profile?.preferences}
                onSave={handlePreferencesSaved}
              />
            </div>

            <div className="flex items-center justify-between pt-2">
              <button
                type="button"
                onClick={() => setCurrentStep(2)}
                className="text-sm text-gray-400 hover:text-gray-200 transition-colors"
              >
                Passer cette étape
              </button>
              <button
                type="button"
                onClick={() => setCurrentStep(2)}
                className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-semibold text-sm shadow-md hover:from-blue-500 hover:to-indigo-500 transition-all transform hover:-translate-y-0.5"
              >
                <span>Continuer vers le CV</span>
                <FiArrowRight />
              </button>
            </div>
          </div>
        )}

        {currentStep === 2 && (
          <OnboardingStepCv
            profile={profile}
            hasCv={hasCv}
            experiencesCount={experiencesCount}
            skillsCount={skillsCount}
            onProfileUpdated={setProfile}
            onBack={() => setCurrentStep(1)}
            onNext={() => setCurrentStep(3)}
          />
        )}

        {currentStep === 3 && (
          <OnboardingStepWeb
            profile={profile}
            githubUrl={githubUrl}
            websiteUrl={websiteUrl}
            isImportingGithub={isImportingGithub}
            isImportingWebsite={isImportingWebsite}
            isCompleting={isCompleting}
            sourceMessage={sourceMessage}
            hasCv={hasCv}
            hasGithub={hasGithub}
            hasWebsite={hasWebsite}
            experiencesCount={experiencesCount}
            onGithubUrlChange={setGithubUrl}
            onWebsiteUrlChange={setWebsiteUrl}
            onImportGithub={handleImportGithub}
            onImportWebsite={handleImportWebsite}
            onBack={() => setCurrentStep(2)}
            onComplete={handleCompleteOnboarding}
          />
        )}
      </div>
    </div>
  );
}

export default function OnboardingPage() {
  return (
    <ProtectedRoute>
      <OnboardingContent />
    </ProtectedRoute>
  );
}
