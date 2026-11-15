"use client";

import { FiDollarSign, FiCheck } from "react-icons/fi";
import type { UserTier } from "@/types/usage";

interface UsageTierPlansProps {
  currentTier: UserTier;
  updatingTier: string | null;
  onSelectTier: (tier: UserTier) => void;
}

export default function UsageTierPlans({
  currentTier,
  updatingTier,
  onSelectTier,
}: UsageTierPlansProps) {
  return (
    <div className="space-y-4 pt-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-bold text-white flex items-center gap-2">
          <FiDollarSign className="w-5 h-5 text-indigo-400" />
          Changer de Formule (Simulation &amp; Upgrade)
        </h3>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div
          className={`rounded-2xl p-6 border flex flex-col justify-between transition-all ${
            currentTier === "free"
              ? "bg-slate-900/90 border-indigo-500/50 shadow-xl shadow-indigo-500/10"
              : "bg-slate-900/50 border-slate-800 hover:border-slate-700"
          }`}
        >
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="text-lg font-bold text-white">Free</h4>
              {currentTier === "free" && (
                <span className="text-xs font-bold px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                  Actuel
                </span>
              )}
            </div>
            <div>
              <span className="text-3xl font-black text-white">0€</span>
              <span className="text-xs text-slate-400"> / pour toujours</span>
            </div>
            <ul className="space-y-2 text-xs text-slate-300 border-t border-slate-800 pt-4">
              <li className="flex items-center gap-2">
                <FiCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                <span><strong>1</strong> Préparation d&apos;entretien / mois</span>
              </li>
              <li className="flex items-center gap-2">
                <FiCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                <span><strong>2</strong> CVs Sur-Mesure / mois</span>
              </li>
              <li className="flex items-center gap-2">
                <FiCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                <span><strong>5</strong> Lettres de motivation / mois</span>
              </li>
              <li className="flex items-center gap-2">
                <FiCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                <span><strong>20</strong> Évaluations d&apos;offres / mois</span>
              </li>
            </ul>
          </div>

          <button
            type="button"
            disabled={currentTier === "free" || updatingTier !== null}
            onClick={() => onSelectTier("free")}
            className="mt-6 w-full py-2.5 rounded-xl text-xs font-bold border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-200 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {currentTier === "free" ? "Plan Actif" : "Basculer en Free"}
          </button>
        </div>

        <div
          className={`rounded-2xl p-6 border flex flex-col justify-between transition-all relative overflow-hidden ${
            currentTier === "advanced"
              ? "bg-slate-900/90 border-indigo-500 shadow-xl shadow-indigo-500/20"
              : "bg-slate-900/60 border-slate-800 hover:border-slate-700"
          }`}
        >
          <div className="absolute top-0 right-0 bg-indigo-600 text-white text-[10px] font-extrabold uppercase px-3 py-1 rounded-bl-xl tracking-wider">
            Populaire
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="text-lg font-bold text-white">Advanced</h4>
              {currentTier === "advanced" && (
                <span className="text-xs font-bold px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                  Actuel
                </span>
              )}
            </div>
            <div>
              <span className="text-3xl font-black text-white">9.90€</span>
              <span className="text-xs text-slate-400"> / mois</span>
            </div>
            <ul className="space-y-2 text-xs text-slate-300 border-t border-slate-800 pt-4">
              <li className="flex items-center gap-2">
                <FiCheck className="w-4 h-4 text-indigo-400 shrink-0" />
                <span><strong>10</strong> Préparations d&apos;entretien / mois</span>
              </li>
              <li className="flex items-center gap-2">
                <FiCheck className="w-4 h-4 text-indigo-400 shrink-0" />
                <span><strong>15</strong> CVs Sur-Mesure / mois</span>
              </li>
              <li className="flex items-center gap-2">
                <FiCheck className="w-4 h-4 text-indigo-400 shrink-0" />
                <span><strong>30</strong> Lettres de motivation / mois</span>
              </li>
              <li className="flex items-center gap-2">
                <FiCheck className="w-4 h-4 text-indigo-400 shrink-0" />
                <span><strong>100</strong> Évaluations d&apos;offres / mois</span>
              </li>
            </ul>
          </div>

          <button
            type="button"
            disabled={currentTier === "advanced" || updatingTier !== null}
            onClick={() => onSelectTier("advanced")}
            className="mt-6 w-full py-2.5 rounded-xl text-xs font-bold bg-indigo-600 hover:bg-indigo-500 text-white shadow-md shadow-indigo-500/20 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {updatingTier === "advanced"
              ? "Mise à jour..."
              : currentTier === "advanced"
              ? "Plan Actif"
              : "Choisir Advanced"}
          </button>
        </div>

        <div
          className={`rounded-2xl p-6 border flex flex-col justify-between transition-all ${
            currentTier === "pro"
              ? "bg-slate-900/90 border-purple-500 shadow-xl shadow-purple-500/20"
              : "bg-slate-900/50 border-slate-800 hover:border-slate-700"
          }`}
        >
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="text-lg font-bold text-white">Pro</h4>
              {currentTier === "pro" && (
                <span className="text-xs font-bold px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30">
                  Actuel
                </span>
              )}
            </div>
            <div>
              <span className="text-3xl font-black text-white">24.90€</span>
              <span className="text-xs text-slate-400"> / mois</span>
            </div>
            <ul className="space-y-2 text-xs text-slate-300 border-t border-slate-800 pt-4">
              <li className="flex items-center gap-2">
                <FiCheck className="w-4 h-4 text-purple-400 shrink-0" />
                <span className="font-bold text-purple-300">Tout Illimité</span>
              </li>
              <li className="flex items-center gap-2">
                <FiCheck className="w-4 h-4 text-purple-400 shrink-0" />
                <span>Préparations d&apos;entretien illimitées</span>
              </li>
              <li className="flex items-center gap-2">
                <FiCheck className="w-4 h-4 text-purple-400 shrink-0" />
                <span>Générateur de CVs illimité</span>
              </li>
              <li className="flex items-center gap-2">
                <FiCheck className="w-4 h-4 text-purple-400 shrink-0" />
                <span>Lettres &amp; Évaluations illimitées</span>
              </li>
            </ul>
          </div>

          <button
            type="button"
            disabled={currentTier === "pro" || updatingTier !== null}
            onClick={() => onSelectTier("pro")}
            className="mt-6 w-full py-2.5 rounded-xl text-xs font-bold bg-purple-600 hover:bg-purple-500 text-white shadow-md shadow-purple-500/20 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {updatingTier === "pro"
              ? "Mise à jour..."
              : currentTier === "pro"
              ? "Plan Actif"
              : "Choisir Pro"}
          </button>
        </div>
      </div>
    </div>
  );
}
