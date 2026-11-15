"use client";

import { useState } from "react";
import { FiEdit2, FiTrash2, FiPlus } from "react-icons/fi";

interface ApplicationNotesEditorProps {
  notes: string[];
  onChange: (notes: string[]) => void;
}

export default function ApplicationNotesEditor({
  notes,
  onChange,
}: ApplicationNotesEditorProps) {
  const [newNote, setNewNote] = useState("");
  const [editingNoteIndex, setEditingNoteIndex] = useState<number | null>(null);
  const [editedNoteText, setEditedNoteText] = useState("");

  const handleAddNote = () => {
    if (!newNote.trim()) return;
    onChange([...notes, newNote]);
    setNewNote("");
  };

  const handleDeleteNote = (index: number) => {
    const updatedNotes = [...notes];
    updatedNotes.splice(index, 1);
    onChange(updatedNotes);
  };

  const handleSaveEditNote = () => {
    if (editingNoteIndex === null || !editedNoteText.trim()) return;
    const updatedNotes = [...notes];
    updatedNotes[editingNoteIndex] = editedNoteText;
    onChange(updatedNotes);
    setEditingNoteIndex(null);
    setEditedNoteText("");
  };

  return (
    <div className="mt-4">
      <h3 className="text-lg font-semibold mb-2">Notes</h3>
      <div className="space-y-2 mb-4">
        {notes.map((note, index) => (
          <div key={index} className="p-3 bg-blue-night-light rounded-md relative group">
            {editingNoteIndex === index ? (
              <div>
                <textarea
                  value={editedNoteText}
                  onChange={(e) => setEditedNoteText(e.target.value)}
                  className="w-full px-2 py-1 rounded-md bg-blue-night border border-gray-700 focus:border-blue-500 focus:outline-none text-white"
                  rows={3}
                />
                <div className="flex justify-end mt-2 space-x-2">
                  <button
                    type="button"
                    onClick={() => {
                      setEditingNoteIndex(null);
                      setEditedNoteText("");
                    }}
                    className="px-2 py-1 bg-gray-700 hover:bg-gray-600 rounded-md text-sm"
                  >
                    Annuler
                  </button>
                  <button
                    type="button"
                    onClick={handleSaveEditNote}
                    disabled={!editedNoteText.trim()}
                    className={`px-2 py-1 rounded-md text-sm text-white ${
                      !editedNoteText.trim()
                        ? "bg-gray-600 cursor-not-allowed"
                        : "bg-blue-600 hover:bg-blue-500"
                    }`}
                  >
                    Enregistrer
                  </button>
                </div>
              </div>
            ) : (
              <>
                <p className="text-gray-300 pr-12">{note}</p>
                <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity flex space-x-1">
                  <button
                    type="button"
                    onClick={() => {
                      setEditingNoteIndex(index);
                      setEditedNoteText(note);
                    }}
                    className="p-1 rounded-full text-gray-400 hover:text-blue-400 hover:bg-blue-900/30"
                  >
                    <FiEdit2 className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDeleteNote(index)}
                    className="p-1 rounded-full text-gray-400 hover:text-red-400 hover:bg-red-900/30"
                  >
                    <FiTrash2 className="h-4 w-4" />
                  </button>
                </div>
              </>
            )}
          </div>
        ))}
      </div>

      <div>
        <textarea
          value={newNote}
          onChange={(e) => setNewNote(e.target.value)}
          placeholder="Ajouter une nouvelle note..."
          className="w-full px-3 py-2 rounded-md bg-blue-night border border-gray-700 focus:border-blue-500 focus:outline-none text-white"
          rows={2}
        />
        <div className="flex justify-end mt-2">
          <button
            type="button"
            onClick={handleAddNote}
            disabled={!newNote.trim()}
            className={`px-3 py-1 rounded-md flex items-center text-white ${
              !newNote.trim() ? "bg-gray-600 cursor-not-allowed" : "bg-blue-600 hover:bg-blue-500"
            }`}
          >
            <FiPlus className="w-4 h-4 mr-1" />
            Ajouter
          </button>
        </div>
      </div>
    </div>
  );
}
