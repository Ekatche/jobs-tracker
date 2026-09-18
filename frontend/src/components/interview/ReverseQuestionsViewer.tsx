"use client";

import React from "react";
import { ReverseQuestion } from "@/types/interview";
import { FiShield, FiAlertCircle, FiMessageSquare } from "react-icons/fi";

interface ReverseQuestionsViewerProps {
  questions: ReverseQuestion[];
}

export default function ReverseQuestionsViewer({
  questions,
}: ReverseQuestionsViewerProps) {
  return (
    <div className="space-y-4">
      <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-200/90 flex items-start gap-3">
        <FiShield className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
        <p className="leading-relaxed">
          Inspiré du module <em>interview-redflag</em> de <strong>Career-Ops</strong> : Ces questions
          inversées sont conçues pour être posées avec courtoisie aux interviewers, tout en vous permettant
          d'auditer la réalité du terrain et de détecter d'éventuels signaux toxiques ou instables.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {questions.map((rq, idx) => (
          <div
            key={rq.id || idx}
            className="bg-slate-900/70 border border-slate-800 rounded-xl p-4 sm:p-5 flex flex-col justify-between shadow-md hover:border-slate-700 transition-colors"
          >
            <div>
              <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-slate-800 text-indigo-400 border border-slate-700 inline-block mb-2">
                {rq.category}
              </span>
              <h4 className="text-sm sm:text-base font-semibold text-white mb-3 flex items-start gap-2">
                <FiMessageSquare className="w-4 h-4 text-indigo-400 shrink-0 mt-1" />
                <span>{rq.question}</span>
              </h4>
            </div>

            <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800/80 text-xs text-slate-300 mt-2">
              <div className="flex items-center gap-1.5 text-amber-400 font-semibold mb-1">
                <FiAlertCircle className="w-3.5 h-3.5" />
                <span>Ce que révèle la réponse :</span>
              </div>
              <p className="leading-relaxed text-slate-300 italic">
                {rq.probe_intent}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
