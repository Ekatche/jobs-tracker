"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import TargetingPreferencesSection from "@/components/profile/TargetingPreferencesSection";
import CvDropzone from "@/components/profile/CvDropzone";
import { coverLetterApi, userApi } from "@/lib/api";
import { CandidatePreferences, CandidateProfile } from "@/types/coverLetter";
import {
  FiTarget,
  FiFileText,
  FiGlobe,
  FiGithub,
  FiArrowRight,
  FiArrowLeft,
  FiCheckCircle,
  FiAlertCircle,
  FiBriefcase,
  FiCode,
  FiZap,
  FiCheck,
  FiCompass,
} from "react-icons/fi";

function OnboardingContent() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState<1 | 2 | 3>(1);
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [loadingProfile, setLoadingProfile] = useState(true);
  const [isCompleting, setIsCompleting] = useState(false);

  // Sources externes
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
      } finally {
        setLoadingProfile(false);
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
      // Même en cas d'erreur de flag, rediriger pour ne pas bloquer l'utilisateur
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
        {/* Titre & Introduction */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-blue-500/10 border border-blue-500/20 text-blue-400 mb-3">
            <FiZap className="text-sm animate-pulse" />
            <span>Configuration Initiale de votre Espace Candidat</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
            Bienvenue sur MonSuiviJob
          </h1>
          <p className="mt-2 text-sm sm:text-base text-gray-400 max-w-2xl mx-auto">
            Configurez votre profil numérique en 3 étapes clés pour activer l'analyse prédictive,
            le matching d'offres et la rédaction automatisée de candidatures.
          </p>
        </div>

        {/* Stepper Progress Bar */}
        <div className="bg-blue-night-lighter/60 border border-gray-800 rounded-xl p-4 sm:p-6 mb-8 backdrop-blur-sm shadow-xl">
          <div className="flex items-center justify-between relative">
            {/* Ligne d'arrière-plan */}
            <div className="absolute left-0 top-1/2 -translate-y-1/2 w-full h-1 bg-gray-800 -z-0" />
            <div
              className="absolute left-0 top-1/2 -translate-y-1/2 h-1 bg-gradient-to-r from-blue-500 to-indigo-500 transition-all duration-500 -z-0"
              style={{
                width: currentStep === 1 ? "0%" : currentStep === 2 ? "50%" : "100%",
              }}
            />

            {/* Étape 1 */}
            <button
              onClick={() => setCurrentStep(1)}
              className="flex flex-col items-center z-10 group focus:outline-none"
            >
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-sm transition-all duration-300 ${
                  currentStep === 1
                    ? "bg-blue-600 text-white ring-4 ring-blue-500/20 shadow-lg shadow-blue-500/30"
                    : currentStep > 1
                    ? "bg-emerald-600 text-white"
                    : "bg-gray-800 text-gray-400 border border-gray-700"
                }`}
              >
                {currentStep > 1 ? <FiCheck className="text-lg" /> : <FiTarget className="text-lg" />}
              </div>
              <span
                className={`mt-2 text-xs font-semibold tracking-wide ${
                  currentStep === 1 ? "text-blue-400" : "text-gray-400"
                }`}
              >
                1. Ciblage
              </span>
            </button>

            {/* Étape 2 */}
            <button
              onClick={() => setCurrentStep(2)}
              className="flex flex-col items-center z-10 group focus:outline-none"
            >
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-sm transition-all duration-300 ${
                  currentStep === 2
                    ? "bg-blue-600 text-white ring-4 ring-blue-500/20 shadow-lg shadow-blue-500/30"
                    : currentStep > 2
                    ? "bg-emerald-600 text-white"
                    : "bg-gray-800 text-gray-400 border border-gray-700"
                }`}
              >
                {currentStep > 2 ? <FiCheck className="text-lg" /> : <FiFileText className="text-lg" />}
              </div>
              <span
                className={`mt-2 text-xs font-semibold tracking-wide ${
                  currentStep === 2 ? "text-blue-400" : "text-gray-400"
                }`}
              >
                2. CV & Parcours
              </span>
            </button>

            {/* Étape 3 */}
            <button
              onClick={() => setCurrentStep(3)}
              className="flex flex-col items-center z-10 group focus:outline-none"
            >
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-sm transition-all duration-300 ${
                  currentStep === 3
                    ? "bg-blue-600 text-white ring-4 ring-blue-500/20 shadow-lg shadow-blue-500/30"
                    : "bg-gray-800 text-gray-400 border border-gray-700"
                }`}
              >
                <FiCompass className="text-lg" />
              </div>
              <span
                className={`mt-2 text-xs font-semibold tracking-wide ${
                  currentStep === 3 ? "text-blue-400" : "text-gray-400"
                }`}
              >
                3. Web & Lancement
              </span>
            </button>
          </div>
        </div>

        {/* Étape 1 : Préférences & Ciblage */}
        {currentStep === 1 && (
          <div className="space-y-6">
            <div className="bg-blue-night-lighter/50 border border-gray-800 rounded-xl p-5 sm:p-6 shadow-lg">
              <div className="mb-6 pb-4 border-b border-gray-800">
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  <FiTarget className="text-blue-400" />
                  <span>Vos Critères & Préférences de Recherche</span>
                </h2>
                <p className="text-sm text-gray-400 mt-1">
                  Définissez précisément les rôles, les modalités de travail et vos attentes pour que l'IA filtre
                  les offres et calcule des scores de pertinence adaptés.
                </p>
              </div>

              {/* Réutilisation du composant existant de ciblage */}
              <TargetingPreferencesSection
                initialPreferences={profile?.preferences}
                onSave={handlePreferencesSaved}
              />
            </div>

            {/* Barre de navigation de l'étape 1 */}
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

        {/* Étape 2 : Ingestion CV */}
        {currentStep === 2 && (
          <div className="space-y-6">
            <div className="bg-blue-night-lighter/50 border border-gray-800 rounded-xl p-5 sm:p-6 shadow-lg">
              <div className="mb-6 pb-4 border-b border-gray-800">
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  <FiFileText className="text-blue-400" />
                  <span>Import de votre CV de Référence</span>
                </h2>
                <p className="text-sm text-gray-400 mt-1">
                  Chargez votre CV au format PDF. Le parseur multi-modal (Mistral VLM + LLM) extrait automatiquement
                  vos expériences, stacks techniques, réalisations et formations.
                </p>
              </div>

              {/* Dropzone existante réutilisée */}
              <div className="my-6">
                <CvDropzone
                  onProfileUpdated={(updated) => setProfile(updated)}
                  hasCvSource={hasCv}
                />
              </div>

              {/* Aperçu synthétique des données extraites */}
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

            {/* Barre de navigation de l'étape 2 */}
            <div className="flex items-center justify-between pt-2">
              <button
                type="button"
                onClick={() => setCurrentStep(1)}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg border border-gray-700 text-gray-300 hover:text-white hover:border-gray-600 text-sm font-medium transition-colors"
              >
                <FiArrowLeft />
                <span>Retour au ciblage</span>
              </button>
              <div className="flex items-center gap-4">
                <button
                  type="button"
                  onClick={() => setCurrentStep(3)}
                  className="text-sm text-gray-400 hover:text-gray-200 transition-colors"
                >
                  Passer cette étape
                </button>
                <button
                  type="button"
                  onClick={() => setCurrentStep(3)}
                  className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-semibold text-sm shadow-md hover:from-blue-500 hover:to-indigo-500 transition-all transform hover:-translate-y-0.5"
                >
                  <span>Continuer vers les sources web</span>
                  <FiArrowRight />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Étape 3 : Sources Web & Lancement */}
        {currentStep === 3 && (
          <div className="space-y-6">
            <div className="bg-blue-night-lighter/50 border border-gray-800 rounded-xl p-5 sm:p-6 shadow-lg">
              <div className="mb-6 pb-4 border-b border-gray-800">
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  <FiGlobe className="text-blue-400" />
                  <span>Présence Web & Finalisation</span>
                </h2>
                <p className="text-sm text-gray-400 mt-1">
                  Connectez vos profils publics pour consolider vos réalisations techniques réelles.
                </p>
              </div>

              {/* Message d'état pour les imports */}
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
                {/* Formulaire GitHub */}
                <form
                  onSubmit={handleImportGithub}
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
                      onChange={(e) => setGithubUrl(e.target.value)}
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

                {/* Formulaire Portfolio / Site Web */}
                <form
                  onSubmit={handleImportWebsite}
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
                      onChange={(e) => setWebsiteUrl(e.target.value)}
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

              {/* Récapitulatif global avant validation */}
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

            {/* Barre de navigation finale */}
            <div className="flex items-center justify-between pt-2">
              <button
                type="button"
                onClick={() => setCurrentStep(2)}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg border border-gray-700 text-gray-300 hover:text-white hover:border-gray-600 text-sm font-medium transition-colors"
              >
                <FiArrowLeft />
                <span>Retour au CV</span>
              </button>
              <button
                type="button"
                onClick={handleCompleteOnboarding}
                disabled={isCompleting}
                className="inline-flex items-center gap-2 px-8 py-3 rounded-lg bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold text-sm shadow-lg shadow-emerald-900/30 transition-all transform hover:-translate-y-0.5 disabled:opacity-50"
              >
                <FiZap />
                <span>{isCompleting ? "Finalisation..." : "Lancer mon espace MonSuiviJob"}</span>
                <FiArrowRight />
              </button>
            </div>
          </div>
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
