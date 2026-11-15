"use client";

import React from "react";
import { FiTarget, FiCheckCircle, FiAlertCircle, FiSave, FiX } from "react-icons/fi";
import { CandidatePreferences } from "@/types/coverLetter";
import { useTargetingPreferences } from "@/hooks/useTargetingPreferences";
import { TargetingRolesSection } from "./targeting/TargetingRolesSection";
import { TargetingLocationsSection } from "./targeting/TargetingLocationsSection";
import {
  TargetingSalarySection,
  TargetingContractSection,
} from "./targeting/TargetingContractSalarySection";
import {
  TargetingSectorsSection,
  TargetingExcludedSection,
} from "./targeting/TargetingSectorsBlacklistSection";

interface TargetingPreferencesSectionProps {
  initialPreferences?: CandidatePreferences;
  onSave?: (preferences: CandidatePreferences) => Promise<void>;
  isSaving?: boolean;
}

export default function TargetingPreferencesSection({
  initialPreferences,
  onSave,
  isSaving = false,
}: TargetingPreferencesSectionProps) {
  const tp = useTargetingPreferences(initialPreferences, onSave);
  const effectiveSaving = isSaving || tp.isInternalSaving;

  return (
    <form onSubmit={tp.handleSubmit} className="space-y-8">
      {/* Automatic watch toggle card */}
      <div className="p-5 rounded-2xl bg-slate-900/90 border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-start gap-3">
          <div
            className={`p-2.5 rounded-xl border ${
              tp.searchActive
                ? "bg-blue-500/10 border-blue-500/30 text-blue-400"
                : "bg-slate-800 border-slate-700 text-slate-400"
            }`}
          >
            <FiTarget className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-white">Veille automatique des offres</h3>
              <span
                className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                  tp.searchActive
                    ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
                    : "bg-slate-800 text-slate-400 border border-slate-700"
                }`}
              >
                {tp.searchActive ? "Actif" : "En pause"}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1 max-w-xl">
              Lorsque cette option est activée, vos rôles cibles et villes sont automatiquement inclus dans les collectes d&apos;offres d&apos;Airflow. Désactivez-la pour suspendre la recherche sans altérer votre profil.
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => tp.setSearchActive(!tp.searchActive)}
          className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
            tp.searchActive ? "bg-blue-600" : "bg-slate-700"
          }`}
        >
          <span
            className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out ${
              tp.searchActive ? "translate-x-5" : "translate-x-0"
            }`}
          />
        </button>
      </div>

      {/* Floating Toast Notification */}
      {tp.saveSuccess && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-3 p-4 bg-emerald-950/90 border border-emerald-500/50 text-emerald-100 rounded-2xl shadow-2xl backdrop-blur-md animate-in fade-in slide-in-from-bottom-5 duration-300">
          <div className="p-2 bg-emerald-500/20 text-emerald-400 rounded-xl">
            <FiCheckCircle className="w-5 h-5" />
          </div>
          <div>
            <p className="text-sm font-bold text-white">Préférences enregistrées</p>
            <p className="text-xs text-emerald-300/80">
              Critères de ciblage et filtres mis à jour avec succès.
            </p>
          </div>
          <button
            type="button"
            onClick={() => tp.setSaveSuccess(false)}
            className="ml-2 text-emerald-400 hover:text-emerald-200"
          >
            <FiX className="w-4 h-4" />
          </button>
        </div>
      )}

      {tp.saveError && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-3 p-4 bg-rose-950/90 border border-rose-500/50 text-rose-100 rounded-2xl shadow-2xl backdrop-blur-md animate-in fade-in slide-in-from-bottom-5 duration-300">
          <div className="p-2 bg-rose-500/20 text-rose-400 rounded-xl">
            <FiAlertCircle className="w-5 h-5" />
          </div>
          <div>
            <p className="text-sm font-bold text-white">Erreur d&apos;enregistrement</p>
            <p className="text-xs text-rose-300/80">{tp.saveError}</p>
          </div>
          <button
            type="button"
            onClick={() => tp.setSaveError(null)}
            className="ml-2 text-rose-400 hover:text-rose-200"
          >
            <FiX className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Top inline alerts */}
      {tp.saveSuccess && (
        <div className="flex items-center gap-2 p-4 bg-emerald-950/40 border border-emerald-800 text-emerald-300 rounded-xl text-sm font-medium animate-in fade-in">
          <FiCheckCircle className="w-5 h-5 flex-shrink-0" />
          <span>Critères de ciblage et préférences enregistrés avec succès.</span>
        </div>
      )}

      {tp.saveError && (
        <div className="flex items-center gap-2 p-4 bg-rose-950/40 border border-rose-800 text-rose-300 rounded-xl text-sm font-medium animate-in fade-in">
          <FiAlertCircle className="w-5 h-5 flex-shrink-0" />
          <span>{tp.saveError}</span>
        </div>
      )}

      <TargetingRolesSection
        isOpen={tp.openSections.roles}
        onToggle={() => tp.toggleSection("roles")}
        targetRoles={tp.targetRoles}
        suggestedRoles={tp.suggestedRoles}
        newRoleInput={tp.newRoleInput}
        seniorityLevels={tp.seniorityLevels}
        onNewRoleInputChange={tp.setNewRoleInput}
        onAddRole={tp.handleAddRole}
        onSelectSuggestedRole={(role) => tp.setTargetRoles([...tp.targetRoles, role])}
        onRemoveRole={tp.handleRemoveRole}
        onToggleSeniority={tp.handleToggleSeniority}
        onClearSeniority={() => tp.setSeniorityLevels([])}
      />

      <TargetingLocationsSection
        isOpen={tp.openSections.location}
        onToggle={() => tp.toggleSection("location")}
        remotePolicy={tp.remotePolicy}
        locations={tp.locations}
        newLocationInput={tp.newLocationInput}
        onRemotePolicyChange={tp.setRemotePolicy}
        onNewLocationInputChange={tp.setNewLocationInput}
        onAddLocation={tp.handleAddLocation}
        onSelectSuggestedLocation={(loc) => tp.setLocations([...tp.locations, loc])}
        onRemoveLocation={tp.handleRemoveLocation}
      />

      <TargetingSalarySection
        isOpen={tp.openSections.salary}
        onToggle={() => tp.toggleSection("salary")}
        minSalary={tp.minSalary}
        targetSalary={tp.targetSalary}
        currency={tp.currency}
        onMinSalaryChange={tp.setMinSalary}
        onTargetSalaryChange={tp.setTargetSalary}
        onCurrencyChange={tp.setCurrency}
      />

      <TargetingContractSection
        isOpen={tp.openSections.contract}
        onToggle={() => tp.toggleSection("contract")}
        contractTypes={tp.contractTypes}
        noticePeriod={tp.noticePeriod}
        workAuthorization={tp.workAuthorization}
        onToggleContract={tp.handleToggleContract}
        onNoticePeriodChange={tp.setNoticePeriod}
        onWorkAuthorizationChange={tp.setWorkAuthorization}
      />

      <TargetingSectorsSection
        isOpen={tp.openSections.sectors}
        onToggle={() => tp.toggleSection("sectors")}
        preferredIndustries={tp.preferredIndustries}
        preferredCompanySizes={tp.preferredCompanySizes}
        onPreferredIndustriesChange={tp.setPreferredIndustries}
        onPreferredCompanySizesChange={tp.setPreferredCompanySizes}
      />

      <TargetingExcludedSection
        isOpen={tp.openSections.excluded}
        onToggle={() => tp.toggleSection("excluded")}
        excludedKeywords={tp.excludedKeywords}
        newExcludedInput={tp.newExcludedInput}
        onNewExcludedInputChange={tp.setNewExcludedInput}
        onAddExcluded={tp.handleAddExcluded}
        onRemoveExcluded={tp.handleRemoveExcluded}
      />

      {/* Submit button with status feedback */}
      <div className="flex items-center justify-end gap-3 pt-4">
        {tp.saveSuccess && (
          <span className="text-xs font-semibold text-emerald-400 flex items-center gap-1.5 animate-in fade-in">
            <FiCheckCircle className="w-4 h-4" />
            Enregistré avec succès !
          </span>
        )}
        <button
          type="submit"
          disabled={effectiveSaving}
          className={`inline-flex items-center gap-2 px-6 py-3 rounded-xl text-sm font-semibold shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer ${
            tp.saveSuccess
              ? "bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-500/25"
              : "bg-blue-600 hover:bg-blue-500 text-white shadow-blue-500/25"
          }`}
        >
          {effectiveSaving ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              <span>Enregistrement...</span>
            </>
          ) : tp.saveSuccess ? (
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
