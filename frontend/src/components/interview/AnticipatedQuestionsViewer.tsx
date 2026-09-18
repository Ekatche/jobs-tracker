"use client";

import React, { useState } from "react";
import { AnticipatedQuestion } from "@/types/interview";
import {
  FiHelpCircle,
  FiCheckCircle,
  FiBookOpen,
  FiFilter,
} from "react-icons/fi";

interface AnticipatedQuestionsViewerProps {
  questions: AnticipatedQuestion[];
}

export default function AnticipatedQuestionsViewer({
  questions,
}: AnticipatedQuestionsViewerProps) {
  const [filter, setFilter] = useState<"all" | "behavioral" | "technical">("all");

  const filteredQuestions = questions.filter((q) => {
    if (filter === "all") return true;
    return q.category?.toLowerCase() === filter;
  });

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <div className="flex items-center justify-between gap-3 bg-slate-900/60 p-3 rounded-xl border border-slate-800">
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <FiFilter className="w-4 h-4 text-slate-500" />
          <span>Filtrer :</span>
          <button
            type="button"
            onClick={() => setFilter("all")}
            className={`px-2.5 py-1 rounded-lg transition-colors ${
              filter === "all"
                ? "bg-indigo-600 text-white font-medium"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Toutes ({questions.length})
          </button>
          <button
            type="button"
            onClick={() => setFilter("behavioral")}
            className={`px-2.5 py-1 rounded-lg transition-colors ${
              filter === "behavioral"
                ? "bg-indigo-600 text-white font-medium"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Comportementales ({questions.filter((q) => q.category === "behavioral").length})
          </button>
          <button
            type="button"
            onClick={() => setFilter("technical")}
            className={`px-2.5 py-1 rounded-lg transition-colors ${
              filter === "technical"
                ? "bg-indigo-600 text-white font-medium"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Techniques ({questions.filter((q) => q.category === "technical").length})
          </button>
        </div>
      </div>

      {/* Questions list */}
      <div className="space-y-3">
        {filteredQuestions.map((q, idx) => {
          const isBehavioral = q.category?.toLowerCase() === "behavioral";
          return (
            <div
              key={q.id || idx}
              className="bg-slate-900/70 border border-slate-800 rounded-xl p-4 sm:p-5 shadow-md hover:border-slate-700 transition-colors"
            >
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <span
                  className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full border ${
                    isBehavioral
                      ? "bg-purple-500/10 text-purple-400 border-purple-500/20"
                      : "bg-cyan-500/10 text-cyan-400 border-cyan-500/20"
                  }`}
                >
                  {isBehavioral ? "Comportementale" : "Technique"}
                </span>

                {q.mapped_story_id && (
                  <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 flex items-center gap-1">
                    <FiBookOpen className="w-3 h-3 text-indigo-400" />
                    Histoire STAR+R liée
                  </span>
                )}
              </div>

              <h4 className="text-base font-semibold text-white mb-2 flex items-start gap-2">
                <FiHelpCircle className="w-5 h-5 text-indigo-400 shrink-0 mt-0.5" />
                <span>{q.question}</span>
              </h4>

              {q.why_it_will_be_asked && (
                <p className="text-xs text-slate-400 italic mb-3 pl-7">
                  🎯 <strong>Pourquoi :</strong> {q.why_it_will_be_asked}
                </p>
              )}

              {q.key_points_to_cover && q.key_points_to_cover.length > 0 && (
                <div className="pl-7 pt-2 border-t border-slate-800/80">
                  <strong className="text-xs text-slate-300 block mb-1.5 font-medium">
                    Points clés à couvrir (Niveau Senior) :
                  </strong>
                  <ul className="space-y-1">
                    {q.key_points_to_cover.map((pt, pIdx) => (
                      <li key={pIdx} className="flex items-start gap-2 text-xs text-slate-300">
                        <FiCheckCircle className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                        <span>{pt}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
