"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { coverLetterApi, type JobOfferFilter } from "@/lib/api";

export function useOfferFilters() {
  const [searchTerm, setSearchTerm] = useState("");
  const [locationFilter, setLocationFilter] = useState("");
  const [companyFilter, setCompanyFilter] = useState("");
  const [contractTypeFilter, setContractTypeFilter] = useState("");
  const [workModeFilter, setWorkModeFilter] = useState("");
  const [daysRecentFilter, setDaysRecentFilter] = useState<number | undefined>(undefined);
  const [onlySaved, setOnlySaved] = useState(false);
  const [interactionStatus, setInteractionStatus] = useState<
    "saved" | "applied" | "hidden" | undefined
  >(undefined);
  const [unseenOnly, setUnseenOnly] = useState(false);
  const [minScoreFilter, setMinScoreFilter] = useState<number | undefined>(undefined);
  const [sortFilter, setSortFilter] = useState<"recent" | "relevance">("recent");
  const [sectorFilter, setSectorFilter] = useState<string[]>([]);
  const [companySizeFilter, setCompanySizeFilter] = useState<string[]>([]);
  const [relevanceLevelFilter, setRelevanceLevelFilter] = useState<string[]>([]);

  const [profileRoles, setProfileRoles] = useState<string[]>([]);
  const [profileLocations, setProfileLocations] = useState<string[]>([]);
  const [profileContracts, setProfileContracts] = useState<string[]>([]);
  const [profileEmpty, setProfileEmpty] = useState(false);

  const loadProfileCriteria = useCallback(async () => {
    try {
      const [profile, suggested] = await Promise.all([
        coverLetterApi.getCandidateProfile(),
        coverLetterApi.getSuggestedRoles().catch(() => ({ roles: [] })),
      ]);
      if (!profile) return;

      const prefs = profile.preferences || {};
      const targetRoles = prefs.target_roles || [];
      const allRoles = targetRoles.length > 0 ? targetRoles : suggested.roles || [];
      const locs = prefs.locations || [];
      const contracts = prefs.contract_types || [];

      setProfileRoles(allRoles);
      setProfileLocations(locs);
      setProfileContracts(contracts);
      setProfileEmpty(allRoles.length === 0 && locs.length === 0 && contracts.length === 0);

      if (contracts.length > 0) {
        setContractTypeFilter((prev) => (prev === "" ? "profile_targeted" : prev));
      }
    } catch (err) {
      console.error("Erreur lors de la récupération des critères du profil:", err);
    }
  }, []);

  useEffect(() => {
    loadProfileCriteria();
  }, [loadProfileCriteria]);

  const currentFilters = useMemo((): JobOfferFilter => {
    const f: JobOfferFilter = {};
    if (searchTerm) f.keywords = searchTerm;
    if (locationFilter) f.location = locationFilter;
    if (companyFilter) f.company = companyFilter;
    if (contractTypeFilter) {
      if (contractTypeFilter === "profile_targeted" && profileContracts.length > 0) {
        f.contract_type = profileContracts.map((c) => c.split("/")[0].trim()).join("|");
      } else {
        f.contract_type = contractTypeFilter;
      }
    }
    if (workModeFilter) f.work_mode = workModeFilter;
    if (daysRecentFilter !== undefined) f.days_recent = daysRecentFilter;
    if (onlySaved) f.only_saved = true;
    if (interactionStatus) f.interaction_status = interactionStatus;
    if (unseenOnly) f.unseen_only = true;
    if (minScoreFilter !== undefined) f.min_score = minScoreFilter;
    if (sortFilter !== "recent") f.sort = sortFilter;
    if (sectorFilter.length > 0) f.sector = sectorFilter;
    if (companySizeFilter.length > 0) f.company_size = companySizeFilter;
    if (relevanceLevelFilter.length > 0) f.relevance_level = relevanceLevelFilter;
    return f;
  }, [
    searchTerm,
    locationFilter,
    companyFilter,
    contractTypeFilter,
    profileContracts,
    workModeFilter,
    daysRecentFilter,
    onlySaved,
    interactionStatus,
    unseenOnly,
    minScoreFilter,
    sortFilter,
    sectorFilter,
    companySizeFilter,
    relevanceLevelFilter,
  ]);

  const hasActiveFilters = Boolean(
    searchTerm ||
      locationFilter ||
      companyFilter ||
      contractTypeFilter ||
      workModeFilter ||
      daysRecentFilter !== undefined ||
      onlySaved ||
      interactionStatus ||
      minScoreFilter !== undefined ||
      sortFilter !== "recent" ||
      sectorFilter.length > 0 ||
      companySizeFilter.length > 0 ||
      relevanceLevelFilter.length > 0
  );

  const resetAllFilters = useCallback(() => {
    setSearchTerm("");
    setLocationFilter("");
    setCompanyFilter("");
    setContractTypeFilter("");
    setWorkModeFilter("");
    setDaysRecentFilter(undefined);
    setOnlySaved(false);
    setInteractionStatus(undefined);
    setMinScoreFilter(undefined);
    setSortFilter("recent");
    setSectorFilter([]);
    setCompanySizeFilter([]);
    setRelevanceLevelFilter([]);
  }, []);

  const resetQuickPills = useCallback(() => {
    setOnlySaved(false);
    setInteractionStatus(undefined);
    setDaysRecentFilter(undefined);
    setMinScoreFilter(undefined);
    setUnseenOnly(false);
  }, []);

  return {
    searchTerm,
    setSearchTerm,
    locationFilter,
    setLocationFilter,
    companyFilter,
    setCompanyFilter,
    contractTypeFilter,
    setContractTypeFilter,
    workModeFilter,
    setWorkModeFilter,
    daysRecentFilter,
    setDaysRecentFilter,
    onlySaved,
    setOnlySaved,
    interactionStatus,
    setInteractionStatus,
    unseenOnly,
    setUnseenOnly,
    minScoreFilter,
    setMinScoreFilter,
    sortFilter,
    setSortFilter,
    sectorFilter,
    setSectorFilter,
    companySizeFilter,
    setCompanySizeFilter,
    relevanceLevelFilter,
    setRelevanceLevelFilter,
    profileRoles,
    profileLocations,
    profileContracts,
    profileEmpty,
    currentFilters,
    hasActiveFilters,
    resetAllFilters,
    resetQuickPills,
  };
}

export type OfferFiltersState = ReturnType<typeof useOfferFilters>;
