"use client";

import React from "react";
import { FiDollarSign, FiBriefcase, FiClock, FiShield } from "react-icons/fi";
import { TargetingSectionShell } from "./TargetingSectionShell";
import { CONTRACT_OPTIONS, NOTICE_OPTIONS } from "./targetingOptions";

interface TargetingSalarySectionProps {
  isOpen: boolean;
  onToggle: () => void;
  minSalary: string;
  targetSalary: string;
  currency: string;
  onMinSalaryChange: (val: string) => void;
  onTargetSalaryChange: (val: string) => void;
  onCurrencyChange: (val: string) => void;
}

/**
 * Section 3: Minimum salary, target salary, and currency preferences.
 */
export function TargetingSalarySection({
  isOpen,
  onToggle,
  minSalary,
  targetSalary,
  currency,
  onMinSalaryChange,
  onTargetSalaryChange,
  onCurrencyChange,
}: TargetingSalarySectionProps) {
  return (
    <TargetingSectionShell
      icon={<FiDollarSign className="w-5 h-5" />}
      iconBoxClassName="bg-amber-950/60 text-amber-400 border-amber-800/50"
      title="Rémunération Souhaitée"
      subtitle="Permet de filtrer et classer les offres selon vos attentes financières annuelles."
      isOpen={isOpen}
      onToggle={onToggle}
    >
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-2">
            Salaire Minimum Brut / an
          </label>
          <div className="relative">
            <input
              type="number"
              value={minSalary}
              onChange={(e) => onMinSalaryChange(e.target.value)}
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
              onChange={(e) => onTargetSalaryChange(e.target.value)}
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
            onChange={(e) => onCurrencyChange(e.target.value)}
            className="w-full px-3.5 py-2 text-sm bg-slate-950 border border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-amber-500 text-white"
          >
            <option value="EUR">EUR (€) - Euro</option>
            <option value="USD">USD ($) - Dollar US</option>
            <option value="CHF">CHF - Franc Suisse</option>
            <option value="GBP">GBP (£) - Livre Sterling</option>
          </select>
        </div>
      </div>
    </TargetingSectionShell>
  );
}

interface TargetingContractSectionProps {
  isOpen: boolean;
  onToggle: () => void;
  contractTypes: string[];
  noticePeriod: string;
  workAuthorization: string;
  onToggleContract: (contract: string) => void;
  onNoticePeriodChange: (val: string) => void;
  onWorkAuthorizationChange: (val: string) => void;
}

/**
 * Section 4: Contract types, notice period, and work authorization.
 */
export function TargetingContractSection({
  isOpen,
  onToggle,
  contractTypes,
  noticePeriod,
  workAuthorization,
  onToggleContract,
  onNoticePeriodChange,
  onWorkAuthorizationChange,
}: TargetingContractSectionProps) {
  return (
    <TargetingSectionShell
      icon={<FiBriefcase className="w-5 h-5" />}
      iconBoxClassName="bg-purple-950/60 text-purple-400 border-purple-800/50"
      title="Contrat & Disponibilité"
      subtitle="Types de contrats acceptés et statut d'autorisation de travail."
      isOpen={isOpen}
      onToggle={onToggle}
    >
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
                  onClick={() => onToggleContract(contract)}
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
              onChange={(e) => onNoticePeriodChange(e.target.value)}
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
              onChange={(e) => onWorkAuthorizationChange(e.target.value)}
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
    </TargetingSectionShell>
  );
}
