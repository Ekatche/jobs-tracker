"use client";

import {
  FiFileText,
  FiSearch,
  FiRefreshCw,
  FiCheckCircle,
  FiX,
} from "react-icons/fi";
import { type JobOffer } from "@/lib/api";
import {
  CV_TEMPLATES,
  type CvAccentKey,
  type CvTemplateKey,
} from "@/lib/cvTemplates";
import AccentSwatches from "@/components/resumes/AccentSwatches";

interface ResumeGeneratorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (e: React.FormEvent) => void;
  generateError: string | null;
  selectedOffer: JobOffer | null;
  selectedOfferId: string;
  isSearchingOffer: boolean;
  isLoadingSelectedOffer: boolean;
  offerSearchQuery: string;
  searchResults: JobOffer[];
  isSearchingOffers: boolean;
  selectedTemplate: CvTemplateKey;
  selectedAccent: CvAccentKey;
  isGenerating: boolean;
  onSearchQueryChange: (q: string) => void;
  onStartOfferSearch: () => void;
  onSelectOffer: (offer: JobOffer) => void;
  onTemplateChange: (tmpl: CvTemplateKey) => void;
  onAccentChange: (accent: CvAccentKey) => void;
}

export default function ResumeGeneratorModal({
  isOpen,
  onClose,
  onSubmit,
  generateError,
  selectedOffer,
  selectedOfferId,
  isSearchingOffer,
  isLoadingSelectedOffer,
  offerSearchQuery,
  searchResults,
  isSearchingOffers,
  selectedTemplate,
  selectedAccent,
  isGenerating,
  onSearchQueryChange,
  onStartOfferSearch,
  onSelectOffer,
  onTemplateChange,
  onAccentChange,
}: ResumeGeneratorModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
      <div className="bg-[#152238] border border-slate-700 rounded-2xl shadow-2xl w-full max-w-lg p-6 text-slate-100 animate-in fade-in zoom-in-95 duration-200">
        <div className="flex items-start justify-between mb-1">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <FiFileText className="text-blue-400" />
            <span>Générer un CV sur-mesure</span>
          </h2>
          <button
            type="button"
            onClick={onClose}
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

        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-xs font-semibold text-slate-300">
                Offre d&apos;emploi cible
              </label>
              {selectedOffer && !isSearchingOffer && (
                <button
                  type="button"
                  onClick={onStartOfferSearch}
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
                      <span className="text-slate-300 font-medium">
                        {selectedOffer.entreprise || "Entreprise"}
                      </span>
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
                    onClick={onStartOfferSearch}
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
                    onChange={(e) => onSearchQueryChange(e.target.value)}
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
                          onClick={() => onSelectOffer(o)}
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
                              <span className="text-slate-300 font-medium">
                                {o.entreprise || "Entreprise"}
                              </span>
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
                    onClick={() => onTemplateChange(tmpl.key)}
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
            <AccentSwatches value={selectedAccent} onChange={onAccentChange} />
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
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
  );
}
