"use client";

import React from "react";
import { RewriteProposal } from "@/hooks/useCoverLetter";
import { FiRefreshCw, FiAlertCircle, FiCheck, FiZap, FiX } from "react-icons/fi";

const QUICK_INSTRUCTIONS = [
  "Plus percutant",
  "Plus concis",
  "Corriger",
  "Plus naturel",
];

interface CoverLetterRewriteBoxProps {
  proposal: RewriteProposal | null;
  staleError: string | null;
  selectedPassage: string;
  customInstruction: string;
  rewriting: boolean;
  isPending: boolean;
  rewriteError: string | null;
  onCustomInstructionChange: (value: string) => void;
  onRewrite: (instruction: string) => void;
  onAcceptProposal: () => void;
  onRejectProposal: () => void;
}

/**
 * Renders either the side-by-side rewrite proposal diff or the passage rewrite instruction bar.
 */
export function CoverLetterRewriteBox({
  proposal,
  staleError,
  selectedPassage,
  customInstruction,
  rewriting,
  isPending,
  rewriteError,
  onCustomInstructionChange,
  onRewrite,
  onAcceptProposal,
  onRejectProposal,
}: CoverLetterRewriteBoxProps) {
  if (proposal) {
    return (
      <div className="p-4 rounded-xl bg-blue-950/30 border border-blue-500/40 space-y-3 shadow-lg">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FiZap className="text-blue-400" />
            <h4 className="text-sm font-semibold text-white">
              Proposition d&apos;amélioration ciblée
            </h4>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onRejectProposal}
              className="px-3 py-1.5 text-xs text-gray-300 hover:text-white bg-gray-800 hover:bg-gray-700 rounded-lg border border-gray-700 transition-colors flex items-center gap-1.5"
            >
              <FiX />
              <span>Rejeter</span>
            </button>
            <button
              type="button"
              onClick={onAcceptProposal}
              className="px-3 py-1.5 text-xs font-medium text-white bg-green-600 hover:bg-green-500 rounded-lg transition-colors flex items-center gap-1.5 shadow-sm"
            >
              <FiCheck />
              <span>Accepter</span>
            </button>
          </div>
        </div>

        {staleError && (
          <div className="p-2.5 rounded-lg bg-red-950/40 border border-red-800/50 text-xs text-red-300 flex items-center gap-2">
            <FiAlertCircle className="shrink-0 text-red-400" />
            <span>{staleError}</span>
          </div>
        )}

        {proposal.warnings.length > 0 && (
          <div className="p-2.5 rounded-lg bg-amber-950/40 border border-amber-800/50 text-xs text-amber-300 space-y-1">
            {proposal.warnings.map((warn, i) => (
              <div key={i} className="flex items-center gap-2">
                <FiAlertCircle className="shrink-0 text-amber-400" />
                <span>{warn}</span>
              </div>
            ))}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
          <div className="p-3 rounded-lg bg-gray-900/90 border border-gray-800">
            <div className="text-[11px] font-semibold text-gray-400 uppercase tracking-wide mb-1.5">
              Passage original
            </div>
            <div className="text-gray-300 whitespace-pre-wrap font-sans leading-relaxed">
              {proposal.originalPassage}
            </div>
          </div>
          <div className="p-3 rounded-lg bg-blue-900/20 border border-blue-500/30">
            <div className="text-[11px] font-semibold text-blue-300 uppercase tracking-wide mb-1.5">
              Texte réécrit
            </div>
            <div className="text-white whitespace-pre-wrap font-sans leading-relaxed">
              {proposal.rewritten}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-3.5 rounded-xl bg-gray-900/80 border border-gray-800 space-y-2.5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-xs">
          <FiZap className="text-blue-400" />
          <span className="font-medium text-gray-200">
            Améliorer une partie ciblée
          </span>
          {selectedPassage ? (
            <span className="text-gray-400 text-[11px] truncate max-w-xs">
              ({selectedPassage.length} car. sélectionnés)
            </span>
          ) : (
            <span className="text-gray-500 text-[11px]">
              (sélectionnez d&apos;abord du texte dans l&apos;éditeur)
            </span>
          )}
        </div>

        {/* Quick instruction chips */}
        <div className="flex flex-wrap items-center gap-1.5">
          {QUICK_INSTRUCTIONS.map((chip) => (
            <button
              key={chip}
              type="button"
              disabled={!selectedPassage || rewriting || isPending}
              onClick={() => onRewrite(chip)}
              className="px-2 py-1 text-[11px] font-medium rounded-md bg-gray-800 hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed text-gray-300 hover:text-white border border-gray-700/80 transition-colors"
            >
              {chip}
            </button>
          ))}
        </div>
      </div>

      {/* Custom instruction input + submit button */}
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={customInstruction}
          onChange={(e) => onCustomInstructionChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && selectedPassage && !rewriting && !isPending) {
              e.preventDefault();
              onRewrite(customInstruction);
            }
          }}
          disabled={!selectedPassage || rewriting || isPending}
          placeholder={
            selectedPassage
              ? "Consigne libre (ex: insister sur les résultats, ton plus formel...)"
              : "Sélectionnez un passage ci-dessus pour activer la réécriture"
          }
          className="flex-1 bg-gray-950/80 text-gray-200 text-xs px-3 py-2 rounded-lg border border-gray-700/80 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed placeholder:text-gray-500"
        />
        <button
          type="button"
          disabled={!selectedPassage || rewriting || isPending}
          onClick={() => onRewrite(customInstruction)}
          className="px-3 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-medium rounded-lg flex items-center gap-1.5 transition-colors shadow-sm whitespace-nowrap"
        >
          {rewriting ? (
            <FiRefreshCw className="animate-spin text-xs" />
          ) : (
            <FiZap className="text-xs" />
          )}
          <span>{rewriting ? "Réécriture..." : "Proposer"}</span>
        </button>
      </div>

      {rewriteError && (
        <div className="p-2 rounded-lg bg-red-950/40 border border-red-800/40 text-xs text-red-300 flex items-center gap-2">
          <FiAlertCircle className="shrink-0 text-red-400" />
          <span>{rewriteError}</span>
        </div>
      )}
    </div>
  );
}
