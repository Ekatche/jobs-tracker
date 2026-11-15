"use client";

import React from "react";
import { FiLayers, FiSlash, FiPlus, FiX } from "react-icons/fi";
import { SECTOR_OPTIONS, COMPANY_SIZE_OPTIONS } from "@/lib/companyTaxonomy";
import { TargetingSectionShell } from "./TargetingSectionShell";
import { SECTOR_VALUES, toggleStringValue } from "./targetingOptions";

interface TargetingSectorsSectionProps {
  isOpen: boolean;
  onToggle: () => void;
  preferredIndustries: string[];
  preferredCompanySizes: string[];
  onPreferredIndustriesChange: (val: string[]) => void;
  onPreferredCompanySizesChange: (val: string[]) => void;
}

/**
 * Section 5: Preferred industries and company size filters.
 */
export function TargetingSectorsSection({
  isOpen,
  onToggle,
  preferredIndustries,
  preferredCompanySizes,
  onPreferredIndustriesChange,
  onPreferredCompanySizesChange,
}: TargetingSectorsSectionProps) {
  return (
    <TargetingSectionShell
      icon={<FiLayers className="w-5 h-5" />}
      iconBoxClassName="bg-cyan-950/60 text-cyan-400 border-cyan-800/50"
      title="Secteurs d'activité & Taille d'entreprise"
      subtitle="Les secteurs et tailles d'entreprise qui vous intéressent."
      isOpen={isOpen}
      onToggle={onToggle}
    >
      <div className="space-y-4">
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-2.5">
            Secteurs d&apos;activité
          </label>
          <div className="flex flex-wrap gap-2.5">
            {SECTOR_OPTIONS.map((sector) => {
              const isSelected = preferredIndustries.includes(sector.value);
              return (
                <button
                  key={sector.value}
                  type="button"
                  title={sector.desc}
                  onClick={() =>
                    onPreferredIndustriesChange(toggleStringValue(preferredIndustries, sector.value))
                  }
                  className={`px-3.5 py-2 text-xs font-semibold rounded-xl border transition-all ${
                    isSelected
                      ? "bg-cyan-950/50 border-cyan-500 text-cyan-200 shadow-md shadow-cyan-500/10"
                      : "bg-slate-950/50 border-slate-800 text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"
                  }`}
                >
                  {sector.label}
                </button>
              );
            })}
            {preferredIndustries
              .filter((value) => !SECTOR_VALUES.has(value))
              .map((value) => (
                <span
                  key={value}
                  title="Ancienne valeur, non utilisée pour le tri"
                  className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold rounded-xl border border-slate-800 bg-slate-900/40 text-slate-500"
                >
                  {value}
                  <button
                    type="button"
                    onClick={() =>
                      onPreferredIndustriesChange(preferredIndustries.filter((v) => v !== value))
                    }
                    className="hover:text-slate-300"
                  >
                    <FiX className="w-3.5 h-3.5" />
                  </button>
                </span>
              ))}
          </div>
        </div>

        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-2.5">
            Taille d&apos;entreprise
          </label>
          <div className="flex flex-wrap gap-2.5">
            {COMPANY_SIZE_OPTIONS.map((size) => {
              const isSelected = preferredCompanySizes.includes(size.value);
              return (
                <button
                  key={size.value}
                  type="button"
                  onClick={() =>
                    onPreferredCompanySizesChange(toggleStringValue(preferredCompanySizes, size.value))
                  }
                  className={`px-3.5 py-2 text-xs font-semibold rounded-xl border transition-all ${
                    isSelected
                      ? "bg-cyan-950/50 border-cyan-500 text-cyan-200 shadow-md shadow-cyan-500/10"
                      : "bg-slate-950/50 border-slate-800 text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"
                  }`}
                >
                  {size.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </TargetingSectionShell>
  );
}

interface TargetingExcludedSectionProps {
  isOpen: boolean;
  onToggle: () => void;
  excludedKeywords: string[];
  newExcludedInput: string;
  onNewExcludedInputChange: (val: string) => void;
  onAddExcluded: (e: React.KeyboardEvent | React.MouseEvent) => void;
  onRemoveExcluded: (word: string) => void;
}

/**
 * Section 6: Excluded keywords (scraping & recommendation blacklist).
 */
export function TargetingExcludedSection({
  isOpen,
  onToggle,
  excludedKeywords,
  newExcludedInput,
  onNewExcludedInputChange,
  onAddExcluded,
  onRemoveExcluded,
}: TargetingExcludedSectionProps) {
  return (
    <TargetingSectionShell
      icon={<FiSlash className="w-5 h-5" />}
      iconBoxClassName="bg-rose-950/60 text-rose-400 border-rose-800/50"
      title="Filtres d'Exclusion (Blacklist)"
      subtitle="Les offres contenant ces technologies ou termes seront automatiquement rejetées lors du scraping."
      isOpen={isOpen}
      onToggle={onToggle}
    >
      <div>
        <div className="flex gap-2">
          <input
            type="text"
            value={newExcludedInput}
            onChange={(e) => onNewExcludedInputChange(e.target.value)}
            onKeyDown={onAddExcluded}
            placeholder="Ex: PHP, COBOL, Wordpress, ESN..."
            className="flex-1 px-3.5 py-2 text-sm bg-slate-950/60 border border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-rose-500 text-white placeholder-slate-500"
          />
          <button
            type="button"
            onClick={onAddExcluded}
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
                  onClick={() => onRemoveExcluded(word)}
                  className="hover:text-rose-100"
                >
                  <FiX className="w-3.5 h-3.5" />
                </button>
              </span>
            ))}
          </div>
        )}
      </div>
    </TargetingSectionShell>
  );
}
