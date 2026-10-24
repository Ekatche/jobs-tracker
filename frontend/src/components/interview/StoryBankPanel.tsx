"use client";

import React, { useCallback, useEffect, useState } from "react";
import { interviewPrepApi, starBankApi } from "@/lib/api";
import { BankExperience, BankGroup, BankStory, InterviewPrep } from "@/types/interview";
import { FiX, FiSearch, FiAlertCircle } from "react-icons/fi";

interface StoryBankPanelProps {
  offerId: string;
  prep: InterviewPrep | null;
  open: boolean;
  onClose: () => void;
  onPrepUpdated: (prep: InterviewPrep) => void;
}

function kitsLabel(count: number): string {
  return `utilisée dans ${count} kit${count === 1 ? "" : "s"}`;
}

function matchesSearch(story: BankStory, query: string): boolean {
  if (!query) return true;
  const q = query.toLowerCase();
  return (
    story.title.toLowerCase().includes(q) ||
    story.result.toLowerCase().includes(q) ||
    story.situation.toLowerCase().includes(q) ||
    story.key_tags.some((tag) => tag.toLowerCase().includes(q))
  );
}

export default function StoryBankPanel({ offerId, prep, open, onClose, onPrepUpdated }: StoryBankPanelProps) {
  const [groups, setGroups] = useState<BankGroup[]>([]);
  const [experiences, setExperiences] = useState<BankExperience[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [savingStoryId, setSavingStoryId] = useState<string | null>(null);

  const loadBank = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await starBankApi.list();
      setGroups(data.groups);
      setExperiences(data.experiences);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Impossible de charger la banque d'histoires.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  // Recharge à l'ouverture, et chaque fois que `prep` change de référence pendant que le panneau
  // est ouvert (ex: « Utiliser pour… » qui passe par onPrepUpdated) : pas de rechargement
  // explicite dans les handlers, cet effet s'en charge seul pour éviter un double appel.
  useEffect(() => {
    if (!open) return;
    void loadBank();
  }, [open, prep, loadBank]);

  if (!open) return null;

  const storySlots = prep?.story_slots ?? [];
  const storyIdsInKit = new Set(
    storySlots.map((slot) => slot.story_id).filter((id): id is string => !!id)
  );
  const anyBusy = savingStoryId !== null;

  const handlePick = async (story: BankStory, slotId: string) => {
    try {
      setSavingStoryId(story.id);
      setError(null);
      const updated = await interviewPrepApi.updateSlot(offerId, slotId, { story_id: story.id });
      onPrepUpdated(updated);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Impossible d'utiliser cette histoire pour cette ligne.";
      setError(msg);
    } finally {
      setSavingStoryId(null);
    }
  };

  const handleAttach = async (story: BankStory, experience: BankExperience) => {
    const { label, ...rest } = experience;
    void label;
    try {
      setSavingStoryId(story.id);
      setError(null);
      await starBankApi.updateFacts(story.id, { experience: rest });
      // La liste du kit ne change pas ici : seule la banque doit être rechargée.
      await loadBank();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Impossible de rattacher cette histoire à une expérience.";
      setError(msg);
    } finally {
      setSavingStoryId(null);
    }
  };

  const filteredGroups = groups
    .map((group) => ({ ...group, stories: group.stories.filter((story) => matchesSearch(story, search)) }))
    .filter((group) => group.stories.length > 0);

  const isEmptyBank = !loading && groups.length === 0;
  const isNoMatch = !loading && !isEmptyBank && filteredGroups.length === 0;

  return (
    <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-4 space-y-3 lg:sticky lg:top-4 h-fit">
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-sm font-semibold text-white">Ma banque d&apos;histoires</h4>
        <button
          type="button"
          onClick={onClose}
          aria-label="Fermer la banque d'histoires"
          className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
        >
          <FiX className="w-4 h-4" />
        </button>
      </div>

      <div className="relative">
        <FiSearch className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Rechercher…"
          className="w-full rounded-lg bg-slate-950/60 border border-slate-700 pl-8 pr-3 py-1.5 text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
        />
      </div>

      {error && (
        <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/20 text-xs text-rose-300 flex items-center gap-2">
          <FiAlertCircle className="w-3.5 h-3.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <p className="text-xs text-slate-500">Chargement…</p>
      ) : isEmptyBank ? (
        <p className="text-xs text-slate-500">Votre banque d&apos;histoires est vide pour l&apos;instant.</p>
      ) : isNoMatch ? (
        <p className="text-xs text-slate-500">Aucune histoire ne correspond à cette recherche.</p>
      ) : (
        <div className="space-y-3 max-h-[70vh] overflow-y-auto pr-1">
          {filteredGroups.map((group, groupIndex) => (
            <div key={`${group.label}-${groupIndex}`}>
              <div className="text-[11px] uppercase tracking-wider text-slate-500 mb-1.5">{group.label}</div>
              <div className="space-y-2">
                {group.stories.map((story) => {
                  const inKit = storyIdsInKit.has(story.id);
                  return (
                    <div key={story.id} className="bg-slate-800/60 border border-slate-700 rounded-lg p-2.5">
                      <p className="text-xs font-semibold text-slate-100">{story.title}</p>
                      <p className="text-[11px] text-slate-400 mt-0.5">
                        Résultat : <span className="text-emerald-400">{story.result}</span> ·{" "}
                        {kitsLabel(story.used_in_kits ?? 0)}
                      </p>
                      <div className="mt-2 flex flex-col gap-1.5">
                        {inKit ? (
                          <span className="text-[11px] font-medium text-emerald-400">✓ dans ce kit</span>
                        ) : (
                          <select
                            value=""
                            disabled={anyBusy || storySlots.length === 0}
                            onChange={(e) => {
                              const slotId = e.target.value;
                              if (slotId) void handlePick(story, slotId);
                            }}
                            className="w-full rounded-lg bg-slate-950/60 border border-slate-700 px-2 py-1 text-[11px] text-slate-200 focus:outline-none focus:border-indigo-500 disabled:opacity-50"
                          >
                            <option value="" disabled>
                              Utiliser pour…
                            </option>
                            {storySlots.map((slot) => (
                              <option key={slot.id} value={slot.id}>
                                {slot.requirement}
                              </option>
                            ))}
                          </select>
                        )}

                        {group.experience === null && (
                          <select
                            value=""
                            disabled={anyBusy || experiences.length === 0}
                            onChange={(e) => {
                              const exp = experiences.find((candidate) => candidate.label === e.target.value);
                              if (exp) void handleAttach(story, exp);
                            }}
                            className="w-full rounded-lg bg-slate-950/60 border border-slate-700 px-2 py-1 text-[11px] text-slate-200 focus:outline-none focus:border-indigo-500 disabled:opacity-50"
                          >
                            <option value="" disabled>
                              Rattacher à une expérience…
                            </option>
                            {experiences.map((exp) => (
                              <option key={exp.label} value={exp.label}>
                                {exp.label}
                              </option>
                            ))}
                          </select>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
