"use client";

import React, { useState, useEffect } from "react";
import {
  FiTarget,
  FiMapPin,
  FiDollarSign,
  FiBriefcase,
  FiSlash,
  FiClock,
  FiCheckCircle,
  FiAlertCircle,
  FiSave,
  FiPlus,
  FiX,
  FiShield,
  FiCheck,
} from "react-icons/fi";
import { CandidatePreferences, RemotePolicy } from "@/types/coverLetter";
import { coverLetterApi } from "@/lib/api";

interface TargetingPreferencesSectionProps {
  initialPreferences?: CandidatePreferences;
  onSave?: (preferences: CandidatePreferences) => Promise<void>;
  isSaving?: boolean;
}

const REMOTE_OPTIONS: { value: RemotePolicy; label: string; desc: string; icon: string }[] = [
  { value: "full_remote", label: "Full Remote", desc: "100% télétravail", icon: "🏠" },
  { value: "hybrid", label: "Hybride", desc: "2 à 3 jours de remote / semaine", icon: "🏢" },
  { value: "on_site", label: "Sur site", desc: "Présentiel complet", icon: "📍" },
  { value: "flexible", label: "Flexible", desc: "Ouvert à toutes les options", icon: "🌐" },
];

const CONTRACT_OPTIONS = ["CDI", "Freelance / Prestation", "CDD", "Alternance", "Stage"];
const NOTICE_OPTIONS = ["Immédiat", "1 mois", "2 mois", "3 mois", "Plus de 3 mois"];
const SENIORITY_OPTIONS = [
  { value: "junior", label: "Junior", desc: "0-2 ans d'expérience" },
  { value: "mid", label: "Intermédiaire", desc: "3-5 ans d'expérience" },
  { value: "senior", label: "Senior", desc: "6-8 ans d'expérience" },
  { value: "lead", label: "Lead / Staff", desc: "8+ ans d'expérience" },
  { value: "head_of", label: "Direction / Head of", desc: "Management & stratégie" },
];

const SUGGESTED_LOCATIONS = [
  "Paris",
  "Lyon",
  "Toulouse",
  "Nantes",
  "Bordeaux",
  "Full Remote",
];

