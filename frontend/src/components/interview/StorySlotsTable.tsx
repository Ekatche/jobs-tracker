"use client";

import React, { useRef, useState } from "react";
import { interviewPrepApi, starBankApi } from "@/lib/api";
import { InterviewPrep, StoryFacts, StoryFit, StorySlot } from "@/types/interview";
import StarStoryCard from "./StarStoryCard";
import DuplicateResolver from "./DuplicateResolver";
import {
  FiZap,
  FiEdit2,
  FiTrash2,
  FiX,
  FiAlertCircle,
  FiChevronRight,
} from "react-icons/fi";

interface StorySlotsTableProps {
  prep: InterviewPrep;
  offerId: string;
  onPrepUpdated: (prep: InterviewPrep) => void;
  onOpenBank: () => void;
}

const FIT_LABELS: Record<StoryFit, string> = {
  strong: "forte",
  partial: "partielle",
  transferable: "transférable",
  gap: "manque",
  no_experience: "pas d'expérience dans ton profil",
  manual: "choisie",
};

const FIT_STYLES: Record<StoryFit, string> = {
  strong: "bg-emerald-500/15 text-emerald-400 border border-emerald-500/20",
  partial: "bg-amber-500/15 text-amber-400 border border-amber-500/20",
  transferable: "bg-amber-500/15 text-amber-400 border border-amber-500/20",
  gap: "bg-rose-500/15 text-rose-400 border border-rose-500/20",
  no_experience: "bg-rose-500/15 text-rose-400 border border-rose-500/20",
  manual: "bg-indigo-500/15 text-indigo-400 border border-indigo-500/20",
};

const emptyFacts: StoryFacts = {
  title: "",
  theme: "Général",
  situation: "",
  task: "",
  action: "",
  result: "",
  reflection: "",
  key_tags: [],
};

function FitPill({ fit }: { fit: StoryFit }) {
  return (
    <span className={`text-[11px] font-medium px-2.5 py-0.5 rounded-full whitespace-nowrap ${FIT_STYLES[fit]}`}>
      {FIT_LABELS[fit]}
    </span>
  );
}

