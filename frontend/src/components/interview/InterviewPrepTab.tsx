"use client";

import React, { useEffect, useState, useCallback } from "react";
import { interviewPrepApi } from "@/lib/api";
import { InterviewPrep } from "@/types/interview";
import StarStoryCard from "./StarStoryCard";
import AudiencePacksViewer from "./AudiencePacksViewer";
import AnticipatedQuestionsViewer from "./AnticipatedQuestionsViewer";
import ReverseQuestionsViewer from "./ReverseQuestionsViewer";
import {
  FiZap,
  FiDownload,
  FiCopy,
  FiCheck,
  FiRefreshCw,
  FiBookOpen,
  FiUsers,
  FiHelpCircle,
  FiShield,
  FiAlertCircle,
} from "react-icons/fi";

interface InterviewPrepTabProps {
  offerId: string;
  targetRole?: string;
  targetCompany?: string;
}

export default function InterviewPrepTab({
  offerId,
  targetRole,
  targetCompany,
}: InterviewPrepTabProps) {
  const [prep, setPrep] = useState<InterviewPrep | null>(null);
  const [loading, setLoading] = useState(true);
  const [generatingModule, setGeneratingModule] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [activeSection, setActiveSection] = useState<"stories" | "audience" | "questions" | "reverse">("stories");

  const loadPrep = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await interviewPrepApi.get(offerId);
      setPrep(data);
    } catch (err: unknown) {
      console.error("Error loading interview prep:", err);
      const msg = err instanceof Error ? err.message : "Impossible de charger la préparation d'entretien.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [offerId]);

  useEffect(() => {
    loadPrep();
  }, [loadPrep]);

  const handleGenerateModule = async (moduleType: "stories" | "audience-packs" | "questions" | "reverse-questions" | "all") => {
    try {
      setGeneratingModule(moduleType);
      setError(null);
      let updated: InterviewPrep;
      if (moduleType === "stories") {
        updated = await interviewPrepApi.generateStories(offerId);
      } else if (moduleType === "audience-packs") {
        updated = await interviewPrepApi.generateAudiencePacks(offerId);
      } else if (moduleType === "questions") {
        updated = await interviewPrepApi.generateQuestions(offerId);
      } else if (moduleType === "reverse-questions") {
        updated = await interviewPrepApi.generateReverseQuestions(offerId);
      } else {
        updated = await interviewPrepApi.generateAll(offerId);
      }
      setPrep(updated);
    } catch (err: unknown) {
      console.error(`Error generating ${moduleType}:`, err);
      const msg = err instanceof Error ? err.message : `Erreur lors de la génération du module ${moduleType}`;
      setError(msg);
    } finally {
      setGeneratingModule(null);
    }
  };

  const handleCopyMarkdown = async () => {
    try {
      const md = await interviewPrepApi.exportMarkdown(offerId);
      await navigator.clipboard.writeText(md);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Error copying markdown:", err);
    }
  };

  const handleDownloadMarkdown = async () => {
    try {
      const compSlug = targetCompany ? targetCompany.replace(/[^\w]/g, "_").toLowerCase() : "company";
      await interviewPrepApi.downloadMarkdown(offerId, `prep_${compSlug}_${offerId.slice(0, 6)}.md`);
    } catch (err) {
      console.error("Error downloading markdown:", err);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-slate-400 space-y-3">
        <FiRefreshCw className="w-8 h-8 animate-spin text-indigo-400" />
        <p className="text-sm">Chargement du kit de préparation d'entretien...</p>
      </div>
    );
  }

  const storiesCount = prep?.stories?.length || 0;
  const hasAudience = !!(prep?.recruiter_pack || prep?.hm_pack || prep?.tech_pack);
  const questionsCount = prep?.anticipated_questions?.length || 0;
  const reverseCount = prep?.reverse_questions?.length || 0;
  const totalCompleted = (storiesCount > 0 ? 1 : 0) + (hasAudience ? 1 : 0) + (questionsCount > 0 ? 1 : 0) + (reverseCount > 0 ? 1 : 0);

  return (
    <div className="space-y-6">
      {/* Action Header Card */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 sm:p-6 shadow-xl relative overflow-hidden backdrop-blur-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 flex items-center gap-1.5">
                <FiZap className="w-3.5 h-3.5 text-indigo-400" />
                Intelligence Career-Ops
              </span>
              <span className="text-xs text-slate-400">
                • {totalCompleted}/4 modules prêts
              </span>
            </div>
            <h3 className="text-xl font-bold text-white">
              Kit de Préparation d'Entretien {targetCompany ? `— ${targetCompany}` : ""}
            </h3>
            <p className="text-xs text-slate-400 mt-1 max-w-2xl">
              Préparez vos entretiens avec précision : histoires STAR+R réelles, discours segmenté par audience, questions probables et questions inversées anti red-flags.
            </p>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-wrap items-center gap-2 shrink-0">
            <button
              type="button"
              disabled={generatingModule !== null}
              onClick={() => handleGenerateModule("all")}
              className="px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-500/25 flex items-center gap-2 transition-all disabled:opacity-50"
            >
              <FiZap className={`w-4 h-4 ${generatingModule === "all" ? "animate-spin" : ""}`} />
              <span>{generatingModule === "all" ? "Génération en cours..." : "Tout générer (1-Clic)"}</span>
            </button>

            <button
              type="button"
              onClick={handleCopyMarkdown}
              title="Copier en Markdown"
              className="p-2 sm:px-3 sm:py-2 rounded-xl text-xs sm:text-sm font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1.5 transition-colors"
            >
              {copied ? <FiCheck className="w-4 h-4 text-emerald-400" /> : <FiCopy className="w-4 h-4" />}
              <span className="hidden sm:inline">{copied ? "Copié !" : "Copier .md"}</span>
            </button>

            <button
              type="button"
              onClick={handleDownloadMarkdown}
              title="Télécharger en fichier Markdown"
              className="p-2 sm:px-3 sm:py-2 rounded-xl text-xs sm:text-sm font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1.5 transition-colors"
            >
              <FiDownload className="w-4 h-4" />
              <span className="hidden sm:inline">Télécharger</span>
            </button>
          </div>
        </div>

        {error && (
          <div className="mt-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-300 flex items-center gap-2">
            <FiAlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* Modular Section Navigation */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <button
          type="button"
          onClick={() => setActiveSection("stories")}
          className={`p-3.5 rounded-xl border flex flex-col items-start gap-1 transition-all ${
            activeSection === "stories"
              ? "bg-indigo-950/40 border-indigo-500/60 shadow-lg shadow-indigo-500/10"
              : "bg-slate-900/60 border-slate-800 text-slate-400 hover:bg-slate-800/40"
          }`}
        >
          <div className="flex items-center justify-between w-full">
            <span className="text-xs font-semibold text-white flex items-center gap-1.5">
              <FiBookOpen className="w-4 h-4 text-indigo-400" />
              1. Histoires STAR+R
            </span>
            <span className={`text-[11px] font-bold px-1.5 py-0.2 rounded ${storiesCount > 0 ? "bg-emerald-500/10 text-emerald-400" : "bg-slate-800 text-slate-500"}`}>
              {storiesCount}
            </span>
          </div>
          <span className="text-[11px] text-slate-400">Preuves & métriques réelles</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveSection("audience")}
          className={`p-3.5 rounded-xl border flex flex-col items-start gap-1 transition-all ${
            activeSection === "audience"
              ? "bg-indigo-950/40 border-indigo-500/60 shadow-lg shadow-indigo-500/10"
              : "bg-slate-900/60 border-slate-800 text-slate-400 hover:bg-slate-800/40"
          }`}
        >
          <div className="flex items-center justify-between w-full">
            <span className="text-xs font-semibold text-white flex items-center gap-1.5">
              <FiUsers className="w-4 h-4 text-indigo-400" />
              2. Packs d'Audience
            </span>
            <span className={`text-[11px] font-bold px-1.5 py-0.2 rounded ${hasAudience ? "bg-emerald-500/10 text-emerald-400" : "bg-slate-800 text-slate-500"}`}>
              {hasAudience ? "Prêt" : "0"}
            </span>
          </div>
          <span className="text-[11px] text-slate-400">RH, Manager, Panel Tech</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveSection("questions")}
          className={`p-3.5 rounded-xl border flex flex-col items-start gap-1 transition-all ${
            activeSection === "questions"
              ? "bg-indigo-950/40 border-indigo-500/60 shadow-lg shadow-indigo-500/10"
              : "bg-slate-900/60 border-slate-800 text-slate-400 hover:bg-slate-800/40"
          }`}
        >
          <div className="flex items-center justify-between w-full">
            <span className="text-xs font-semibold text-white flex items-center gap-1.5">
              <FiHelpCircle className="w-4 h-4 text-indigo-400" />
              3. Questions Anticipées
            </span>
            <span className={`text-[11px] font-bold px-1.5 py-0.2 rounded ${questionsCount > 0 ? "bg-emerald-500/10 text-emerald-400" : "bg-slate-800 text-slate-500"}`}>
              {questionsCount}
            </span>
          </div>
          <span className="text-[11px] text-slate-400">Comportement & Technique</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveSection("reverse")}
          className={`p-3.5 rounded-xl border flex flex-col items-start gap-1 transition-all ${
            activeSection === "reverse"
              ? "bg-indigo-950/40 border-indigo-500/60 shadow-lg shadow-indigo-500/10"
              : "bg-slate-900/60 border-slate-800 text-slate-400 hover:bg-slate-800/40"
          }`}
        >
          <div className="flex items-center justify-between w-full">
            <span className="text-xs font-semibold text-white flex items-center gap-1.5">
              <FiShield className="w-4 h-4 text-amber-400" />
              4. Anti Red-Flags
            </span>
            <span className={`text-[11px] font-bold px-1.5 py-0.2 rounded ${reverseCount > 0 ? "bg-emerald-500/10 text-emerald-400" : "bg-slate-800 text-slate-500"}`}>
              {reverseCount}
            </span>
          </div>
          <span className="text-[11px] text-slate-400">Questions à poser</span>
        </button>
      </div>

      {/* Section Content with Unitary Generation Header */}
      <div>
        {activeSection === "stories" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between bg-slate-900/40 p-3 rounded-xl border border-slate-800/80">
              <span className="text-xs text-slate-400">
                Génération de 3 à 5 histoires structurées basées sur vos expériences déclarées et les exigences du Bloc B.
              </span>
              <button
                type="button"
                disabled={generatingModule !== null}
                onClick={() => handleGenerateModule("stories")}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600/90 hover:bg-indigo-600 text-white shrink-0 flex items-center gap-1.5 transition-colors disabled:opacity-50"
              >
                <FiRefreshCw className={`w-3.5 h-3.5 ${generatingModule === "stories" ? "animate-spin" : ""}`} />
                <span>{generatingModule === "stories" ? "Génération..." : storiesCount > 0 ? "Régénérer" : "Générer les histoires"}</span>
              </button>
            </div>

            {storiesCount === 0 ? (
              <div className="text-center py-12 px-4 rounded-2xl bg-slate-900/40 border border-dashed border-slate-800">
                <FiBookOpen className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                <h4 className="text-sm font-medium text-slate-300">Aucune histoire STAR+R générée</h4>
                <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                  Cliquez sur "Générer les histoires" pour extraire vos meilleures réalisations alignées sur cette offre.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {prep!.stories.map((story, idx) => (
                  <StarStoryCard key={story.id || idx} story={story} index={idx} />
                ))}
              </div>
            )}
          </div>
        )}

        {activeSection === "audience" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between bg-slate-900/40 p-3 rounded-xl border border-slate-800/80">
              <span className="text-xs text-slate-400">
                Adaptez votre discours selon l'interlocuteur : RH (cadrage & salaire), Manager (stratégie), ou Pairs (architecture).
              </span>
              <button
                type="button"
                disabled={generatingModule !== null}
                onClick={() => handleGenerateModule("audience-packs")}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600/90 hover:bg-indigo-600 text-white shrink-0 flex items-center gap-1.5 transition-colors disabled:opacity-50"
              >
                <FiRefreshCw className={`w-3.5 h-3.5 ${generatingModule === "audience-packs" ? "animate-spin" : ""}`} />
                <span>{generatingModule === "audience-packs" ? "Génération..." : hasAudience ? "Régénérer" : "Générer les packs"}</span>
              </button>
            </div>

            {!hasAudience ? (
              <div className="text-center py-12 px-4 rounded-2xl bg-slate-900/40 border border-dashed border-slate-800">
                <FiUsers className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                <h4 className="text-sm font-medium text-slate-300">Aucun pack d'audience généré</h4>
                <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                  Générez vos guides personnalisés pour aborder sereinement chaque tour d'entretien.
                </p>
              </div>
            ) : (
              <AudiencePacksViewer
                recruiterPack={prep?.recruiter_pack}
                hmPack={prep?.hm_pack}
                techPack={prep?.tech_pack}
              />
            )}
          </div>
        )}

        {activeSection === "questions" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between bg-slate-900/40 p-3 rounded-xl border border-slate-800/80">
              <span className="text-xs text-slate-400">
                Anticipation des questions comportementales (avec renvoi STAR+R) et techniques déduites de l'offre.
              </span>
              <button
                type="button"
                disabled={generatingModule !== null}
                onClick={() => handleGenerateModule("questions")}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600/90 hover:bg-indigo-600 text-white shrink-0 flex items-center gap-1.5 transition-colors disabled:opacity-50"
              >
                <FiRefreshCw className={`w-3.5 h-3.5 ${generatingModule === "questions" ? "animate-spin" : ""}`} />
                <span>{generatingModule === "questions" ? "Génération..." : questionsCount > 0 ? "Régénérer" : "Générer les questions"}</span>
              </button>
            </div>

            {questionsCount === 0 ? (
              <div className="text-center py-12 px-4 rounded-2xl bg-slate-900/40 border border-dashed border-slate-800">
                <FiHelpCircle className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                <h4 className="text-sm font-medium text-slate-300">Aucune question anticipée</h4>
                <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                  Prévoyez les questions ciblées et préparez les points clés incontournables.
                </p>
              </div>
            ) : (
              <AnticipatedQuestionsViewer questions={prep!.anticipated_questions} />
            )}
          </div>
        )}

        {activeSection === "reverse" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between bg-slate-900/40 p-3 rounded-xl border border-slate-800/80">
              <span className="text-xs text-slate-400">
                Questions d'audit pour évaluer la santé de l'équipe, la dette technique et l'autonomie.
              </span>
              <button
                type="button"
                disabled={generatingModule !== null}
                onClick={() => handleGenerateModule("reverse-questions")}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600/90 hover:bg-indigo-600 text-white shrink-0 flex items-center gap-1.5 transition-colors disabled:opacity-50"
              >
                <FiRefreshCw className={`w-3.5 h-3.5 ${generatingModule === "reverse-questions" ? "animate-spin" : ""}`} />
                <span>{generatingModule === "reverse-questions" ? "Génération..." : reverseCount > 0 ? "Régénérer" : "Générer les questions"}</span>
              </button>
            </div>

            {reverseCount === 0 ? (
              <div className="text-center py-12 px-4 rounded-2xl bg-slate-900/40 border border-dashed border-slate-800">
                <FiShield className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                <h4 className="text-sm font-medium text-slate-300">Aucune question inversée générée</h4>
                <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                  Générez les questions tactiques pour auditer vos futurs collaborateurs.
                </p>
              </div>
            ) : (
              <ReverseQuestionsViewer questions={prep!.reverse_questions} />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
