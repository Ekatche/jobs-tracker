"use client";

import React, { useState, useEffect, useCallback } from "react";
import { CandidatePreferences, RemotePolicy } from "@/types/coverLetter";
import { coverLetterApi } from "@/lib/api";
import { toggleStringValue } from "@/components/profile/targeting/targetingOptions";

export type TargetingSectionKey =
  | "roles"
  | "location"
  | "salary"
  | "contract"
  | "sectors"
  | "excluded";

/**
 * Manages targeting preferences form state, hydration, chip toggles, and persistence.
 */
export function useTargetingPreferences(
  initialPreferences?: CandidatePreferences,
  onSave?: (preferences: CandidatePreferences) => Promise<void>
) {
  const [targetRoles, setTargetRoles] = useState<string[]>([]);
  const [suggestedRoles, setSuggestedRoles] = useState<string[]>([]);
  const [newRoleInput, setNewRoleInput] = useState("");
  const [searchActive, setSearchActive] = useState<boolean>(true);

  const [locations, setLocations] = useState<string[]>([]);
  const [newLocationInput, setNewLocationInput] = useState("");

  const [remotePolicy, setRemotePolicy] = useState<RemotePolicy>("flexible");
  const [seniorityLevels, setSeniorityLevels] = useState<string[]>([]);

  const [minSalary, setMinSalary] = useState<string>("");
  const [targetSalary, setTargetSalary] = useState<string>("");
  const [currency, setCurrency] = useState("EUR");

  const [contractTypes, setContractTypes] = useState<string[]>([]);
  const [noticePeriod, setNoticePeriod] = useState<string>("");
  const [workAuthorization, setWorkAuthorization] = useState<string>("");

  const [preferredIndustries, setPreferredIndustries] = useState<string[]>([]);
  const [preferredCompanySizes, setPreferredCompanySizes] = useState<string[]>([]);

  const [excludedKeywords, setExcludedKeywords] = useState<string[]>([]);
  const [newExcludedInput, setNewExcludedInput] = useState("");

  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [isInternalSaving, setIsInternalSaving] = useState(false);

  // Progressive disclosure: only roles starts expanded
  const [openSections, setOpenSections] = useState<Record<TargetingSectionKey, boolean>>({
    roles: true,
    location: false,
    salary: false,
    contract: false,
    sectors: false,
    excluded: false,
  });

  const toggleSection = (key: TargetingSectionKey) => {
    setOpenSections((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const applyPreferences = useCallback((pref: CandidatePreferences) => {
    setTargetRoles(pref.target_roles || []);
    setLocations(pref.locations || []);
    setRemotePolicy(pref.remote_policy || "flexible");
    const initSeniority =
      pref.seniority_levels && pref.seniority_levels.length > 0
        ? pref.seniority_levels
        : pref.seniority_level
        ? [pref.seniority_level]
        : [];
    setSeniorityLevels(initSeniority);
    setMinSalary(pref.min_salary ? String(pref.min_salary) : "");
    setTargetSalary(pref.target_salary ? String(pref.target_salary) : "");
    setCurrency(pref.currency || "EUR");
    setContractTypes(pref.contract_types || []);
    setNoticePeriod(pref.notice_period || "");
    setWorkAuthorization(pref.work_authorization || "");
    setPreferredIndustries(pref.preferred_industries || []);
    setPreferredCompanySizes(pref.preferred_company_sizes || []);
    setExcludedKeywords(pref.excluded_keywords || []);
    setSearchActive(pref.search_active ?? true);
  }, []);

  useEffect(() => {
    if (initialPreferences) {
      applyPreferences(initialPreferences);
    }
    coverLetterApi
      .getCandidateProfile()
      .then((data) => {
        if (!initialPreferences && data && data.preferences) {
          applyPreferences(data.preferences);
        }
      })
      .catch(() => {});
    coverLetterApi
      .getSuggestedRoles()
      .then((data) => {
        setSuggestedRoles(data.roles || []);
      })
      .catch(() => {});
  }, [initialPreferences, applyPreferences]);

  const handleAddRole = (e: React.KeyboardEvent | React.MouseEvent) => {
    if ("key" in e && e.key !== "Enter") return;
    e.preventDefault();
    const val = newRoleInput.trim();
    if (val && !targetRoles.some((r) => r.toLowerCase() === val.toLowerCase())) {
      setTargetRoles([...targetRoles, val]);
      setNewRoleInput("");
    }
  };

  const handleAddLocation = (e: React.KeyboardEvent | React.MouseEvent) => {
    if ("key" in e && e.key !== "Enter") return;
    e.preventDefault();
    const val = newLocationInput.trim();
    if (val && !locations.some((l) => l.toLowerCase() === val.toLowerCase())) {
      setLocations([...locations, val]);
      setNewLocationInput("");
    }
  };

  const handleAddExcluded = (e: React.KeyboardEvent | React.MouseEvent) => {
    if ("key" in e && e.key !== "Enter") return;
    e.preventDefault();
    const val = newExcludedInput.trim();
    if (val && !excludedKeywords.some((k) => k.toLowerCase() === val.toLowerCase())) {
      setExcludedKeywords([...excludedKeywords, val]);
      setNewExcludedInput("");
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaveError(null);
    setSaveSuccess(false);

    const payload: CandidatePreferences = {
      target_roles: targetRoles,
      seniority_level: seniorityLevels[0] || undefined,
      seniority_levels: seniorityLevels,
      locations,
      remote_policy: remotePolicy,
      min_salary: minSalary ? parseInt(minSalary, 10) : null,
      target_salary: targetSalary ? parseInt(targetSalary, 10) : null,
      currency,
      contract_types: contractTypes,
      notice_period: noticePeriod || undefined,
      work_authorization: workAuthorization || undefined,
      preferred_industries: preferredIndustries,
      preferred_company_sizes: preferredCompanySizes,
      excluded_keywords: excludedKeywords,
      search_active: searchActive,
    };

    try {
      setIsInternalSaving(true);
      if (onSave) {
        await onSave(payload);
      } else {
        await coverLetterApi.updateCandidatePreferences(payload);
      }
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 4000);
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : "Erreur lors de l'enregistrement");
    } finally {
      setIsInternalSaving(false);
    }
  };

  return {
    targetRoles,
    setTargetRoles,
    suggestedRoles,
    newRoleInput,
    setNewRoleInput,
    searchActive,
    setSearchActive,
    locations,
    setLocations,
    newLocationInput,
    setNewLocationInput,
    remotePolicy,
    setRemotePolicy,
    seniorityLevels,
    setSeniorityLevels,
    minSalary,
    setMinSalary,
    targetSalary,
    setTargetSalary,
    currency,
    setCurrency,
    contractTypes,
    setContractTypes,
    noticePeriod,
    setNoticePeriod,
    workAuthorization,
    setWorkAuthorization,
    preferredIndustries,
    setPreferredIndustries,
    preferredCompanySizes,
    setPreferredCompanySizes,
    excludedKeywords,
    setExcludedKeywords,
    newExcludedInput,
    setNewExcludedInput,
    saveSuccess,
    setSaveSuccess,
    saveError,
    setSaveError,
    isInternalSaving,
    openSections,
    toggleSection,
    handleAddRole,
    handleRemoveRole: (role: string) => setTargetRoles(targetRoles.filter((r) => r !== role)),
    handleAddLocation,
    handleRemoveLocation: (loc: string) => setLocations(locations.filter((l) => l !== loc)),
    handleToggleContract: (contract: string) =>
      setContractTypes(toggleStringValue(contractTypes, contract)),
    handleAddExcluded,
    handleRemoveExcluded: (word: string) =>
      setExcludedKeywords(excludedKeywords.filter((k) => k !== word)),
    handleToggleSeniority: (val: string) =>
      setSeniorityLevels(toggleStringValue(seniorityLevels, val)),
    handleSubmit,
  };
}
