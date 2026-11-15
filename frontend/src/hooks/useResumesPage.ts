"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { TailoredResume, TailoredCVSchema } from "@/types/resume";
import { resumeApi, jobOffersApi, type JobOffer } from "@/lib/api";
import {
  DEFAULT_ACCENT,
  DEFAULT_TEMPLATE,
  resolveAccentKey,
  resolveTemplateKey,
  type CvAccentKey,
  type CvTemplateKey,
  type ResumeAppearance,
} from "@/lib/cvTemplates";

/**
 * Manages tailored resume list, generation modal search/submission, and resume mutations.
 */
export function useResumesPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const preselectedOfferId = searchParams.get("generate_offer_id");

  const [resumes, setResumes] = useState<TailoredResume[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [templateFilter, setTemplateFilter] = useState<string>("all");
  const [activeResumeForPreview, setActiveResumeForPreview] =
    useState<TailoredResume | null>(null);
  const [modalInitialTab, setModalInitialTab] = useState<"preview" | "edit">("preview");

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

  const fetchResumes = useCallback(async () => {
    setLoading(true);
    try {
      const data = await resumeApi.getAll();
      setResumes(data);
    } catch (err) {
      console.error("Failed to load resumes:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchResumes();
  }, [fetchResumes]);

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

  const openGenerateModal = useCallback(
    async (initialOfferId?: string) => {
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
    },
    [loadDefaultSuggestions]
  );

  const closeGenerateModal = useCallback(() => {
    setIsGenerateModalOpen(false);
    setGenerateError(null);
    if (searchParams.get("generate_offer_id")) {
      router.replace("/resumes", { scroll: false });
    }
  }, [router, searchParams]);

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
      setSearchQuery("");
      setTemplateFilter("all");
      closeGenerateModal();
      setActiveResumeForPreview(newResume);
      await fetchResumes();
    } catch (err: unknown) {
      console.error("CV generation failed:", err);
      const errorDetail =
        err instanceof Error
          ? err.message
          : err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
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

  const filteredResumes = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return resumes.filter((r) => {
      const role = (r.target_role || "").toLowerCase();
      const company = (r.target_company || "").toLowerCase();
      const matchesSearch = !query || role.includes(query) || company.includes(query);
      const matchesTemplate =
        templateFilter === "all" || resolveTemplateKey(r.template) === templateFilter;
      return matchesSearch && matchesTemplate;
    });
  }, [resumes, searchQuery, templateFilter]);

  return {
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
  };
}