export default function StorySlotsTable({ prep, offerId, onPrepUpdated, onOpenBank }: StorySlotsTableProps) {
  const [expandedSlotId, setExpandedSlotId] = useState<string | null>(null);
  const [requirementDraft, setRequirementDraft] = useState("");
  const [angleDraft, setAngleDraft] = useState("");
  const [savingField, setSavingField] = useState<"requirement" | "angle" | null>(null);

  const [manualFormSlotId, setManualFormSlotId] = useState<string | null>(null);
  const [manualDraft, setManualDraft] = useState<StoryFacts>(emptyFacts);
  const [manualTags, setManualTags] = useState("");
  const [manualSaving, setManualSaving] = useState(false);

  const [writingSlotId, setWritingSlotId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const [error, setError] = useState<string | null>(null);

  const slots = prep.story_slots ?? [];
  const expandedSlot = slots.find((s) => s.id === expandedSlotId) ?? null;

  const handleToggleRow = (slot: StorySlot) => {
    if (!slot.story) return;
    setManualFormSlotId(null);
    setError(null);
    if (expandedSlotId === slot.id) {
      setExpandedSlotId(null);
      return;
    }
    setExpandedSlotId(slot.id);
    setRequirementDraft(slot.requirement);
    setAngleDraft(slot.angle);
  };

  const handleWriteSlot = async (slotId: string) => {
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      setWritingSlotId(slotId);
      setError(null);
      const updated = await interviewPrepApi.writeSlot(offerId, slotId, controller.signal);
      onPrepUpdated(updated);
    } catch (err: unknown) {
      if (controller.signal.aborted) return;
      const msg = err instanceof Error ? err.message : "Erreur lors de l'écriture de l'histoire.";
      setError(msg);
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
        setWritingSlotId(null);
      }
    }
  };

  const handleCancelWrite = () => {
    abortRef.current?.abort();
  };

  const openManualForm = (slotId: string) => {
    setManualDraft(emptyFacts);
    setManualTags("");
    setManualFormSlotId(slotId);
    setExpandedSlotId(null);
    setError(null);
  };

  const closeManualForm = () => {
    setManualFormSlotId(null);
  };

  const handleSaveManualStory = async () => {
    if (!manualFormSlotId) return;
    try {
      setManualSaving(true);
      setError(null);
      const facts: StoryFacts = {
        ...manualDraft,
        key_tags: manualTags.split(",").map((t) => t.trim()).filter(Boolean),
      };
      const updated = await interviewPrepApi.createManualStory(offerId, manualFormSlotId, facts);
      onPrepUpdated(updated);
      setManualFormSlotId(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Impossible d'enregistrer l'histoire.";
      setError(msg);
    } finally {
      setManualSaving(false);
    }
  };

  const handleDeleteSlot = async (slotId: string) => {
    if (!confirm("Retirer cette ligne du kit ?")) return;
    try {
      setError(null);
      const updated = await interviewPrepApi.deleteSlot(offerId, slotId);
      onPrepUpdated(updated);
      if (expandedSlotId === slotId) setExpandedSlotId(null);
      if (manualFormSlotId === slotId) setManualFormSlotId(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Impossible de retirer la ligne.";
      setError(msg);
    }
  };

  const handleSaveRequirement = async () => {
    if (!expandedSlotId) return;
    try {
      setSavingField("requirement");
      setError(null);
      const updated = await interviewPrepApi.updateSlot(offerId, expandedSlotId, {
        requirement: requirementDraft,
      });
      onPrepUpdated(updated);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Impossible d'enregistrer l'exigence.";
      setError(msg);
    } finally {
      setSavingField(null);
    }
  };

  const handleSaveAngle = async () => {
    if (!expandedSlotId) return;
    try {
      setSavingField("angle");
      setError(null);
      const updated = await interviewPrepApi.updateSlot(offerId, expandedSlotId, {
        angle: angleDraft,
      });
      onPrepUpdated(updated);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Impossible d'enregistrer l'angle.";
      setError(msg);
    } finally {
      setSavingField(null);
    }
  };

  const handleSaveFacts = async (storyId: string, facts: StoryFacts) => {
    await starBankApi.updateFacts(storyId, facts);
    const updated = await interviewPrepApi.get(offerId);
    onPrepUpdated(updated);
  };

  const handleDuplicateResolved = async () => {
    const updated = await interviewPrepApi.get(offerId);
    onPrepUpdated(updated);
  };

  const handleRestoreVersion = async (storyId: string, versionId: string) => {
    await starBankApi.restore(storyId, versionId);
    const updated = await interviewPrepApi.get(offerId);
    onPrepUpdated(updated);
  };

  const handleDeleteStory = async (storyId: string) => {
    await starBankApi.remove(storyId);
    const updated = await interviewPrepApi.get(offerId);
    onPrepUpdated(updated);
    if (expandedSlot?.story?.id === storyId) setExpandedSlotId(null);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h4 className="text-sm font-semibold text-white">Histoires pour cette offre</h4>
        <button
          type="button"
          onClick={onOpenBank}
          className="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1 transition-colors shrink-0"
        >
          <span>Toute ma banque ({prep.bank_count})</span>
          <FiChevronRight className="w-3.5 h-3.5" />
        </button>
      </div>

      {error && (
        <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-300 flex items-center gap-2">
          <FiAlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="overflow-x-auto rounded-xl border border-slate-800">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-900/60 text-left text-[11px] uppercase tracking-wider text-slate-400">
              <th className="px-4 py-2.5 font-medium">Ce que l&apos;offre demande</th>
              <th className="px-4 py-2.5 font-medium">Ton histoire</th>
              <th className="px-4 py-2.5 font-medium">Adéquation</th>
              <th className="px-4 py-2.5 font-medium w-10"></th>
            </tr>
          </thead>
          <tbody>
            {slots.map((slot) => {
              const isWriting = writingSlotId === slot.id;
              return (
                <tr
                  key={slot.id}
                  className={`border-t border-slate-800/80 ${
                    slot.story ? "cursor-pointer hover:bg-slate-800/30" : ""
                  } ${expandedSlotId === slot.id ? "bg-indigo-950/30" : "bg-slate-900/20"}`}
                  onClick={() => handleToggleRow(slot)}
                >
                  <td className="px-4 py-3 align-top text-slate-200">{slot.requirement}</td>
                  <td className="px-4 py-3 align-top">
                    {slot.story ? (
                      <span className="text-slate-100 font-medium">{slot.story.title}</span>
                    ) : (
                      <div className="flex flex-wrap items-center gap-2 text-slate-500">
                        <span>
                          {slot.fit === "no_experience" ? "Sans expérience rattachée" : "Aucune ne répond"}
                        </span>
                        {slot.fit === "gap" && !isWriting && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleWriteSlot(slot.id);
                            }}
                            disabled={writingSlotId !== null || manualSaving}
                            className="px-2.5 py-1 rounded-lg text-[11px] font-semibold bg-indigo-600/90 hover:bg-indigo-600 text-white flex items-center gap-1 transition-colors disabled:opacity-50"
                          >
                            <FiZap className="w-3 h-3" />
                            Écrire avec l&apos;IA
                          </button>
                        )}
                        {isWriting && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleCancelWrite();
                            }}
                            className="px-2.5 py-1 rounded-lg text-[11px] font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1 transition-colors"
                          >
                            <FiX className="w-3 h-3" />
                            Annuler
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            openManualForm(slot.id);
                          }}
                          disabled={isWriting || manualSaving}
                          className="px-2.5 py-1 rounded-lg text-[11px] font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1 transition-colors disabled:opacity-50"
                        >
                          <FiEdit2 className="w-3 h-3" />
                          L&apos;écrire moi-même
                        </button>
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 align-top">
                    <FitPill fit={slot.fit} />
                  </td>
                  <td className="px-4 py-3 align-top text-right">
                    <button
                      type="button"
                      title="Retirer la ligne"
                      aria-label="Retirer la ligne"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteSlot(slot.id);
                      }}
                      className="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                    >
                      <FiTrash2 className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Manual story form */}
      {manualFormSlotId && (
        <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-4 sm:p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h5 className="text-sm font-semibold text-white">Écrire l&apos;histoire moi-même</h5>
            <button
              type="button"
              onClick={closeManualForm}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white transition-colors"
            >
              <FiX className="w-4 h-4" />
            </button>
          </div>
          <label className="block">
            <span className="text-xs uppercase text-slate-400 tracking-wider block mb-1">Titre</span>
            <input
              type="text"
              value={manualDraft.title}
              onChange={(e) => setManualDraft({ ...manualDraft, title: e.target.value })}
              className="w-full rounded-lg bg-slate-950/60 border border-slate-700 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
            />
          </label>
          <label className="block">
            <span className="text-xs uppercase text-slate-400 tracking-wider block mb-1">Thème</span>
            <input
              type="text"
              value={manualDraft.theme}
              onChange={(e) => setManualDraft({ ...manualDraft, theme: e.target.value })}
              className="w-full rounded-lg bg-slate-950/60 border border-slate-700 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
            />
          </label>
          {([
            ["situation", "S — Situation & Contexte"],
            ["task", "T — Mission & Rôle"],
            ["action", "A — Actions & Choix Techniques"],
            ["result", "R — Résultats & Métriques"],
            ["reflection", "+R — Réflexion & Apprentissages"],
          ] as const).map(([field, label]) => (
            <label className="block" key={field}>
              <span className="text-xs uppercase text-slate-400 tracking-wider block mb-1">{label}</span>
              <textarea
                value={manualDraft[field]}
                onChange={(e) => setManualDraft({ ...manualDraft, [field]: e.target.value })}
                rows={3}
                className="w-full rounded-lg bg-slate-950/60 border border-slate-700 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
              />
            </label>
          ))}
          <label className="block">
            <span className="text-xs uppercase text-slate-400 tracking-wider block mb-1">
              Mots-clés (séparés par des virgules)
            </span>
            <input
              type="text"
              value={manualTags}
              onChange={(e) => setManualTags(e.target.value)}
              className="w-full rounded-lg bg-slate-950/60 border border-slate-700 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
            />
          </label>
          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={closeManualForm}
              disabled={manualSaving}
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors disabled:opacity-50"
            >
              Annuler
            </button>
            <button
              type="button"
              onClick={handleSaveManualStory}
              disabled={manualSaving || manualDraft.title.trim() === ""}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white transition-colors disabled:opacity-50"
            >
              {manualSaving ? "Enregistrement..." : "Enregistrer"}
            </button>
          </div>
        </div>
      )}

      {/* Duplicate resolution banners */}
      {prep.duplicates.length > 0 && (
        <div className="space-y-3">
          {prep.duplicates.map((duplicate) => {
            const current = slots.find((s) => s.story_id === duplicate.story_id)?.story;
            if (!current) return null;
            const otherInThisKit = slots.some((s) => s.story_id === duplicate.other_story.id);
            return (
              <DuplicateResolver
                key={`${duplicate.story_id}-${duplicate.other_story.id}`}
                duplicate={duplicate}
                current={current}
                otherInThisKit={otherInThisKit}
                onResolved={handleDuplicateResolved}
              />
            );
          })}
        </div>
      )}

      {/* Selected slot detail */}
      {expandedSlot && expandedSlot.story && (
        <div className="space-y-3">
          <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-4 sm:p-5 space-y-3">
            <label className="block">
              <span className="text-xs uppercase text-slate-400 tracking-wider block mb-1">Exigence</span>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={requirementDraft}
                  onChange={(e) => setRequirementDraft(e.target.value)}
                  className="flex-1 rounded-lg bg-slate-950/60 border border-slate-700 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
                />
                <button
                  type="button"
                  onClick={handleSaveRequirement}
                  disabled={savingField !== null || requirementDraft === expandedSlot.requirement}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white transition-colors disabled:opacity-50 shrink-0"
                >
                  {savingField === "requirement" ? "..." : "Enregistrer"}
                </button>
              </div>
            </label>

            <label className="block">
              <span className="text-xs uppercase text-slate-400 tracking-wider block mb-1">
                Angle pour cette offre
              </span>
              <div className="flex gap-2">
                <textarea
                  value={angleDraft}
                  onChange={(e) => setAngleDraft(e.target.value)}
                  rows={2}
                  className="flex-1 rounded-lg bg-slate-950/60 border border-slate-700 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
                />
                <button
                  type="button"
                  onClick={handleSaveAngle}
                  disabled={savingField !== null || angleDraft === expandedSlot.angle}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white transition-colors disabled:opacity-50 shrink-0 self-start"
                >
                  {savingField === "angle" ? "..." : "Enregistrer"}
                </button>
              </div>
            </label>
          </div>

          <StarStoryCard
            key={expandedSlot.story.id}
            story={expandedSlot.story}
            usedInKits={expandedSlot.story.used_in_kits ?? 1}
            onSaveFacts={(facts) => handleSaveFacts(expandedSlot.story!.id, facts)}
            onRestoreVersion={(versionId) => handleRestoreVersion(expandedSlot.story!.id, versionId)}
            onDelete={() => handleDeleteStory(expandedSlot.story!.id)}
          />
        </div>
      )}
    </div>
  );
}
