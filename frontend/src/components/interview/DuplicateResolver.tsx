"use client";

import React, { useState } from "react";
import { starBankApi } from "@/lib/api";
import { BankStory, StoryDuplicate } from "@/types/interview";
import { FiAlertCircle, FiChevronDown, FiChevronUp } from "react-icons/fi";

interface DuplicateResolverProps {
  duplicate: StoryDuplicate;
  current: BankStory;
  otherInThisKit: boolean;
  onResolved: () => Promise<void> | void;
}

const FACT_FIELDS: Array<[
  "situation" | "task" | "action" | "result" | "reflection",
  string
]> = [
  ["situation", "S — Situation & Contexte"],
  ["task", "T — Mission & Rôle"],
  ["action", "A — Actions & Choix Techniques"],
  ["result", "R — Résultats & Métriques"],
  ["reflection", "+R — Réflexion & Apprentissages"],
];

function resultHint(result: string): string {
  const numbers = result.match(/[−+-]?\d+(?:[.,]\d+)?\s?%?/g);
  if (numbers && numbers.length > 0) {
    return numbers.slice(0, 2).map((n) => n.trim()).join(", ");
  }
  const trimmed = result.trim();
  if (trimmed.length <= 60) return trimmed;
  return `${trimmed.slice(0, 60).trimEnd()}…`;
}

function StoryColumn({ label, story }: { label: string; story: BankStory }) {
  return (
    <div className="flex-1 min-w-0 bg-slate-950/40 border border-slate-800 rounded-lg p-3 space-y-2">
      <span className="text-[11px] uppercase tracking-wider text-slate-400 font-medium block">
        {label}
      </span>
      <h5 className="text-sm font-semibold text-white">{story.title}</h5>
      {FACT_FIELDS.map(([field, fieldLabel]) => (
        <div key={field}>
          <strong className="text-[10px] uppercase text-slate-500 tracking-wider block mb-0.5">
            {fieldLabel}
          </strong>
          <p className="text-xs text-slate-300 leading-relaxed">{story[field]}</p>
        </div>
      ))}
    </div>
  );
}

export default function DuplicateResolver({
  duplicate,
  current,
  otherInThisKit,
  onResolved,
}: DuplicateResolverProps) {
  const [expanded, setExpanded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const other = duplicate.other_story;
  const otherColumnLabel = otherInThisKit ? "Autre ligne de ce kit" : "Dans un autre kit";
  const otherLocationPhrase = otherInThisKit ? "dans une autre ligne de ce kit" : "dans un autre kit";

  const handleKeep = async (keepId: string, discardId: string) => {
    try {
      setBusy(true);
      setError(null);
      await starBankApi.merge(keepId, discardId);
      await onResolved();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Impossible de fusionner ces histoires.";
      setError(msg);
    } finally {
      setBusy(false);
    }
  };

  const handleMarkDifferent = async () => {
    try {
      setBusy(true);
      setError(null);
      await starBankApi.markDifferent(current.id, other.id);
      await onResolved();
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Impossible d'enregistrer ces histoires comme différentes.";
      setError(msg);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-xl bg-amber-500/10 border border-amber-500/20 p-3 sm:p-4 space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p className="text-xs text-amber-200/90 leading-relaxed">
          {`« ${current.title} » est racontée avec « ${resultHint(other.result)} » ${otherLocationPhrase} et « ${resultHint(current.result)} » ici.`}
        </p>
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="shrink-0 text-xs font-medium text-amber-300 hover:text-amber-200 flex items-center gap-1 transition-colors"
        >
          Choisir la bonne version
          {expanded ? <FiChevronUp className="w-3.5 h-3.5" /> : <FiChevronDown className="w-3.5 h-3.5" />}
        </button>
      </div>

      {error && (
        <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/20 text-xs text-rose-300 flex items-center gap-2">
          <FiAlertCircle className="w-3.5 h-3.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {expanded && (
        <div className="space-y-3">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            <div className="space-y-2">
              <StoryColumn label="Ici" story={current} />
              <button
                type="button"
                disabled={busy}
                onClick={() => handleKeep(current.id, other.id)}
                className="w-full px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white transition-colors disabled:opacity-50"
              >
                Garder celle-ci
              </button>
            </div>
            <div className="space-y-2">
              <StoryColumn label={otherColumnLabel} story={other} />
              <button
                type="button"
                disabled={busy}
                onClick={() => handleKeep(other.id, current.id)}
                className="w-full px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white transition-colors disabled:opacity-50"
              >
                Garder celle-ci
              </button>
            </div>
          </div>
          <button
            type="button"
            disabled={busy}
            onClick={handleMarkDifferent}
            className="w-full px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors disabled:opacity-50"
          >
            Ce sont deux histoires différentes
          </button>
        </div>
      )}
    </div>
  );
}
