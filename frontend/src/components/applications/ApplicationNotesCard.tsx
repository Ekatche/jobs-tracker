"use client";

import React from "react";
import { FiEdit2, FiPlus, FiTrash2 } from "react-icons/fi";

interface ApplicationNotesCardProps {
  localNotes: string[];
  newNote: string;
  onNewNoteChange: (value: string) => void;
  isAddingLocalNote: boolean;
  onSetAddingLocalNote: (adding: boolean) => void;
  editingNoteIndex: number | null;
  editedNoteText: string;
  onEditedNoteTextChange: (value: string) => void;
  onCancelEditNote: () => void;
  onAddLocalNote: () => void;
  onEditLocalNote: (index: number, noteText: string) => void;
  onSaveEditNote: () => void;
  onDeleteLocalNote: (index: number) => void;
}

/**
 * Inline CRUD list for tracking notes on an application.
 */
export function ApplicationNotesCard({
  localNotes,
  newNote,
  onNewNoteChange,
  isAddingLocalNote,
  onSetAddingLocalNote,
  editingNoteIndex,
  editedNoteText,
  onEditedNoteTextChange,
  onCancelEditNote,
  onAddLocalNote,
  onEditLocalNote,
  onSaveEditNote,
  onDeleteLocalNote,
}: ApplicationNotesCardProps) {
  return (
    <div className="pt-2 border-t border-slate-800/80">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
          <FiEdit2 className="w-3.5 h-3.5 text-indigo-400" />
          <span>Notes & Suivi ({localNotes.length})</span>
        </h3>

        {!isAddingLocalNote && (
          <button
            type="button"
            onClick={() => onSetAddingLocalNote(true)}
            className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1 px-2.5 py-1 rounded bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/30 font-medium transition-colors"
          >
            <FiPlus className="w-3.5 h-3.5" />
            <span>Ajouter une note</span>
          </button>
        )}
      </div>

      {isAddingLocalNote && (
        <div className="mb-4 p-3.5 bg-slate-800/80 border border-indigo-500/30 rounded-xl animate-in fade-in">
          <textarea
            value={newNote}
            onChange={(e) => onNewNoteChange(e.target.value)}
            placeholder="Écrivez votre note (contact RH, date d'échange, question technique...)..."
            className="w-full px-3 py-2 rounded-lg bg-slate-900/90 border border-slate-700 focus:border-indigo-500 text-white text-xs focus:outline-none leading-relaxed"
            rows={3}
            autoFocus
          />
          <div className="flex justify-end gap-2 mt-2">
            <button
              type="button"
              onClick={() => {
                onSetAddingLocalNote(false);
                onNewNoteChange("");
              }}
              className="px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-300 text-xs font-medium transition-colors"
            >
              Annuler
            </button>
            <button
              type="button"
              onClick={onAddLocalNote}
              disabled={!newNote.trim()}
              className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition-colors disabled:opacity-50"
            >
              Enregistrer la note
            </button>
          </div>
        </div>
      )}

      {localNotes.length === 0 && !isAddingLocalNote ? (
        <p className="text-xs text-slate-500 italic py-2">
          Aucune note enregistrée pour cette candidature.
        </p>
      ) : (
        <div className="space-y-2.5">
          {localNotes.map((note, index) => (
            <div
              key={index}
              className="p-3.5 bg-slate-800/60 hover:bg-slate-800/90 border border-slate-700/60 rounded-xl relative group transition-all"
            >
              {editingNoteIndex === index ? (
                <div>
                  <textarea
                    value={editedNoteText}
                    onChange={(e) => onEditedNoteTextChange(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-600 focus:border-blue-500 text-white text-xs focus:outline-none leading-relaxed"
                    rows={3}
                    autoFocus
                  />
                  <div className="flex justify-end mt-2 space-x-2">
                    <button
                      type="button"
                      onClick={onCancelEditNote}
                      className="px-2.5 py-1 bg-slate-700 hover:bg-slate-600 rounded-md text-xs text-slate-300 transition-colors"
                    >
                      Annuler
                    </button>
                    <button
                      type="button"
                      onClick={onSaveEditNote}
                      disabled={!editedNoteText.trim()}
                      className="px-3 py-1 bg-blue-600 hover:bg-blue-500 rounded-md text-xs font-semibold text-white transition-colors disabled:opacity-50"
                    >
                      Enregistrer
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <p className="text-xs text-slate-200 leading-relaxed pr-14 whitespace-pre-wrap">
                    {note}
                  </p>
                  <div className="absolute top-2.5 right-2.5 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => onEditLocalNote(index, note)}
                      className="p-1 rounded-md text-slate-400 hover:text-blue-300 hover:bg-blue-900/40 transition-colors"
                      title="Modifier"
                    >
                      <FiEdit2 className="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => onDeleteLocalNote(index)}
                      className="p-1 rounded-md text-slate-400 hover:text-rose-400 hover:bg-rose-900/40 transition-colors"
                      title="Supprimer"
                    >
                      <FiTrash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
