"use client";

import { useEffect, useState, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  FiFileText,
  FiSearch,
  FiPlus,
  FiRefreshCw,
  FiFilter,
  FiCheckCircle,
} from "react-icons/fi";
import { TailoredResume, TailoredCVSchema } from "@/types/resume";
import { resumeApi, jobOffersApi, type JobOffer } from "@/lib/api";
import ResumeCard from "@/components/resumes/ResumeCard";
import ResumePreviewModal from "@/components/resumes/ResumePreviewModal";

function ResumesContent() {
  const searchParams = useSearchParams();
  const preselectedOfferId = searchParams.get("generate_offer_id");

  const [resumes, setResumes] = useState<TailoredResume[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [templateFilter, setTemplateFilter] = useState<string>("all");
  const [activeResumeForPreview, setActiveResumeForPreview] = useState<TailoredResume | null>(null);
  const [modalInitialTab, setModalInitialTab] = useState<"preview" | "edit">("preview");

  // New CV Generation Modal State
  const [isGenerateModalOpen, setIsGenerateModalOpen] = useState<boolean>(false);
  const [availableOffers, setAvailableOffers] = useState<JobOffer[]>([]);
  const [offerSearchQuery, setOfferSearchQuery] = useState<string>("" );
  const [selectedOfferId, setSelectedOfferId] = useState<string>("");
  const [selectedTemplate, setSelectedTemplate] = useState<string>("sidebar_elegance");
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [generateError, setGenerateError] = useState<string | null>(null);

  const fetchResumes = async () => {
    setLoading(true);
    try {
      const data = await resumeApi.getAll();
      setResumes(data);
    } catch (err) {
      console.error("Failed to load resumes:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchResumes();
  }, []);

  const openGenerateModal = async (initialOfferId?: string) => {
    setIsGenerateModalOpen(true);
    setGenerateError(null);
    setOfferSearchQuery("");
    try {
      const offers = await jobOffersApi.getAll({ limit: 100 });
      setAvailableOffers(offers);
      if (initialOfferId) {
        setSelectedOfferId(initialOfferId);
      } else if (offers.length > 0) {
        setSelectedOfferId(offers[0].id || "");
      }
    } catch (err) {
      console.error("Failed to fetch job offers:", err);
    }
  };

  const filteredOffersForModal = availableOffers.filter((o) => {
    if (!offerSearchQuery.trim()) return true;
    const q = offerSearchQuery.toLowerCase();
    return (
      (o.poste && o.poste.toLowerCase().includes(q)) ||
      (o.entreprise && o.entreprise.toLowerCase().includes(q)) ||
      (o.localisation && o.localisation.toLowerCase().includes(q))
    );
  });


  useEffect(() => {
    if (preselectedOfferId) {
      openGenerateModal(preselectedOfferId);
    }
  }, [preselectedOfferId]);

  const handleGenerateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedOfferId) return;

    setIsGenerating(true);
    setGenerateError(null);
    try {
      const newResume = await resumeApi.generate({
        offer_id: selectedOfferId,
        template: selectedTemplate,
        with_photo: false,
      });
      setResumes((prev) => [newResume, ...prev]);
      setIsGenerateModalOpen(false);
      setActiveResumeForPreview(newResume);
    } catch (err: unknown) {
      console.error("CV generation failed:", err);
      const errorDetail =
        err instanceof Error
          ? err.message
          : err && typeof err === "object" && "response" in err
          ? ((err as { response?: { data?: { detail?: string } } }).response?.data?.detail)
          : null;
      setGenerateError(
        errorDetail || "Échec de la génération du CV. Vérifiez votre profil ou réessayez."
      );
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDeleteResume = async (id: string) => {
    await resumeApi.delete(id);
    setResumes((prev) => prev.filter((r) => (r.id || r._id) !== id));
    if ((activeResumeForPreview?.id || activeResumeForPreview?._id) === id) {
      setActiveResumeForPreview(null);
    }
  };

  const handleUpdateTemplate = async (id: string, template: string, withPhoto: boolean) => {
    try {
      const updated = await resumeApi.update(id, { template, with_photo: withPhoto });
      setResumes((prev) => prev.map((r) => ((r.id || r._id) === id ? updated : r)));
      if ((activeResumeForPreview?.id || activeResumeForPreview?._id) === id) {
        setActiveResumeForPreview(updated);
      }
    } catch (err) {
      console.error("Failed to update template:", err);
    }
  };

  const handleUpdateResumeContent = async (id: string, content: TailoredCVSchema) => {
    try {
      const updated = await resumeApi.update(id, { content });
      setResumes((prev) => prev.map((r) => ((r.id || r._id) === id ? updated : r)));
      if ((activeResumeForPreview?.id || activeResumeForPreview?._id) === id) {
        setActiveResumeForPreview(updated);
      }
    } catch (err) {
      console.error("Failed to update resume content:", err);
      throw err;
    }
  };

  const handleRegenerateResume = async (resume: TailoredResume) => {
    try {
      const newResume = await resumeApi.generate({
        offer_id: resume.offer_id,
        template: resume.template,
        with_photo: resume.with_photo,
        application_id: resume.application_id,
      });
      setResumes((prev) => [newResume, ...prev]);
      if ((activeResumeForPreview?.id || activeResumeForPreview?._id) === (resume.id || resume._id)) {
        setActiveResumeForPreview(newResume);
      }
    } catch (err: unknown) {
      console.error("Failed to regenerate resume:", err);
      const msg = err instanceof Error ? err.message : "Erreur lors de la régénération du CV.";
      alert(msg);
      throw err;
    }
  };

  // Filtering
  const filteredResumes = resumes.filter((r) => {
    const matchesSearch =
      r.target_role.toLowerCase().includes(searchQuery.toLowerCase()) ||
      r.target_company.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesTemplate = templateFilter === "all" || r.template === templateFilter;
    return matchesSearch && matchesTemplate;
  });

  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-white flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-blue-600/20 text-blue-400 border border-blue-500/30 shadow-inner">
              <FiFileText className="text-2xl" />
            </div>
            <span>Mes CV Personnalisés</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Générez des CV A4 vectoriels sur-mesure alignés sur chaque offre d'emploi et certifiés anti-hallucination.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => openGenerateModal()}
            className="flex items-center gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white px-4 py-2.5 rounded-xl text-sm font-semibold shadow-lg shadow-blue-500/25 transition-all"
          >
            <FiPlus className="text-lg" />
            <span>Générer un CV adapté</span>
          </button>
        </div>
      </div>

      {/* Search & Filters */}
      <div className="bg-[#152238] border border-slate-700/60 rounded-xl p-4 mb-8 flex flex-col md:flex-row items-center justify-between gap-4 shadow-md">
        <div className="relative w-full md:w-80">
          <FiSearch className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 text-base" />
          <input
            type="text"
            placeholder="Rechercher par poste ou entreprise..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-slate-900/60 border border-slate-700/80 rounded-lg text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
          />
        </div>

        <div className="flex items-center gap-3 w-full md:w-auto">
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <FiFilter />
            <span>Modèle :</span>
          </div>
          <select
            value={templateFilter}
            onChange={(e) => setTemplateFilter(e.target.value)}
            className="bg-slate-900/60 border border-slate-700/80 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
          >
            <option value="all">Tous les modèles ({resumes.length})</option>
            <option value="sidebar_elegance">Sidebar Elegance</option>
            <option value="executive_minimalist">Executive Minimalist</option>
          </select>
        </div>
      </div>

      {/* Main Grid or Empty States */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 gap-3">
          <FiRefreshCw className="animate-spin text-3xl text-blue-400" />
          <p className="text-sm text-slate-400">Chargement de vos CV personnalisés...</p>
        </div>
      ) : filteredResumes.length === 0 ? (
        <div className="bg-[#152238]/60 border border-slate-800 rounded-2xl p-12 text-center max-w-xl mx-auto shadow-xl">
          <div className="w-16 h-16 rounded-full bg-blue-600/10 border border-blue-500/20 text-blue-400 flex items-center justify-center mx-auto mb-4 text-2xl">
            <FiFileText />
          </div>
          <h2 className="text-lg font-bold text-white mb-2">
            {searchQuery || templateFilter !== "all"
              ? "Aucun résultat trouvé"
              : "Aucun CV adapté pour le moment"}
          </h2>
          <p className="text-sm text-slate-400 mb-6 leading-relaxed">
            {searchQuery || templateFilter !== "all"
              ? "Essayez de modifier vos filtres de recherche."
              : "Adaptez instantanément votre CV à une offre d'emploi cible pour maximiser vos chances d'entretien."}
          </p>
          <button
            onClick={() => openGenerateModal()}
            className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-5 py-2.5 rounded-xl text-sm font-semibold shadow-md transition-colors"
          >
            <FiPlus />
            <span>Créer mon premier CV adapté</span>
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredResumes.map((resume) => (
            <ResumeCard
              key={resume.id || resume._id}
              resume={resume}
              onPreview={(r) => {
                setModalInitialTab("preview");
                setActiveResumeForPreview(r);
              }}
              onEdit={(r) => {
                setModalInitialTab("edit");
                setActiveResumeForPreview(r);
              }}
              onRegenerate={handleRegenerateResume}
              onDelete={handleDeleteResume}
            />
          ))}
        </div>
      )}

      {/* Preview & Edit Modal */}
      <ResumePreviewModal
        resume={activeResumeForPreview}
        isOpen={!!activeResumeForPreview}
        onClose={() => setActiveResumeForPreview(null)}
        onUpdateTemplate={handleUpdateTemplate}
        onUpdateContent={handleUpdateResumeContent}
        onRegenerate={handleRegenerateResume}
        initialTab={modalInitialTab}
      />

      {/* Generator Modal */}
      {isGenerateModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
          <div className="bg-[#152238] border border-slate-700 rounded-2xl shadow-2xl w-full max-w-lg p-6 text-slate-100 animate-in fade-in zoom-in-95 duration-200">
            <h2 className="text-lg font-bold text-white mb-1 flex items-center gap-2">
              <FiFileText className="text-blue-400" />
              <span>Générer un CV sur-mesure</span>
            </h2>
            <p className="text-xs text-slate-400 mb-5">
              Sélectionnez l'offre cible pour laquelle adapter vos expériences et vos compétences.
            </p>

            {generateError && (
              <div className="mb-4 p-3 bg-red-950/50 border border-red-800/60 rounded-xl text-xs text-red-200">
                {generateError}
              </div>
            )}

            <form onSubmit={handleGenerateSubmit} className="space-y-4">
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="block text-xs font-semibold text-slate-300">
                    Offre d'emploi cible
                  </label>
                  {availableOffers.length > 0 && (
                    <span className="text-[11px] text-slate-400">
                      {filteredOffersForModal.length} / {availableOffers.length} offres
                    </span>
                  )}
                </div>

                {availableOffers.length === 0 ? (
                  <div className="text-xs text-slate-400 p-3 bg-slate-900/60 rounded-lg border border-slate-800">
                    Aucune offre trouvée.{" "}
                    <Link href="/offers" className="text-blue-400 underline">
                      Explorez d'abord les offres
                    </Link>
                    .
                  </div>
                ) : (
                  <div className="space-y-2">
                    <div className="relative">
                      <FiSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-xs" />
                      <input
                        type="text"
                        placeholder="Rechercher par poste, entreprise, ville..."
                        value={offerSearchQuery}
                        onChange={(e) => setOfferSearchQuery(e.target.value)}
                        className="w-full pl-8 pr-3 py-1.5 bg-slate-900/90 border border-slate-700/80 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
                      />
                    </div>

                    <div className="max-h-48 overflow-y-auto space-y-1.5 pr-1 border border-slate-800/80 bg-slate-900/50 rounded-xl p-1.5">
                      {filteredOffersForModal.length === 0 ? (
                        <div className="text-center py-5 text-xs text-slate-500">
                          Aucune offre trouvée pour &quot;{offerSearchQuery}&quot;
                        </div>
                      ) : (
                        filteredOffersForModal.map((o) => {
                          const isSelected = selectedOfferId === o.id;
                          return (
                            <div
                              key={o.id}
                              onClick={() => setSelectedOfferId(o.id)}
                              className={`cursor-pointer p-2.5 rounded-lg border transition-all flex items-start justify-between gap-2 ${
                                isSelected
                                  ? "bg-blue-600/20 border-blue-500 text-white shadow-sm"
                                  : "bg-slate-900/60 border-slate-800 text-slate-300 hover:border-slate-700 hover:bg-slate-800/60"
                              }`}
                            >
                              <div className="min-w-0 flex-1">
                                <div className="font-medium text-xs truncate">
                                  <span className={isSelected ? "text-blue-300 font-semibold" : "text-slate-200"}>
                                    {o.poste || "Poste sans titre"}
                                  </span>
                                </div>
                                <div className="text-[11px] text-slate-400 truncate mt-0.5 flex items-center gap-2">
                                  <span className="text-slate-300 font-medium">{o.entreprise || "Entreprise"}</span>
                                  <span>•</span>
                                  <span>{o.localisation || "France"}</span>
                                </div>
                              </div>
                              {isSelected && (
                                <div className="p-1 rounded-full bg-blue-500/20 text-blue-400 mt-0.5 shrink-0">
                                  <FiCheckCircle className="text-xs" />
                                </div>
                              )}
                            </div>
                          );
                        })
                      )}
                    </div>
                  </div>
                )}
              </div>


              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Modèle de départ
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <div
                    onClick={() => setSelectedTemplate("sidebar_elegance")}
                    className={`cursor-pointer border rounded-xl p-3 text-xs transition-all ${
                      selectedTemplate === "sidebar_elegance"
                        ? "border-blue-500 bg-blue-900/30 text-white"
                        : "border-slate-800 bg-slate-900/40 text-slate-400 hover:border-slate-700"
                    }`}
                  >
                    <div className="font-semibold mb-0.5">Sidebar Elegance</div>
                    <div className="text-[11px] text-slate-400">2 colonnes, sidebar de compétences & langues</div>
                  </div>

                  <div
                    onClick={() => setSelectedTemplate("executive_minimalist")}
                    className={`cursor-pointer border rounded-xl p-3 text-xs transition-all ${
                      selectedTemplate === "executive_minimalist"
                        ? "border-blue-500 bg-blue-900/30 text-white"
                        : "border-slate-800 bg-slate-900/40 text-slate-400 hover:border-slate-700"
                    }`}
                  >
                    <div className="font-semibold mb-0.5">Executive Minimalist</div>
                    <div className="text-[11px] text-slate-400">1 colonne, ultra-épuré style Linear / Stripe</div>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsGenerateModalOpen(false)}
                  className="px-4 py-2 text-xs text-slate-400 hover:text-white transition-colors"
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  disabled={isGenerating || availableOffers.length === 0}
                  className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-xs font-semibold shadow-md transition-colors"
                >
                  {isGenerating ? <FiRefreshCw className="animate-spin" /> : <FiCheckCircle />}
                  <span>{isGenerating ? "Adaptation IA en cours..." : "Générer mon CV"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ResumesPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center min-h-[50vh]">
          <FiRefreshCw className="animate-spin text-3xl text-blue-400" />
        </div>
      }
    >
      <ResumesContent />
    </Suspense>
  );
}