export default function TargetingPreferencesSection({
  initialPreferences,
  onSave,
  isSaving = false,
}: TargetingPreferencesSectionProps) {
  const [targetRoles, setTargetRoles] = useState<string[]>([]);
  const [suggestedRoles, setSuggestedRoles] = useState<string[]>([]);
  const [newRoleInput, setNewRoleInput] = useState("");

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

  const [excludedKeywords, setExcludedKeywords] = useState<string[]>([]);
  const [newExcludedInput, setNewExcludedInput] = useState("");

  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [isInternalSaving, setIsInternalSaving] = useState(false);

  const applyPreferences = (pref: CandidatePreferences) => {
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
    setExcludedKeywords(pref.excluded_keywords || []);
  };

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
  }, [initialPreferences]);

  const handleAddRole = (e: React.KeyboardEvent | React.MouseEvent) => {
    if ("key" in e && e.key !== "Enter") return;
    e.preventDefault();
    const val = newRoleInput.trim();
    if (val && !targetRoles.some((r) => r.toLowerCase() === val.toLowerCase())) {
      setTargetRoles([...targetRoles, val]);
      setNewRoleInput("");
    }
  };

  const handleRemoveRole = (role: string) => {
    setTargetRoles(targetRoles.filter((r) => r !== role));
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

  const handleRemoveLocation = (loc: string) => {
    setLocations(locations.filter((l) => l !== loc));
  };

  const handleToggleContract = (contract: string) => {
    if (contractTypes.includes(contract)) {
      setContractTypes(contractTypes.filter((c) => c !== contract));
    } else {
      setContractTypes([...contractTypes, contract]);
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

  const handleRemoveExcluded = (keyword: string) => {
    setExcludedKeywords(excludedKeywords.filter((k) => k !== keyword));
  };

  const handleToggleSeniority = (val: string) => {
    if (seniorityLevels.includes(val)) {
      setSeniorityLevels(seniorityLevels.filter((s) => s !== val));
    } else {
      setSeniorityLevels([...seniorityLevels, val]);
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
      locations: locations,
      remote_policy: remotePolicy,
      min_salary: minSalary ? parseInt(minSalary, 10) : null,
      target_salary: targetSalary ? parseInt(targetSalary, 10) : null,
      currency: currency,
      contract_types: contractTypes,
      notice_period: noticePeriod || undefined,
      work_authorization: workAuthorization || undefined,
      excluded_keywords: excludedKeywords,
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
      const errorMsg = err instanceof Error ? err.message : "Erreur lors de l'enregistrement";
      setSaveError(errorMsg);
    } finally {
      setIsInternalSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-8">
      {/* Floating Toast Notification */}
      {saveSuccess && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-3 p-4 bg-emerald-950/90 border border-emerald-500/50 text-emerald-100 rounded-2xl shadow-2xl backdrop-blur-md animate-in fade-in slide-in-from-bottom-5 duration-300">
          <div className="p-2 bg-emerald-500/20 text-emerald-400 rounded-xl">
            <FiCheckCircle className="w-5 h-5" />
          </div>
          <div>
            <p className="text-sm font-bold text-white">Préférences enregistrées</p>
            <p className="text-xs text-emerald-300/80">Critères de ciblage et filtres mis à jour avec succès.</p>
          </div>
          <button
            type="button"
            onClick={() => setSaveSuccess(false)}
            className="ml-2 text-emerald-400 hover:text-emerald-200"
          >
            <FiX className="w-4 h-4" />
          </button>
        </div>
      )}

      {saveError && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-3 p-4 bg-rose-950/90 border border-rose-500/50 text-rose-100 rounded-2xl shadow-2xl backdrop-blur-md animate-in fade-in slide-in-from-bottom-5 duration-300">
          <div className="p-2 bg-rose-500/20 text-rose-400 rounded-xl">
            <FiAlertCircle className="w-5 h-5" />
          </div>
          <div>
            <p className="text-sm font-bold text-white">Erreur d'enregistrement</p>
            <p className="text-xs text-rose-300/80">{saveError}</p>
          </div>
          <button
            type="button"
            onClick={() => setSaveError(null)}
            className="ml-2 text-rose-400 hover:text-rose-200"
          >
            <FiX className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Messages de retour inline en haut */}
      {saveSuccess && (
        <div className="flex items-center gap-2 p-4 bg-emerald-950/40 border border-emerald-800 text-emerald-300 rounded-xl text-sm font-medium animate-in fade-in">
          <FiCheckCircle className="w-5 h-5 flex-shrink-0" />
          <span>Critères de ciblage et préférences enregistrés avec succès.</span>
        </div>
      )}

      {saveError && (
        <div className="flex items-center gap-2 p-4 bg-rose-950/40 border border-rose-800 text-rose-300 rounded-xl text-sm font-medium animate-in fade-in">
          <FiAlertCircle className="w-5 h-5 flex-shrink-0" />
          <span>{saveError}</span>
        </div>
      )}

      {/* 1. Postes Cibles & Séniorité */}
      <div className="bg-slate-900/70 border border-slate-800 backdrop-blur-md rounded-2xl p-6 shadow-xl space-y-6">
        <div className="flex items-center gap-3 border-b border-slate-800/80 pb-4">
          <div className="p-2.5 bg-blue-950/60 text-blue-400 border border-blue-800/50 rounded-xl">
            <FiTarget className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white">
              Postes Cibles & Séniorité
            </h3>
            <p className="text-xs text-slate-400">
              Pilote le matching avec les offres d'emploi et les requêtes de collecte Airflow.
            </p>
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-2">
              Intitulés recherchés (ex: Développeur Fullstack, Chef de Projet, Consultant...)
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={newRoleInput}
                onChange={(e) => setNewRoleInput(e.target.value)}
                onKeyDown={handleAddRole}
                placeholder="Ajouter un titre de poste et appuyer sur Entrée..."
                className="flex-1 px-3.5 py-2 text-sm bg-slate-950/60 border border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 text-white placeholder-slate-500"
              />
              <button
                type="button"
                onClick={handleAddRole}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-sm font-medium flex items-center gap-1.5 transition-colors shadow-md shadow-blue-500/10"
              >
                <FiPlus className="w-4 h-4" /> Ajouter
              </button>
            </div>

            {/* Suggestions dynamiques basées sur le profil */}
            {suggestedRoles.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 mt-2.5">
                <span className="text-[11px] text-slate-400 mr-1">Suggestions basées sur votre profil :</span>
                {suggestedRoles.map((role) => {
                  const isSelected = targetRoles.includes(role);
                  return (
                    <button
                      key={role}
                      type="button"
                      onClick={() => {
                        if (!isSelected) setTargetRoles([...targetRoles, role]);
                      }}
                      disabled={isSelected}
                      className={`text-[11px] px-2.5 py-0.5 rounded-full border transition-all ${
                        isSelected
                          ? "bg-slate-800/80 text-slate-500 border-slate-700/50 cursor-default"
                          : "bg-blue-950/40 text-blue-300 border-blue-800/60 hover:bg-blue-900/60 hover:border-blue-500 cursor-pointer"
                      }`}
                    >
                      + {role}
                    </button>
                  );
                })}
              </div>
            )}

            {targetRoles.length > 0 ? (
              <div className="flex flex-wrap gap-2 mt-3">
                {targetRoles.map((role) => (
                  <span
                    key={role}
                    className="inline-flex items-center gap-1.5 px-3 py-1 bg-blue-950/60 border border-blue-800 text-blue-300 text-xs font-semibold rounded-lg shadow-sm"
                  >
                    {role}
                    <button
                      type="button"
                      onClick={() => handleRemoveRole(role)}
                      className="hover:text-blue-100"
                    >
                      <FiX className="w-3.5 h-3.5" />
                    </button>
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-400 mt-2 italic">
                Aucun poste cible défini. Ajoutez au moins un titre pour déclencher la recommandation d'offres.
              </p>
            )}
          </div>

          <div>
            <div className="flex items-center justify-between mb-2.5">
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
                Niveaux de séniorité ciblés (Sélection multiple)
              </label>
              {seniorityLevels.length > 0 && (
                <button
                  type="button"
                  onClick={() => setSeniorityLevels([])}
                  className="text-[11px] text-slate-400 hover:text-slate-200 underline cursor-pointer"
                >
                  Tous les niveaux
                </button>
              )}
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
              {SENIORITY_OPTIONS.map((opt) => {
                const isSelected = seniorityLevels.includes(opt.value);
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => handleToggleSeniority(opt.value)}
                    className={`flex items-center justify-between p-3 rounded-xl border text-left transition-all cursor-pointer ${
                      isSelected
                        ? "bg-blue-950/60 border-blue-500 text-white shadow-md shadow-blue-500/10"
                        : "bg-slate-950/60 border-slate-800 text-slate-400 hover:border-slate-700 hover:text-slate-200"
                    }`}
                  >
                    <div>
                      <p className="text-sm font-semibold">{opt.label}</p>
                      <p className="text-[11px] text-slate-400">{opt.desc}</p>
                    </div>
                    <div
                      className={`w-5 h-5 rounded-md border flex items-center justify-center transition-colors ${
                        isSelected
                          ? "bg-blue-600 border-blue-500 text-white"
                          : "border-slate-700 bg-slate-900/50"
                      }`}
                    >
                      {isSelected && <FiCheck className="w-3.5 h-3.5" />}
                    </div>
                  </button>
                );
              })}
            </div>
            {seniorityLevels.length === 0 && (
              <p className="text-xs text-slate-400 mt-2 italic">
                Aucun niveau sélectionné : le matching et la collecte s'appliqueront à tous les niveaux.
              </p>
            )}
          </div>
        </div>
      </div>

      {/* 2. Localisation & Télétravail */}
      <div className="bg-slate-900/70 border border-slate-800 backdrop-blur-md rounded-2xl p-6 shadow-xl space-y-6">
        <div className="flex items-center gap-3 border-b border-slate-800/80 pb-4">
          <div className="p-2.5 bg-emerald-950/60 text-emerald-400 border border-emerald-800/50 rounded-xl">
            <FiMapPin className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white">
              Localisation & Mobilité
            </h3>
            <p className="text-xs text-slate-400">
              Définissez vos villes de prédilection et votre modalité de travail.
            </p>
          </div>
        </div>

        <div className="space-y-5">
          {/* Badges Remote Policy */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-3">
              Politique de télétravail souhaitée
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {REMOTE_OPTIONS.map((opt) => {
                const isSelected = remotePolicy === opt.value;
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setRemotePolicy(opt.value)}
                    className={`flex flex-col text-left p-3.5 rounded-xl border transition-all ${
                      isSelected
                        ? "bg-emerald-950/50 border-emerald-500 text-white shadow-md shadow-emerald-500/10"
                        : "bg-slate-950/50 border-slate-800 hover:bg-slate-800/50 text-slate-300"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-lg">{opt.icon}</span>
                      <div
                        className={`w-3.5 h-3.5 rounded-full border ${
                          isSelected
                            ? "border-emerald-500 bg-emerald-500"
                            : "border-slate-600"
                        }`}
                      />
                    </div>
                    <span className="text-sm font-semibold text-white">
                      {opt.label}
                    </span>
                    <span className="text-xs text-slate-400 mt-0.5">
                      {opt.desc}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Villes */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-2">
              Villes ou départements cibles (ex: Lyon, Paris, Nantes)
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={newLocationInput}
                onChange={(e) => setNewLocationInput(e.target.value)}
                onKeyDown={handleAddLocation}
                placeholder="Ajouter une ville (ex: Lyon)..."
                className="flex-1 px-3.5 py-2 text-sm bg-slate-950/60 border border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500 text-white placeholder-slate-500"
              />
              <button
                type="button"
                onClick={handleAddLocation}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-sm font-medium flex items-center gap-1.5 transition-colors shadow-md shadow-emerald-500/10"
              >
                <FiPlus className="w-4 h-4" /> Ajouter
              </button>
            </div>

            {/* Suggestions rapides de villes */}
            <div className="flex flex-wrap items-center gap-1.5 mt-2.5">
              <span className="text-[11px] text-slate-400 mr-1">Suggestions :</span>
              {SUGGESTED_LOCATIONS.map((loc) => {
                const isSelected = locations.includes(loc);
                return (
                  <button
                    key={loc}
                    type="button"
                    onClick={() => {
                      if (!isSelected) setLocations([...locations, loc]);
                    }}
                    disabled={isSelected}
                    className={`text-[11px] px-2.5 py-0.5 rounded-full border transition-all ${
                      isSelected
                        ? "bg-slate-800/80 text-slate-500 border-slate-700/50 cursor-default"
                        : "bg-emerald-950/40 text-emerald-300 border-emerald-800/60 hover:bg-emerald-900/60 hover:border-emerald-500 cursor-pointer"
                    }`}
                  >
                    + {loc}
                  </button>
                );
              })}
            </div>

            {locations.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-3">
                {locations.map((loc) => (
                  <span
                    key={loc}
                    className="inline-flex items-center gap-1.5 px-3 py-1 bg-emerald-950/60 border border-emerald-800 text-emerald-300 text-xs font-semibold rounded-lg shadow-sm"
                  >
                    {loc}
                    <button
                      type="button"
                      onClick={() => handleRemoveLocation(loc)}
                      className="hover:text-emerald-100"
                    >
                      <FiX className="w-3.5 h-3.5" />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 3. Prétentions Salariales */}
      <div className="bg-slate-900/70 border border-slate-800 backdrop-blur-md rounded-2xl p-6 shadow-xl space-y-6">
        <div className="flex items-center gap-3 border-b border-slate-800/80 pb-4">
          <div className="p-2.5 bg-amber-950/60 text-amber-400 border border-amber-800/50 rounded-xl">
            <FiDollarSign className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white">
              Rémunération Souhaitée
            </h3>
            <p className="text-xs text-slate-400">
              Permet de filtrer et classer les offres selon vos attentes financières annuelles.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-2">
              Salaire Minimum Brut / an
            </label>
            <div className="relative">
              <input
                type="number"
                value={minSalary}
                onChange={(e) => setMinSalary(e.target.value)}
                placeholder="ex: 55000"
                step="1000"
                className="w-full px-3.5 py-2 text-sm bg-slate-950/60 border border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-amber-500 text-white placeholder-slate-500"
              />
              <span className="absolute right-3.5 top-2.5 text-xs text-slate-400 font-semibold">
                {currency}
              </span>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-2">
              Salaire Cible / an
            </label>
            <div className="relative">
              <input
                type="number"
                value={targetSalary}
                onChange={(e) => setTargetSalary(e.target.value)}
                placeholder="ex: 65000"
                step="1000"
                className="w-full px-3.5 py-2 text-sm bg-slate-950/60 border border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-amber-500 text-white placeholder-slate-500"
              />
              <span className="absolute right-3.5 top-2.5 text-xs text-slate-400 font-semibold">
                {currency}
              </span>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-2">
              Devise
            </label>
            <select
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              className="w-full px-3.5 py-2 text-sm bg-slate-950 border border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-amber-500 text-white"
            >
              <option value="EUR">EUR (€) - Euro</option>
              <option value="USD">USD ($) - Dollar US</option>
              <option value="CHF">CHF - Franc Suisse</option>
              <option value="GBP">GBP (£) - Livre Sterling</option>
            </select>
          </div>
        </div>
      </div>

      {/* 4. Type de Contrat & Disponibilité */}
      <div className="bg-slate-900/70 border border-slate-800 backdrop-blur-md rounded-2xl p-6 shadow-xl space-y-6">
        <div className="flex items-center gap-3 border-b border-slate-800/80 pb-4">
          <div className="p-2.5 bg-purple-950/60 text-purple-400 border border-purple-800/50 rounded-xl">
            <FiBriefcase className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white">
              Contrat & Disponibilité
            </h3>
            <p className="text-xs text-slate-400">
              Types de contrats acceptés et statut d'autorisation de travail.
            </p>
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-2.5">
              Types de contrat recherchés
            </label>
            <div className="flex flex-wrap gap-2.5">
              {CONTRACT_OPTIONS.map((contract) => {
                const isSelected = contractTypes.includes(contract);
                return (
                  <button
                    key={contract}
                    type="button"
                    onClick={() => handleToggleContract(contract)}
                    className={`px-3.5 py-2 text-xs font-semibold rounded-xl border transition-all ${
                      isSelected
                        ? "bg-purple-950/50 border-purple-500 text-purple-200 shadow-md shadow-purple-500/10"
                        : "bg-slate-950/50 border-slate-800 text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"
                    }`}
                  >
                    {contract}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-2 flex items-center gap-1.5">
                <FiClock className="w-3.5 h-3.5 text-purple-400" /> Préavis / Disponibilité
              </label>
              <select
                value={noticePeriod}
                onChange={(e) => setNoticePeriod(e.target.value)}
                className="w-full px-3.5 py-2 text-sm bg-slate-950 border border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-purple-500 text-white"
              >
                <option value="">Non spécifié</option>
                {NOTICE_OPTIONS.map((opt) => (
                  <option key={opt} value={opt}>
                    {opt}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-2 flex items-center gap-1.5">
                <FiShield className="w-3.5 h-3.5 text-purple-400" /> Autorisation de travail
              </label>
              <select
                value={workAuthorization}
                onChange={(e) => setWorkAuthorization(e.target.value)}
                className="w-full px-3.5 py-2 text-sm bg-slate-950 border border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-purple-500 text-white"
              >
                <option value="">Non spécifié</option>
                <option value="EU citizen">Citoyen UE / Espace Économique Européen</option>
                <option value="work_permit_held">Titre de séjour / Autorisation de travail valide</option>
                <option value="sponsorship_required">Besoin de sponsoring de visa</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* 5. Mots-clés Exclus (Filtre anti-bruit) */}
      <div className="bg-slate-900/70 border border-slate-800 backdrop-blur-md rounded-2xl p-6 shadow-xl space-y-6">
        <div className="flex items-center gap-3 border-b border-slate-800/80 pb-4">
          <div className="p-2.5 bg-rose-950/60 text-rose-400 border border-rose-800/50 rounded-xl">
            <FiSlash className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white">
              Filtres d'Exclusion (Blacklist)
            </h3>
            <p className="text-xs text-slate-400">
              Les offres contenant ces technologies ou termes seront automatiquement rejetées lors du scraping.
            </p>
          </div>
        </div>

        <div>
          <div className="flex gap-2">
            <input
              type="text"
              value={newExcludedInput}
              onChange={(e) => setNewExcludedInput(e.target.value)}
              onKeyDown={handleAddExcluded}
              placeholder="Ex: PHP, COBOL, Wordpress, ESN..."
              className="flex-1 px-3.5 py-2 text-sm bg-slate-950/60 border border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-rose-500 text-white placeholder-slate-500"
            />
            <button
              type="button"
              onClick={handleAddExcluded}
              className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-xl text-sm font-medium flex items-center gap-1.5 transition-colors shadow-md shadow-rose-500/10"
            >
              <FiPlus className="w-4 h-4" /> Exclure
            </button>
          </div>

          {excludedKeywords.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-3">
              {excludedKeywords.map((word) => (
                <span
                  key={word}
                  className="inline-flex items-center gap-1.5 px-3 py-1 bg-rose-950/60 border border-rose-800 text-rose-300 text-xs font-semibold rounded-lg shadow-sm"
                >
                  {word}
                  <button
                    type="button"
                    onClick={() => handleRemoveExcluded(word)}
                    className="hover:text-rose-100"
                  >
                    <FiX className="w-3.5 h-3.5" />
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Bouton de sauvegarde avec feedback d'état */}
      <div className="flex items-center justify-end gap-3 pt-4">
        {saveSuccess && (
          <span className="text-xs font-semibold text-emerald-400 flex items-center gap-1.5 animate-in fade-in">
            <FiCheckCircle className="w-4 h-4" />
            Enregistré avec succès !
          </span>
        )}
        <button
          type="submit"
          disabled={isSaving}
          className={`inline-flex items-center gap-2 px-6 py-3 rounded-xl text-sm font-semibold shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer ${
            saveSuccess
              ? "bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-500/25"
              : "bg-blue-600 hover:bg-blue-500 text-white shadow-blue-500/25"
          }`}
        >
          {isSaving ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              <span>Enregistrement...</span>
            </>
          ) : saveSuccess ? (
            <>
              <FiCheckCircle className="w-4 h-4" />
              <span>Préférences à jour</span>
            </>
          ) : (
            <>
              <FiSave className="w-4 h-4" />
              <span>Enregistrer les préférences de ciblage</span>
            </>
          )}
        </button>
      </div>
    </form>
  );
}
