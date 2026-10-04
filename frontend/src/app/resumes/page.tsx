"use client";

import { useEffect, useState, Suspense, useCallback } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import {
  FiFileText,
  FiSearch,
  FiPlus,
  FiRefreshCw,
  FiFilter,
  FiCheckCircle,
  FiBriefcase,
  FiMapPin,
  FiX,
} from "react-icons/fi";
import { TailoredResume, TailoredCVSchema } from "@/types/resume";
import { resumeApi, jobOffersApi, type JobOffer } from "@/lib/api";
import ResumeCard from "@/components/resumes/ResumeCard";
import ResumePreviewModal from "@/components/resumes/ResumePreviewModal";
import {
  CV_TEMPLATES,
  DEFAULT_ACCENT,
  DEFAULT_TEMPLATE,
  resolveAccentKey,
  resolveTemplateKey,
  type CvAccentKey,
  type CvTemplateKey,
  type ResumeAppearance,
} from "@/lib/cvTemplates";
import AccentSwatches from "@/components/resumes/AccentSwatches";

function ResumesContent() {
  const router = useRouter();
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
  const [selectedOffer, setSelectedOffer] = useState<JobOffer | null>(null);
  const [selectedOfferId, setSelectedOfferId] = useState<string>("");
  const [isSearchingOffer, setIsSearchingOffer] = useState<boolean>(false);
  const [offerSearchQuery, setOfferSearchQuery] = useState<string>("");
  const [searchResults, setSearchResults] = useState<JobOffer[]>([]);
  const [isSearchingOffers, setIsSearchingOffers] = useState<boolean>(false);
  const [isLoadingSelectedOffer, setIsLoadingSelectedOffer] = useState<boolean>(false);
  const [selectedTemplate, setSelectedTemplate] = useState<CvTemplateKey>(DEFAULT_TEMPLATE);
  const [selectedAccent, setSelectedAccent] = useState<CvAccentKey>(DEFAULT_ACCENT);
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

  const loadDefaultSuggestions = useCallback(async () => {
    setIsSearchingOffers(true);
    try {
      const suggestions = await jobOffersApi.getAll({ limit: 10 });
      setSearchResults(suggestions);
    } catch (err) {
      console.error("Failed to fetch suggestions:", err);
    } finally {
      setIsSearchingOffers(false);
    }
  }, []);

  const openGenerateModal = useCallback(async (initialOfferId?: string) => {
    setIsGenerateModalOpen(true);
    setGenerateError(null);
    setOfferSearchQuery("");

    if (initialOfferId) {
      setSelectedOfferId(initialOfferId);
      setIsSearchingOffer(false);
      setIsLoadingSelectedOffer(true);
      try {
        const offer = await jobOffersApi.getById(initialOfferId);
        setSelectedOffer(offer);
      } catch (err) {
        console.error("Failed to fetch preselected offer:", err);
        setSelectedOffer(null);
        setIsSearchingOffer(true);
        loadDefaultSuggestions();
      } finally {
        setIsLoadingSelectedOffer(false);
      }
    } else {
      setSelectedOffer(null);
      setSelectedOfferId("");
      setIsSearchingOffer(true);
      loadDefaultSuggestions();
    }
  }, [loadDefaultSuggestions]);

  const closeGenerateModal = () => {
    setIsGenerateModalOpen(false);
    setGenerateError(null);
    if (searchParams.get("generate_offer_id")) {
      router.replace("/resumes", { scroll: false });
    }
  };

  useEffect(() => {
    if (preselectedOfferId) {
      openGenerateModal(preselectedOfferId);
    }
  }, [preselectedOfferId, openGenerateModal]);

  useEffect(() => {
    if (!isGenerateModalOpen || !isSearchingOffer) return;

    const query = offerSearchQuery.trim();
    if (!query) {
      loadDefaultSuggestions();
      return;
    }

    const timer = setTimeout(async () => {
      setIsSearchingOffers(true);
      try {
        const results = await jobOffersApi.getAll({ keywords: query, limit: 15 });
        setSearchResults(results);
      } catch (err) {
        console.error("Error searching job offers:", err);
      } finally {
        setIsSearchingOffers(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [offerSearchQuery, isGenerateModalOpen, isSearchingOffer, loadDefaultSuggestions]);

  const handleGenerateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedOfferId) return;

    setIsGenerating(true);
    setGenerateError(null);
    try {
      const newResume = await resumeApi.generate({
        offer_id: selectedOfferId,
        template: selectedTemplate,
        accent: selectedAccent,
        with_photo: false,
      });
      // Réinitialiser les filtres pour garantir que le nouveau CV apparaisse au premier plan
      setSearchQuery("");
      setTemplateFilter("all");
      closeGenerateModal();
      setActiveResumeForPreview(newResume);
      // Recharger la liste fraîche depuis le serveur pour synchroniser la page
      await fetchResumes();
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

  const handleUpdateAppearance = async (id: string, appearance: ResumeAppearance) => {
    try {
      const updated = await resumeApi.update(id, {
        template: appearance.template,
        accent: appearance.accent,
        with_photo: appearance.withPhoto,
      });
      setResumes((prev) => prev.map((r) => ((r.id || r._id) === id ? updated : r)));
      setActiveResumeForPreview((current) =>
        current && (current.id || current._id) === id ? updated : current
      );
    } catch (err) {
      console.error("Failed to update resume appearance:", err);
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
        template: resolveTemplateKey(resume.template),
        accent: resolveAccentKey(resume.accent),
        with_photo: resume.with_photo,
        application_id: resume.application_id,
      });
      if ((activeResumeForPreview?.id || activeResumeForPreview?._id) === (resume.id || resume._id)) {
        setActiveResumeForPreview(newResume);
      }
      await fetchResumes();
    } catch (err: unknown) {
      console.error("Failed to regenerate resume:", err);
      const msg = err instanceof Error ? err.message : "Erreur lors de la régénération du CV.";
      alert(msg);
      throw err;
    }
  };

  // Filtering
  const filteredResumes = resumes.filter((r) => {
    const role = (r.target_role || "").toLowerCase();
    const company = (r.target_company || "").toLowerCase();
    const query = searchQuery.trim().toLowerCase();
    const matchesSearch = !query || role.includes(query) || company.includes(query);
    const matchesTemplate = templateFilter === "all" || resolveTemplateKey(r.template) === templateFilter;
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
            {CV_TEMPLATES.map((tmpl) => (
              <option key={tmpl.key} value={tmpl.key}>{tmpl.label}</option>
            ))}
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
        onUpdateAppearance={handleUpdateAppearance}
        onUpdateContent={handleUpdateResumeContent}
        onRegenerate={handleRegenerateResume}
        initialTab={modalInitialTab}
      />

      {/* Generator Modal */}
      {isGenerateModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
          <div className="bg-[#152238] border border-slate-700 rounded-2xl shadow-2xl w-full max-w-lg p-6 text-slate-100 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-start justify-between mb-1">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <FiFileText className="text-blue-400" />
                <span>Générer un CV sur-mesure</span>
              </h2>
              <button
                type="button"
                onClick={closeGenerateModal}
                className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
                title="Fermer"
              >
                <FiX className="text-base" />
              </button>
            </div>
            <p className="text-xs text-slate-400 mb-5">
              Sélectionnez l&apos;offre cible pour laquelle adapter vos expériences et vos compétences.
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
                    Offre d&apos;emploi cible
                  </label>
                  {selectedOffer && !isSearchingOffer && (
                    <button
                      type="button"
                      onClick={() => {
                        setIsSearchingOffer(true);
                        loadDefaultSuggestions();
                      }}
                      className="text-[11px] text-blue-400 hover:text-blue-300 font-medium transition-colors"
                    >
                      Changer d&apos;offre
                    </button>
                  )}
                </div>

                {isLoadingSelectedOffer ? (
                  <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60 flex items-center justify-center gap-2 text-xs text-slate-400">
                    <FiRefreshCw className="animate-spin text-blue-400 text-sm" />
                    <span>Chargement de l&apos;offre cible...</span>
                  </div>
                ) : selectedOffer && !isSearchingOffer ? (
                  <div className="rounded-xl border border-blue-500/40 bg-gradient-to-br from-blue-950/30 to-slate-900/80 p-3.5 relative shadow-md">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-500/20 text-blue-300 border border-blue-500/30">
                            <FiCheckCircle className="text-xs" />
                            Offre sélectionnée
                          </span>
                          {selectedOffer.type_contrat && (
                            <span className="text-[10px] text-slate-400 font-medium px-2 py-0.5 rounded bg-slate-800/80 border border-slate-700/60">
                              {selectedOffer.type_contrat}
                            </span>
                          )}
                          {selectedOffer.mode_travail && (
                            <span className="text-[10px] text-slate-400 font-medium px-2 py-0.5 rounded bg-slate-800/80 border border-slate-700/60">
                              {selectedOffer.mode_travail}
                            </span>
                          )}
                        </div>
                        <h3 className="font-semibold text-xs text-white truncate">
                          {selectedOffer.poste || "Poste sans titre"}
                        </h3>
                        <div className="text-[11px] text-slate-400 truncate mt-1 flex items-center gap-2">
                          <span className="text-slate-300 font-medium">{selectedOffer.entreprise || "Entreprise"}</span>
                          {selectedOffer.localisation && (
                            <>
                              <span>•</span>
                              <span>{selectedOffer.localisation}</span>
                            </>
                          )}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          setIsSearchingOffer(true);
                          loadDefaultSuggestions();
                        }}
                        className="text-[11px] px-2.5 py-1.5 rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors shrink-0"
                        title="Rechercher une autre offre"
                      >
                        Modifier
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <div className="relative">
                      <FiSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-xs" />
                      <input
                        type="text"
                        placeholder="Rechercher par métier, mots-clés, entreprise..."
                        value={offerSearchQuery}
                        onChange={(e) => setOfferSearchQuery(e.target.value)}
                        className="w-full pl-8 pr-8 py-1.5 bg-slate-900/90 border border-slate-700/80 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
                        autoFocus
                      />
                      {isSearchingOffers && (
                        <FiRefreshCw className="absolute right-3 top-1/2 -translate-y-1/2 text-blue-400 text-xs animate-spin" />
                      )}
                    </div>

                    <div className="max-h-48 overflow-y-auto space-y-1.5 pr-1 border border-slate-800/80 bg-slate-900/50 rounded-xl p-1.5">
                      {searchResults.length === 0 ? (
                        <div className="text-center py-6 text-xs text-slate-500">
                          {isSearchingOffers ? "Recherche en cours..." : "Aucune offre trouvée"}
                        </div>
                      ) : (
                        searchResults.map((o) => {
                          const isSelected = selectedOfferId === o.id;
                          return (
                            <div
                              key={o.id}
                              onClick={() => {
                                setSelectedOffer(o);
                                setSelectedOfferId(o.id);
                                setIsSearchingOffer(false);
                              }}
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
                                  {o.localisation && (
                                    <>
                                      <span>•</span>
                                      <span>{o.localisation}</span>
                                    </>
                                  )}
                                </div>
                              </div>
                              <span className="text-[11px] text-blue-400 font-medium shrink-0 pt-0.5">
                                Choisir
                              </span>
                            </div>
                          );
                        })
                      )}
                    </div>
                  </div>
                )}
              </div>

              <div>
                <div className="block text-xs font-semibold text-slate-300 mb-1.5">Modèle</div>
                <div className="grid grid-cols-2 gap-3">
                  {CV_TEMPLATES.map((tmpl) => {
                    const selected = selectedTemplate === tmpl.key;
                    return (
                      <button
                        key={tmpl.key}
                        type="button"
                        onClick={() => setSelectedTemplate(tmpl.key)}
                        aria-pressed={selected}
                        className={`text-left border rounded-xl p-3 text-xs transition-all ${
                          selected
                            ? "border-blue-500 bg-blue-900/30 text-white"
                            : "border-slate-800 bg-slate-900/40 text-slate-400 hover:border-slate-700"
                        }`}
                      >
                        <div className="font-semibold mb-0.5">{tmpl.label}</div>
                        <div className="text-[11px] text-slate-400">{tmpl.hint}</div>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div>
                <div className="block text-xs font-semibold text-slate-300 mb-1.5">Couleur</div>
                <AccentSwatches value={selectedAccent} onChange={setSelectedAccent} />
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
                <button
                  type="button"
                  onClick={closeGenerateModal}
                  className="px-4 py-2 text-xs text-slate-400 hover:text-white transition-colors"
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  disabled={isGenerating || !selectedOfferId}
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
