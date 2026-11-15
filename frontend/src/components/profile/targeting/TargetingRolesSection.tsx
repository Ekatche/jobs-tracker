"use client";

import React from "react";
import { FiTarget, FiPlus, FiX, FiCheck } from "react-icons/fi";
import { TargetingSectionShell } from "./TargetingSectionShell";
import { SENIORITY_OPTIONS } from "./targetingOptions";

interface TargetingRolesSectionProps {
  isOpen: boolean;
  onToggle: () => void;
  targetRoles: string[];
  suggestedRoles: string[];
  newRoleInput: string;
  seniorityLevels: string[];
  onNewRoleInputChange: (val: string) => void;
  onAddRole: (e: React.KeyboardEvent | React.MouseEvent) => void;
  onSelectSuggestedRole: (role: string) => void;
  onRemoveRole: (role: string) => void;
  onToggleSeniority: (val: string) => void;
  onClearSeniority: () => void;
}

/**
 * Section 1: Target job titles, profile-based suggestions, and multi-select seniority levels.
 */
export function TargetingRolesSection({
  isOpen,
  onToggle,
  targetRoles,
  suggestedRoles,
  newRoleInput,
  seniorityLevels,
  onNewRoleInputChange,
  onAddRole,
  onSelectSuggestedRole,
  onRemoveRole,
  onToggleSeniority,
  onClearSeniority,
}: TargetingRolesSectionProps) {
  return (
    <TargetingSectionShell
      icon={<FiTarget className="w-5 h-5" />}
      iconBoxClassName="bg-blue-950/60 text-blue-400 border-blue-800/50"
      title="Postes Cibles & Séniorité"
      subtitle="Pilote le matching avec les offres d'emploi et les requêtes de collecte Airflow."
      isOpen={isOpen}
      onToggle={onToggle}
    >
      <div className="space-y-4">
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-2">
            Intitulés recherchés (ex: Développeur Fullstack, Chef de Projet, Consultant...)
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={newRoleInput}
              onChange={(e) => onNewRoleInputChange(e.target.value)}
              onKeyDown={onAddRole}
              placeholder="Ajouter un titre de poste et appuyer sur Entrée..."
              className="flex-1 px-3.5 py-2 text-sm bg-slate-950/60 border border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 text-white placeholder-slate-500"
            />
            <button
              type="button"
              onClick={onAddRole}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-sm font-medium flex items-center gap-1.5 transition-colors shadow-md shadow-blue-500/10"
            >
              <FiPlus className="w-4 h-4" /> Ajouter
            </button>
          </div>

          {suggestedRoles.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 mt-2.5">
              <span className="text-[11px] text-slate-400 mr-1">
                Suggestions basées sur votre profil :
              </span>
              {suggestedRoles.map((role) => {
                const isSelected = targetRoles.includes(role);
                return (
                  <button
                    key={role}
                    type="button"
                    onClick={() => {
                      if (!isSelected) onSelectSuggestedRole(role);
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
                    onClick={() => onRemoveRole(role)}
                    className="hover:text-blue-100"
                  >
                    <FiX className="w-3.5 h-3.5" />
                  </button>
                </span>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-400 mt-2 italic">
              Aucun poste cible défini. Ajoutez au moins un titre pour déclencher la recommandation d&apos;offres.
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
                onClick={onClearSeniority}
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
                  onClick={() => onToggleSeniority(opt.value)}
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
              Aucun niveau sélectionné : le matching et la collecte s&apos;appliqueront à tous les niveaux.
            </p>
          )}
        </div>
      </div>
    </TargetingSectionShell>
  );
}
