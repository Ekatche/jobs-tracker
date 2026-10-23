"use client";

import React, { useState } from "react";
import { interviewPrepApi } from "@/lib/api";
import { AnticipatedQuestion, InterviewPrep, PracticeAttempt } from "@/types/interview";
import { FiAlertCircle, FiClock, FiEdit3, FiLoader, FiSend } from "react-icons/fi";

const CRITERION_LABELS: Record<string, string> = {
  structure: "Structure",
  quantified_result: "Résultat chiffré",
  offer_fit: "Adéquation à l'offre",
  coverage: "Points clés et histoire",
};

interface PracticePanelProps {
  offerId: string;
  question: AnticipatedQuestion;
  attempts: PracticeAttempt[];
  onPrepUpdated: (prep: InterviewPrep) => void;
}

// Mongo renvoie des dates UTC sans fuseau : sans le « Z », le navigateur les lirait en heure locale.
function parseServerDate(value: string): Date {
  return new Date(/(Z|[+-]\d{2}:?\d{2})$/i.test(value) ? value : `${value}Z`);
}

function formatScore(score: number): string {
  return score.toLocaleString("fr-FR", { maximumFractionDigits: 1 });
}

function scoreColor(score: number): string {
  if (score >= 4) return "text-emerald-400";
  if (score >= 3) return "text-amber-400";
  return "text-rose-400";
}

export default function PracticePanel({ offerId, question, attempts, onPrepUpdated }: PracticePanelProps) {
  const [draft, setDraft] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Par défaut, l'essai le plus récent (le backend ajoute en fin de liste).
  const shown = attempts.find((a) => a.id === selectedId) ?? attempts[attempts.length - 1];

  const handleSubmit = async () => {
    if (!draft.trim() || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const updated = await interviewPrepApi.practice(offerId, question.id, draft.trim());
      onPrepUpdated(updated);
      setSelectedId(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Impossible d'évaluer la réponse.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mt-3 pl-7 pt-3 border-t border-slate-800/80 space-y-4">
      <div className="space-y-2">
        <label htmlFor={`practice-${question.id}`} className="text-xs text-slate-300 font-medium block">
          Votre réponse (comme à l&apos;oral) :
        </label>
        <textarea
          id={`practice-${question.id}`}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          maxLength={6000}
          rows={6}
          disabled={submitting}
          placeholder="Situation, tâche, action, résultat…"
          className="w-full bg-slate-950/60 border border-slate-800 rounded-lg p-3 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-indigo-500 disabled:opacity-60"
        />
        <div className="flex items-center justify-between gap-3">
          <span className="text-[11px] text-slate-500">
            {draft.length} / 6000
          </span>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!draft.trim() || submitting}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? <FiLoader className="w-3.5 h-3.5 animate-spin" /> : <FiSend className="w-3.5 h-3.5" />}
            {submitting ? "Analyse en cours…" : "Obtenir un retour"}
          </button>
        </div>
        {error && (
          <p className="flex items-start gap-1.5 text-xs text-rose-400">
            <FiAlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
            <span>{error}</span>
          </p>
        )}
      </div>

      {shown && (
        <div className="bg-slate-950/40 border border-slate-800 rounded-lg p-3 sm:p-4 space-y-3">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <span className="text-xs text-slate-400">
              Essai du {parseServerDate(shown.created_at).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" })}
            </span>
            <span className={`text-lg font-bold ${scoreColor(shown.overall_score)}`}>
              {formatScore(shown.overall_score)} / 5
            </span>
          </div>

          <details className="text-xs">
            <summary className="cursor-pointer text-slate-400 hover:text-slate-200">Votre réponse</summary>
            <p className="mt-1.5 text-slate-300 whitespace-pre-line leading-relaxed">{shown.answer}</p>
          </details>

          <ul className="space-y-2">
            {shown.criteria.map((c) => (
              <li key={c.key} className="text-xs">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-slate-200 font-medium">{CRITERION_LABELS[c.key] ?? c.key}</span>
                  <span className={`font-semibold ${scoreColor(c.score)}`}>{c.score} / 5</span>
                </div>
                {c.comment && <p className="text-slate-400 mt-0.5">{c.comment}</p>}
              </li>
            ))}
          </ul>

          {shown.missing.length > 0 && (
            <div className="pt-2 border-t border-slate-800/80">
              <strong className="text-xs text-slate-300 block mb-1.5 font-medium">Ce qui manque :</strong>
              <ul className="list-disc pl-4 space-y-1 text-xs text-slate-300">
                {shown.missing.map((m, idx) => (
                  <li key={idx}>{m}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="pt-2 border-t border-slate-800/80">
            <strong className="text-xs text-slate-300 mb-1.5 font-medium flex items-center gap-1.5">
              <FiEdit3 className="w-3.5 h-3.5 text-indigo-400" />
              Version retravaillée :
            </strong>
            <p className="text-xs text-slate-200 whitespace-pre-line leading-relaxed">{shown.improved_answer}</p>
          </div>
        </div>
      )}

      {attempts.length > 1 && (
        <div>
          <strong className="text-xs text-slate-300 mb-1.5 font-medium flex items-center gap-1.5">
            <FiClock className="w-3.5 h-3.5 text-slate-500" />
            Historique ({attempts.length} essais) :
          </strong>
          <ul className="space-y-1">
            {attempts
              .map((a, idx) => ({ a, delta: idx > 0 ? a.overall_score - attempts[idx - 1].overall_score : null }))
              .reverse()
              .map(({ a, delta }) => (
                <li key={a.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(a.id)}
                    className={`w-full flex items-center justify-between gap-2 px-2.5 py-1.5 rounded-lg text-xs transition-colors ${
                      a.id === shown?.id ? "bg-indigo-600/20 text-white" : "text-slate-400 hover:bg-slate-800/60"
                    }`}
                  >
                    <span>
                      {parseServerDate(a.created_at).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" })}
                    </span>
                    <span className="flex items-center gap-2">
                      {delta !== null && Math.abs(delta) >= 0.05 && (
                        <span className={delta > 0 ? "text-emerald-400" : "text-rose-400"}>
                          {delta > 0 ? "+" : ""}
                          {formatScore(delta)}
                        </span>
                      )}
                      <span className={`font-semibold ${scoreColor(a.overall_score)}`}>{formatScore(a.overall_score)} / 5</span>
                    </span>
                  </button>
                </li>
              ))}
          </ul>
        </div>
      )}
    </div>
  );
}
