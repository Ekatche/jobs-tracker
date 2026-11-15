"use client";

import React from "react";
import { FiMapPin, FiPlus, FiX } from "react-icons/fi";
import { RemotePolicy } from "@/types/coverLetter";
import { TargetingSectionShell } from "./TargetingSectionShell";
import { REMOTE_OPTIONS, SUGGESTED_LOCATIONS } from "./targetingOptions";

interface TargetingLocationsSectionProps {
  isOpen: boolean;
  onToggle: () => void;
  remotePolicy: RemotePolicy;
  locations: string[];
  newLocationInput: string;
  onRemotePolicyChange: (policy: RemotePolicy) => void;
  onNewLocationInputChange: (val: string) => void;
  onAddLocation: (e: React.KeyboardEvent | React.MouseEvent) => void;
  onSelectSuggestedLocation: (loc: string) => void;
  onRemoveLocation: (loc: string) => void;
}

/**
 * Section 2: Remote policy selector and target cities/locations management.
 */
export function TargetingLocationsSection({
  isOpen,
  onToggle,
  remotePolicy,
  locations,
  newLocationInput,
  onRemotePolicyChange,
  onNewLocationInputChange,
  onAddLocation,
  onSelectSuggestedLocation,
  onRemoveLocation,
}: TargetingLocationsSectionProps) {
  return (
    <TargetingSectionShell
      icon={<FiMapPin className="w-5 h-5" />}
      iconBoxClassName="bg-emerald-950/60 text-emerald-400 border-emerald-800/50"
      title="Localisation & Mobilité"
      subtitle="Définissez vos villes de prédilection et votre modalité de travail."
      isOpen={isOpen}
      onToggle={onToggle}
    >
      <div className="space-y-5">
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
                  onClick={() => onRemotePolicyChange(opt.value)}
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
                        isSelected ? "border-emerald-500 bg-emerald-500" : "border-slate-600"
                      }`}
                    />
                  </div>
                  <span className="text-sm font-semibold text-white">{opt.label}</span>
                  <span className="text-xs text-slate-400 mt-0.5">{opt.desc}</span>
                </button>
              );
            })}
          </div>
        </div>

        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-2">
            Villes ou départements cibles (ex: Lyon, Paris, Nantes)
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={newLocationInput}
              onChange={(e) => onNewLocationInputChange(e.target.value)}
              onKeyDown={onAddLocation}
              placeholder="Ajouter une ville (ex: Lyon)..."
              className="flex-1 px-3.5 py-2 text-sm bg-slate-950/60 border border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500 text-white placeholder-slate-500"
            />
            <button
              type="button"
              onClick={onAddLocation}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-sm font-medium flex items-center gap-1.5 transition-colors shadow-md shadow-emerald-500/10"
            >
              <FiPlus className="w-4 h-4" /> Ajouter
            </button>
          </div>

          <div className="flex flex-wrap items-center gap-1.5 mt-2.5">
            <span className="text-[11px] text-slate-400 mr-1">Suggestions :</span>
            {SUGGESTED_LOCATIONS.map((loc) => {
              const isSelected = locations.includes(loc);
              return (
                <button
                  key={loc}
                  type="button"
                  onClick={() => {
                    if (!isSelected) onSelectSuggestedLocation(loc);
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
                    onClick={() => onRemoveLocation(loc)}
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
    </TargetingSectionShell>
  );
}
