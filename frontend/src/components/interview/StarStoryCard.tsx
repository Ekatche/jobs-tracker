"use client";

import React, { useState } from "react";
import { StarRStory } from "@/types/interview";
import {
  FiChevronDown,
  FiChevronUp,
  FiCopy,
  FiCheck,
  FiEdit2,
  FiTag,
  FiTarget,
} from "react-icons/fi";

interface StarStoryCardProps {
  story: StarRStory;
  index: number;
  onSave?: (story: StarRStory) => Promise<void>;
}

const fieldClass =
  "w-full rounded-lg bg-slate-950/60 border border-slate-700 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500";

export default function StarStoryCard({ story, index, onSave }: StarStoryCardProps) {
  const [isOpen, setIsOpen] = useState(true);
  const [copied, setCopied] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState<StarRStory>(story);
  const [tagsInput, setTagsInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const handleStartEdit = (e: React.MouseEvent) => {
    e.stopPropagation();
    setDraft(story);
    setTagsInput(story.key_tags?.join(", ") ?? "");
    setSaveError(null);
    setIsEditing(true);
    setIsOpen(true);
  };

  const handleSave = async () => {
    if (!onSave) return;
    try {
      setSaving(true);
      setSaveError(null);
      await onSave({
        ...draft,
        key_tags: tagsInput.split(",").map((tag) => tag.trim()).filter(Boolean),
      });
      setIsEditing(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Impossible d'enregistrer l'histoire.";
      setSaveError(msg);
    } finally {
      setSaving(false);
    }
  };

  const editField = (
    label: string,
    value: string,
    onChange: (value: string) => void,
    multiline = false
  ) => (
    <label className="block">
      <span className="text-xs uppercase text-slate-400 tracking-wider block mb-1">{label}</span>
      {multiline ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={3}
          className={fieldClass}
        />
      ) : (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={fieldClass}
        />
      )}
    </label>
  );

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    const text = `${story.title}\nThème: ${story.theme}\nCible: ${story.target_requirement}\n\n• S (Situation): ${story.situation}\n• T (Task): ${story.task}\n• A (Action): ${story.action}\n• R (Result): ${story.result}\n• +R (Reflection): ${story.reflection}`;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="bg-slate-900/70 border border-slate-800 rounded-xl overflow-hidden shadow-lg transition-all duration-200 hover:border-slate-700">
      {/* Header */}
      <div
        onClick={() => setIsOpen(!isOpen)}
        className="p-4 sm:p-5 flex items-start justify-between gap-3 cursor-pointer bg-slate-800/40 hover:bg-slate-800/60 transition-colors"
      >
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1.5">
            <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              #{index + 1} {story.theme}
            </span>
            {story.key_tags?.map((tag) => (
              <span
                key={tag}
                className="text-[11px] px-2 py-0.5 rounded bg-slate-800 text-slate-400 flex items-center gap-1 border border-slate-700/50"
              >
                <FiTag className="w-2.5 h-2.5" />
                {tag}
              </span>
            ))}
          </div>
          <h4 className="text-base sm:text-lg font-semibold text-white truncate">
            {story.title}
          </h4>
          {story.target_requirement && (
            <div className="flex items-center gap-1.5 text-xs text-slate-400 mt-1">
              <FiTarget className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
              <span className="truncate">
                Exigence ciblée :{" "}
                <strong className="text-slate-300 font-medium">
                  {story.target_requirement}
                </strong>
              </span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0 pt-1">
          {onSave && !isEditing && (
            <button
              type="button"
              onClick={handleStartEdit}
              title="Modifier l'histoire"
              className="p-1.5 rounded-lg text-slate-400 hover:text-white bg-slate-800/80 hover:bg-slate-700 border border-slate-700 transition-colors"
            >
              <FiEdit2 className="w-4 h-4" />
            </button>
          )}
          <button
            type="button"
            onClick={handleCopy}
            title="Copier l'histoire"
            className="p-1.5 rounded-lg text-slate-400 hover:text-white bg-slate-800/80 hover:bg-slate-700 border border-slate-700 transition-colors"
          >
            {copied ? (
              <FiCheck className="w-4 h-4 text-emerald-400" />
            ) : (
              <FiCopy className="w-4 h-4" />
            )}
          </button>
          <button
            type="button"
            className="p-1.5 rounded-lg text-slate-400 hover:text-white transition-colors"
          >
            {isOpen ? (
              <FiChevronUp className="w-5 h-5" />
            ) : (
              <FiChevronDown className="w-5 h-5" />
            )}
          </button>
        </div>
      </div>

      {/* Edit form */}
      {isOpen && isEditing && (
        <div className="p-4 sm:p-5 space-y-3 border-t border-slate-800/80 bg-slate-900/40">
          {editField("Titre", draft.title, (v) => setDraft({ ...draft, title: v }))}
          <div className="grid sm:grid-cols-2 gap-3">
            {editField("Thème", draft.theme, (v) => setDraft({ ...draft, theme: v }))}
            {editField("Exigence ciblée", draft.target_requirement, (v) => setDraft({ ...draft, target_requirement: v }))}
          </div>
          {editField("S — Situation & Contexte", draft.situation, (v) => setDraft({ ...draft, situation: v }), true)}
          {editField("T — Mission & Rôle", draft.task, (v) => setDraft({ ...draft, task: v }), true)}
          {editField("A — Actions & Choix Techniques", draft.action, (v) => setDraft({ ...draft, action: v }), true)}
          {editField("R — Résultats & Métriques", draft.result, (v) => setDraft({ ...draft, result: v }), true)}
          {editField("+R — Réflexion & Apprentissages", draft.reflection, (v) => setDraft({ ...draft, reflection: v }), true)}
          {editField("Mots-clés (séparés par des virgules)", tagsInput, setTagsInput)}

          {saveError && (
            <p className="text-xs text-red-400">{saveError}</p>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              disabled={saving}
              onClick={() => {
                setIsEditing(false);
                setSaveError(null);
              }}
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors disabled:opacity-50"
            >
              Annuler
            </button>
            <button
              type="button"
              disabled={saving}
              onClick={handleSave}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white transition-colors disabled:opacity-50"
            >
              {saving ? "Enregistrement..." : "Enregistrer"}
            </button>
          </div>
        </div>
      )}

      {/* STAR+R Body */}
      {isOpen && !isEditing && (
        <div className="p-4 sm:p-5 space-y-3.5 border-t border-slate-800/80 bg-slate-900/40 text-sm text-slate-300">
          {/* Situation */}
          <div className="flex gap-3 items-start">
            <span className="px-2 py-0.5 rounded text-xs font-bold bg-sky-500/10 text-sky-400 border border-sky-500/20 shrink-0">
              S
            </span>
            <div className="flex-1">
              <strong className="text-xs uppercase text-slate-400 tracking-wider block mb-0.5">
                Situation & Contexte
              </strong>
              <p className="leading-relaxed text-slate-200">{story.situation}</p>
            </div>
          </div>

          {/* Task */}
          <div className="flex gap-3 items-start">
            <span className="px-2 py-0.5 rounded text-xs font-bold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 shrink-0">
              T
            </span>
            <div className="flex-1">
              <strong className="text-xs uppercase text-slate-400 tracking-wider block mb-0.5">
                Mission & Rôle
              </strong>
              <p className="leading-relaxed text-slate-200">{story.task}</p>
            </div>
          </div>

          {/* Action */}
          <div className="flex gap-3 items-start">
            <span className="px-2 py-0.5 rounded text-xs font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20 shrink-0">
              A
            </span>
            <div className="flex-1">
              <strong className="text-xs uppercase text-slate-400 tracking-wider block mb-0.5">
                Actions & Choix Techniques
              </strong>
              <p className="leading-relaxed text-slate-200">{story.action}</p>
            </div>
          </div>

          {/* Result */}
          <div className="flex gap-3 items-start">
            <span className="px-2 py-0.5 rounded text-xs font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shrink-0">
              R
            </span>
            <div className="flex-1">
              <strong className="text-xs uppercase text-slate-400 tracking-wider block mb-0.5">
                Résultats & Métriques
              </strong>
              <p className="leading-relaxed text-emerald-200/90 font-medium">
                {story.result}
              </p>
            </div>
          </div>

          {/* Reflection */}
          <div className="flex gap-3 items-start pt-2 border-t border-slate-800/60">
            <span className="px-1.5 py-0.5 rounded text-xs font-bold bg-purple-500/10 text-purple-400 border border-purple-500/20 shrink-0">
              +R
            </span>
            <div className="flex-1">
              <strong className="text-xs uppercase text-slate-400 tracking-wider block mb-0.5">
                Réflexion & Apprentissages
              </strong>
              <p className="leading-relaxed text-purple-200/90 italic">
                {story.reflection}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
