"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  jobOffersApi,
  type CollectionSchedule,
  type JobOffer,
  type JobOfferFilter,
  type JobOfferStats,
} from "@/lib/api";
import type { PrefilledData } from "@/components/dashboard/NewApplicationModal";
import { ITEMS_PER_PAGE } from "@/lib/offerFormatters";

interface UseOffersCatalogOptions {
  currentFilters: JobOfferFilter;
  onlySaved: boolean;
  unseenOnly: boolean;
  activeTab: "offers" | "stats";
}

export function useOffersCatalog({
  currentFilters,
  onlySaved,
  unseenOnly,
  activeTab,
}: UseOffersCatalogOptions) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [offers, setOffers] = useState<JobOffer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(() => {
    const p = Number(searchParams.get("page"));
    return p > 0 ? p : 1;
  });
  const [totalOffers, setTotalOffers] = useState(0);
  const skipNextPageReset = useRef(true);

  const [regeneratingId, setRegeneratingId] = useState<string | null>(null);
  const [regenerateError, setRegenerateError] = useState<string | null>(null);
  const [stats, setStats] = useState<JobOfferStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [collectionSchedule, setCollectionSchedule] = useState<CollectionSchedule | null>(null);

  const fetchTotalCount = useCallback(async () => {
    try {
      const countData = await jobOffersApi.getCount(currentFilters);
      setTotalOffers(countData.total);
    } catch (err) {
      console.error("Erreur lors du comptage des offres:", err);
      setTotalOffers(0);
    }
  }, [currentFilters]);

  const fetchOffers = useCallback(
    async (silent = false) => {
      if (!silent) setLoading(true);
      setError(null);
      try {
        const data = await jobOffersApi.getAll({
          ...currentFilters,
          limit: ITEMS_PER_PAGE,
          skip: (currentPage - 1) * ITEMS_PER_PAGE,
        });
        setOffers(data);
      } catch (err) {
        setError("Erreur lors du chargement des offres d'emploi");
        console.error("Erreur:", err);
      } finally {
        setLoading(false);
      }
    },
    [currentFilters, currentPage]
  );

  const fetchStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      setStats(await jobOffersApi.getStats());
    } catch (err) {
      console.error("Erreur lors du chargement des statistiques:", err);
    } finally {
      setStatsLoading(false);
    }
  }, []);

  const handleHideOffer = useCallback(
    async (offerId: string) => {
      try {
        await jobOffersApi.setInteraction(offerId, "hidden");
        setOffers((prev) => prev.filter((o) => o.id !== offerId));
        await fetchTotalCount();
      } catch (err) {
        console.error("Erreur lors du masquage de l'offre:", err);
        alert("Erreur lors du masquage de l'offre");
      }
    },
    [fetchTotalCount]
  );

  const handleToggleSaveOffer = useCallback(
    async (offerId: string, currentInteraction?: string | null) => {
      const isCurrentlySaved = currentInteraction === "saved";
      const nextStatus = isCurrentlySaved ? "none" : "saved";
      try {
        await jobOffersApi.setInteraction(offerId, nextStatus);
        setOffers((prev) =>
          prev.map((o) =>
            o.id === offerId ? { ...o, user_interaction: nextStatus === "none" ? null : "saved" } : o
          )
        );
        if (onlySaved && isCurrentlySaved) {
          setOffers((prev) => prev.filter((o) => o.id !== offerId));
          await fetchTotalCount();
        }
      } catch (err) {
        console.error("Erreur lors de la mise à jour des favoris:", err);
      }
    },
    [onlySaved, fetchTotalCount]
  );

  const handleToggleSeen = useCallback(
    async (offerId: string, currentlySeen?: boolean) => {
      const nextSeen = !currentlySeen;
      try {
        await jobOffersApi.setSeen(offerId, nextSeen);
        setOffers((prev) => prev.map((o) => (o.id === offerId ? { ...o, seen: nextSeen } : o)));
        if (unseenOnly && nextSeen) {
          setOffers((prev) => prev.filter((o) => o.id !== offerId));
          await fetchTotalCount();
        }
      } catch (err) {
        console.error("Erreur lors du marquage vu/non vu:", err);
      }
    },
    [unseenOnly, fetchTotalCount]
  );

  const handleRegenerateDescription = useCallback(async (offerId: string) => {
    try {
      setRegeneratingId(offerId);
      setRegenerateError(null);
      const res = await jobOffersApi.regenerateDescription(offerId);
      setOffers((prev) =>
        prev.map((o) =>
          o.id === offerId
            ? {
                ...o,
                ...(res.offer || {}),
                description: res.description || o.description,
                is_active: res.is_active,
              }
            : o
        )
      );
    } catch (err: unknown) {
      console.error("Erreur lors de la régénération:", err);
      const msg =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : null;
      setRegenerateError(msg || "Erreur lors de la régénération de la description");
    } finally {
      setRegeneratingId(null);
    }
  }, []);

  const handleApplyToOffer = useCallback((offer: JobOffer) => {
    const prefilledData: PrefilledData = {
      company: offer.entreprise,
      position: offer.poste,
      location: offer.localisation,
      url: offer.url,
      offer_id: offer.id,
      description:
        offer.description && offer.description !== "Non spécifié" ? offer.description : undefined,
    };
    window.dispatchEvent(new CustomEvent("open-application-modal", { detail: prefilledData }));
  }, []);

  const handlePageClick = useCallback((page: number) => {
    setCurrentPage(page);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  useEffect(() => {
    if (activeTab === "offers") fetchTotalCount();
  }, [fetchTotalCount, activeTab]);

  useEffect(() => {
    if (activeTab === "offers") fetchOffers();
    else fetchStats();
  }, [fetchOffers, fetchStats, activeTab]);

  useEffect(() => {
    jobOffersApi
      .getCollectionSchedule()
      .then(setCollectionSchedule)
      .catch((err) => console.error("Erreur calendrier de collecte:", err));
  }, []);

  useEffect(() => {
    const onCreated = () => {
      fetchOffers(true);
      fetchTotalCount();
    };
    window.addEventListener("application-created", onCreated);
    return () => window.removeEventListener("application-created", onCreated);
  }, [fetchOffers, fetchTotalCount]);

  useEffect(() => {
    if (skipNextPageReset.current) {
      skipNextPageReset.current = false;
      return;
    }
    setCurrentPage(1);
  }, [currentFilters]);

  useEffect(() => {
    router.replace(currentPage > 1 ? `/offers?page=${currentPage}` : "/offers", { scroll: false });
  }, [currentPage, router]);

  useEffect(() => {
    const totalPages = Math.ceil(totalOffers / ITEMS_PER_PAGE);
    if (totalPages > 0 && currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [totalOffers, currentPage]);

  return {
    offers,
    loading,
    error,
    currentPage,
    totalOffers,
    regeneratingId,
    regenerateError,
    setRegenerateError,
    stats,
    statsLoading,
    collectionSchedule,
    fetchOffers,
    handleHideOffer,
    handleToggleSaveOffer,
    handleToggleSeen,
    handleRegenerateDescription,
    handleApplyToOffer,
    handlePageClick,
  };
}
