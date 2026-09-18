"use client";

import React, { useState } from "react";
import {
  AudiencePackRecruiter,
  AudiencePackHiringManager,
  AudiencePackTechPanel,
} from "@/types/interview";
import {
  FiUserCheck,
  FiBriefcase,
  FiCpu,
  FiDollarSign,
  FiAlertTriangle,
  FiHelpCircle,
  FiLayers,
  FiTrendingUp,
} from "react-icons/fi";

interface AudiencePacksViewerProps {
  recruiterPack?: AudiencePackRecruiter | null;
  hmPack?: AudiencePackHiringManager | null;
  techPack?: AudiencePackTechPanel | null;
}

export default function AudiencePacksViewer({
  recruiterPack,
  hmPack,
  techPack,
}: AudiencePacksViewerProps) {
  const [activeTab, setActiveTab] = useState<"recruiter" | "hm" | "tech">("recruiter");

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
      {/* Tab Switcher */}
      <div className="flex border-b border-slate-800 bg-slate-950/40 p-1.5 gap-1.5">
        <button
          type="button"
          onClick={() => setActiveTab("recruiter")}
          className={`flex-1 py-2.5 px-3 rounded-lg text-xs sm:text-sm font-medium flex items-center justify-center gap-2 transition-all ${
            activeTab === "recruiter"
              ? "bg-indigo-600 text-white shadow-md shadow-indigo-500/20"
              : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
          }`}
        >
          <FiUserCheck className="w-4 h-4" />
          <span>Recruteur / RH</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("hm")}
          className={`flex-1 py-2.5 px-3 rounded-lg text-xs sm:text-sm font-medium flex items-center justify-center gap-2 transition-all ${
            activeTab === "hm"
              ? "bg-indigo-600 text-white shadow-md shadow-indigo-500/20"
              : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
          }`}
        >
          <FiBriefcase className="w-4 h-4" />
          <span>Hiring Manager</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("tech")}
          className={`flex-1 py-2.5 px-3 rounded-lg text-xs sm:text-sm font-medium flex items-center justify-center gap-2 transition-all ${
            activeTab === "tech"
              ? "bg-indigo-600 text-white shadow-md shadow-indigo-500/20"
              : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
          }`}
        >
          <FiCpu className="w-4 h-4" />
          <span>Panel Technique</span>
        </button>
      </div>

      {/* Tab Contents */}
      <div className="p-5 sm:p-6 text-sm text-slate-300">
        {/* Recruiter Tab */}
        {activeTab === "recruiter" && (
          <div className="space-y-6">
            {recruiterPack?.pitch_30s && (
              <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/60">
                <h4 className="text-xs uppercase tracking-wider font-semibold text-indigo-400 mb-2 flex items-center gap-1.5">
                  <FiUserCheck className="w-4 h-4" /> Pitch de cadrage 30s
                </h4>
                <p className="text-slate-100 leading-relaxed italic">
                  &ldquo;{recruiterPack.pitch_30s}&rdquo;
                </p>
              </div>
            )}

            {recruiterPack?.comp_strategy && (
              <div>
                <h4 className="text-xs uppercase tracking-wider font-semibold text-amber-400 mb-3 flex items-center gap-1.5">
                  <FiDollarSign className="w-4 h-4" /> Stratégie de Négociation Salariale
                </h4>
                <div className="grid sm:grid-cols-2 gap-3">
                  <div className="p-3.5 rounded-lg bg-emerald-950/20 border border-emerald-800/30">
                    <span className="text-xs font-semibold text-emerald-400 block mb-1">
                      ✅ À valoriser
                    </span>
                    <p className="text-xs text-slate-300 leading-relaxed">
                      {recruiterPack.comp_strategy.volunteer || "Alignement sur la grille marché et le niveau de séniorité"}
                    </p>
                  </div>
                  <div className="p-3.5 rounded-lg bg-rose-950/20 border border-rose-800/30">
                    <span className="text-xs font-semibold text-rose-400 block mb-1">
                      ❌ À éviter
                    </span>
                    <p className="text-xs text-slate-300 leading-relaxed">
                      {recruiterPack.comp_strategy.avoid || "Donner un chiffre ferme avant de connaître le package"}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {recruiterPack?.red_flags_they_screen_for && recruiterPack.red_flags_they_screen_for.length > 0 && (
              <div>
                <h4 className="text-xs uppercase tracking-wider font-semibold text-rose-400 mb-2 flex items-center gap-1.5">
                  <FiAlertTriangle className="w-4 h-4" /> Pièges RH & Signaux traqués
                </h4>
                <ul className="space-y-1.5">
                  {recruiterPack.red_flags_they_screen_for.map((rf, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-xs text-slate-300">
                      <span className="text-rose-400 font-bold">•</span>
                      <span>{rf}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {recruiterPack?.key_questions_to_ask_recruiter && recruiterPack.key_questions_to_ask_recruiter.length > 0 && (
              <div>
                <h4 className="text-xs uppercase tracking-wider font-semibold text-sky-400 mb-2 flex items-center gap-1.5">
                  <FiHelpCircle className="w-4 h-4" /> Questions clés à poser au recruteur
                </h4>
                <ul className="space-y-1.5">
                  {recruiterPack.key_questions_to_ask_recruiter.map((q, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-xs text-slate-300">
                      <span className="text-sky-400 font-bold">•</span>
                      <span>{q}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* Hiring Manager Tab */}
        {activeTab === "hm" && (
          <div className="space-y-6">
            {hmPack?.strategic_alignment && (
              <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/60">
                <h4 className="text-xs uppercase tracking-wider font-semibold text-indigo-400 mb-2 flex items-center gap-1.5">
                  <FiTrendingUp className="w-4 h-4" /> Alignement Stratégique & Enjeux d'Équipe
                </h4>
                <p className="text-slate-100 leading-relaxed">
                  {hmPack.strategic_alignment}
                </p>
              </div>
            )}

            {hmPack?.internal_vocabulary && hmPack.internal_vocabulary.length > 0 && (
              <div>
                <h4 className="text-xs uppercase tracking-wider font-semibold text-purple-400 mb-2 flex items-center gap-1.5">
                  <FiLayers className="w-4 h-4" /> Vocabulaire Interne Clé à employer
                </h4>
                <div className="flex flex-wrap gap-2">
                  {hmPack.internal_vocabulary.map((term, idx) => (
                    <span
                      key={idx}
                      className="px-3 py-1 rounded-full text-xs font-medium bg-purple-500/10 text-purple-300 border border-purple-500/20"
                    >
                      {term}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {hmPack?.sharp_questions && hmPack.sharp_questions.length > 0 && (
              <div>
                <h4 className="text-xs uppercase tracking-wider font-semibold text-amber-400 mb-2 flex items-center gap-1.5">
                  <FiHelpCircle className="w-4 h-4" /> Questions ciblées pour le Manager
                </h4>
                <ul className="space-y-2">
                  {hmPack.sharp_questions.map((q, idx) => (
                    <li
                      key={idx}
                      className="p-3 rounded-lg bg-slate-800/40 border border-slate-800 text-xs text-slate-200"
                    >
                      {q}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* Tech Panel Tab */}
        {activeTab === "tech" && (
          <div className="space-y-6">
            {techPack?.architecture_points && techPack.architecture_points.length > 0 && (
              <div>
                <h4 className="text-xs uppercase tracking-wider font-semibold text-emerald-400 mb-2 flex items-center gap-1.5">
                  <FiCpu className="w-4 h-4" /> Forces d'Architecture à mettre en avant
                </h4>
                <ul className="space-y-2">
                  {techPack.architecture_points.map((pt, idx) => (
                    <li
                      key={idx}
                      className="p-3 rounded-lg bg-emerald-950/10 border border-emerald-800/20 text-xs text-emerald-200/90"
                    >
                      {pt}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {techPack?.tradeoffs_and_risks && techPack.tradeoffs_and_risks.length > 0 && (
              <div>
                <h4 className="text-xs uppercase tracking-wider font-semibold text-amber-400 mb-2 flex items-center gap-1.5">
                  <FiAlertTriangle className="w-4 h-4" /> Compromis Techniques & Risques assumés
                </h4>
                <ul className="space-y-2">
                  {techPack.tradeoffs_and_risks.map((tr, idx) => (
                    <li
                      key={idx}
                      className="p-3 rounded-lg bg-amber-950/10 border border-amber-800/20 text-xs text-amber-200/90"
                    >
                      {tr}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {techPack?.reverse_questions && techPack.reverse_questions.length > 0 && (
              <div>
                <h4 className="text-xs uppercase tracking-wider font-semibold text-sky-400 mb-2 flex items-center gap-1.5">
                  <FiHelpCircle className="w-4 h-4" /> Questions inverses sur le quotidien d'ingénierie
                </h4>
                <ul className="space-y-2">
                  {techPack.reverse_questions.map((q, idx) => (
                    <li
                      key={idx}
                      className="p-3 rounded-lg bg-slate-800/40 border border-slate-800 text-xs text-slate-200"
                    >
                      {q}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
