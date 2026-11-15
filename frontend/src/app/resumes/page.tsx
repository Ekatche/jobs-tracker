"use client";

import { Suspense } from "react";
import {
  FiFileText,
  FiSearch,
  FiPlus,
  FiRefreshCw,
  FiFilter,
} from "react-icons/fi";
import ResumeCard from "@/components/resumes/ResumeCard";
import ResumePreviewModal from "@/components/resumes/ResumePreviewModal";
import ResumeGeneratorModal from "@/components/resumes/ResumeGeneratorModal";
import { CV_TEMPLATES } from "@/lib/cvTemplates";
import { useResumesPage } from "@/hooks/useResumesPage";

function ResumesContent() {
  const {
    resumes,
    filteredResumes,
    loading,
    searchQuery,
    setSearchQuery,
    templateFilter,
    setTemplateFilter,
    activeResumeForPreview,
    setActiveResumeForPreview,
    modalInitialTab,
    setModalInitialTab,
    isGenerateModalOpen,
    selectedOffer,
    setSelectedOffer,
    selectedOfferId,
    setSelectedOfferId,
    isSearchingOffer,
    setIsSearchingOffer,
    offerSearchQuery,
    setOfferSearchQuery,
    searchResults,
    isSearchingOffers,
    isLoadingSelectedOffer,
    selectedTemplate,
    setSelectedTemplate,
    selectedAccent,
    setSelectedAccent,
    isGenerating,
    generateError,
    loadDefaultSuggestions,
    openGenerateModal,
    closeGenerateModal,
    handleGenerateSubmit,
    handleDeleteResume,
    handleUpdateAppearance,
    handleUpdateResumeContent,
    handleRegenerateResume,
  } = useResumesPage();

  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-white flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-blue-600/20 text-blue-400 border border-blue-500/30 shadow-inner">
              <FiFileText className="text-2xl" />
            </div>
            <span>Mes CV Personnalisés</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Générez des CV A4 vectoriels sur-mesure alignés sur chaque offre d&apos;emploi et certifiés anti-hallucination.
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
              <option key={tmpl.key} value={tmpl.key}>
                {tmpl.label}
              </option>
            ))}
          </select>
        </div>
      </div>

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

      <ResumePreviewModal
        resume={activeResumeForPreview}
        isOpen={!!activeResumeForPreview}
        onClose={() => setActiveResumeForPreview(null)}
        onUpdateAppearance={handleUpdateAppearance}
        onUpdateContent={handleUpdateResumeContent}
        onRegenerate={handleRegenerateResume}
        initialTab={modalInitialTab}
      />

      <ResumeGeneratorModal
        isOpen={isGenerateModalOpen}
        onClose={closeGenerateModal}
        onSubmit={handleGenerateSubmit}
        generateError={generateError}
        selectedOffer={selectedOffer}
        selectedOfferId={selectedOfferId}
        isSearchingOffer={isSearchingOffer}
        isLoadingSelectedOffer={isLoadingSelectedOffer}
        offerSearchQuery={offerSearchQuery}
        searchResults={searchResults}
        isSearchingOffers={isSearchingOffers}
        selectedTemplate={selectedTemplate}
        selectedAccent={selectedAccent}
        isGenerating={isGenerating}
        onSearchQueryChange={setOfferSearchQuery}
        onStartOfferSearch={() => {
          setIsSearchingOffer(true);
          loadDefaultSuggestions();
        }}
        onSelectOffer={(o) => {
          setSelectedOffer(o);
          setSelectedOfferId(o.id);
          setIsSearchingOffer(false);
        }}
        onTemplateChange={setSelectedTemplate}
        onAccentChange={setSelectedAccent}
      />
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
