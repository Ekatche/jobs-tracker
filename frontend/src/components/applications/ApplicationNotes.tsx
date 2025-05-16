import React, { useState } from "react";
interface ApplicationNotesProps {
  notes: string[];
  onAddNote: (note: string) => Promise<void>;
  onEditNote: (index: number, text: string) => Promise<void>;
  onDeleteNote: (index: number) => Promise<void>;
  isAddingNote: boolean;
  isDeletingNote: boolean;
  deletingNoteIndex: number | null;
}

export default function ApplicationNotes({
  notes,
  onAddNote,
  onEditNote,
  onDeleteNote,
  isAddingNote,
  isDeletingNote,
  deletingNoteIndex,
}: ApplicationNotesProps) {
  const [newNote, setNewNote] = useState<string>("");
  const [isEditingNote, setIsEditingNote] = useState<boolean>(false);
  const [editingNoteIndex, setEditingNoteIndex] = useState<number | null>(null);
  const [editedNoteText, setEditedNoteText] = useState<string>("");

  const handleStartEditNote = (index: number, noteText: string) => {
    setEditingNoteIndex(index);
    setEditedNoteText(noteText);
    setIsEditingNote(true);
  };

  const handleSaveEditNote = async () => {
    if (editingNoteIndex === null || !editedNoteText.trim()) return;

    await onEditNote(editingNoteIndex, editedNoteText);
    setIsEditingNote(false);
    setEditingNoteIndex(null);
    setEditedNoteText("");
  };

  const handleCancelEditNote = () => {
    setIsEditingNote(false);
    setEditingNoteIndex(null);
    setEditedNoteText("");
  };

  const handleAddNoteSubmit = async () => {
    if (!newNote.trim()) return;

    await onAddNote(newNote);
    setNewNote("");
  };

  return (
    <div className="border-t border-gray-700 py-4">
      <h3 className="text-lg font-semibold mb-4">Notes</h3>
      {notes?.length ? (
        notes.map((note, index) => (
          <div
            key={index}
            className="mb-3 p-3 bg-blue-night-light rounded-md relative group"
          >
            {isEditingNote && editingNoteIndex === index ? (
              <div>
                <textarea
                  value={editedNoteText}
                  onChange={(e) => setEditedNoteText(e.target.value)}
                  className="w-full px-2 py-1 rounded-md bg-blue-night border border-gray-700 focus:border-blue-500 focus:outline-none text-white"
                  rows={3}
                />
                <div className="flex justify-end mt-2 space-x-2">
                  <button
                    onClick={handleCancelEditNote}
                    className="px-2 py-1 bg-gray-700 hover:bg-gray-600 rounded-md text-sm"
                  >
                    Annuler
                  </button>
                  <button
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
                <p className="text-gray-300 pr-8">{note}</p>
                <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity flex space-x-1">
                  <button
                    onClick={() => handleStartEditNote(index, note)}
                    className="p-1 rounded-full text-gray-400 hover:text-blue-400 hover:bg-blue-900/30"
                  >
                    <svg
                      className="h-4 w-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="2"
                        d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
                      ></path>
                    </svg>
                  </button>

                  <button
                    onClick={() => onDeleteNote(index)}
                    disabled={isDeletingNote && deletingNoteIndex === index}
                    className={`p-1 rounded-full ${
                      isDeletingNote && deletingNoteIndex === index
                        ? "text-gray-500"
                        : "text-gray-400 hover:text-red-400 hover:bg-red-900/30"
                    }`}
                  >
                    {isDeletingNote && deletingNoteIndex === index ? (
                      <svg
                        className="animate-spin h-4 w-4"
                        xmlns="http://www.w3.org/2000/svg"
                        fill="none"
                        viewBox="0 0 24 24"
                      >
                        <circle
                          className="opacity-25"
                          cx="12"
                          cy="12"
                          r="10"
                          stroke="currentColor"
                          strokeWidth="4"
                        ></circle>
                        <path
                          className="opacity-75"
                          fill="currentColor"
                          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                        ></path>
                      </svg>
                    ) : (
                      <svg
                        className="h-4 w-4"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                        xmlns="http://www.w3.org/2000/svg"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth="2"
                          d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                        ></path>
                      </svg>
                    )}
                  </button>
                </div>
              </>
            )}
          </div>
        ))
      ) : (
        <p className="text-gray-400 italic mb-4">
          Aucune note pour cette candidature
        </p>
      )}

      <div className="mt-3">
        <textarea
          value={newNote}
          onChange={(e) => setNewNote(e.target.value)}
          placeholder="Ajouter une nouvelle note..."
          className="w-full px-3 py-2 rounded-md bg-blue-night border border-gray-700 focus:border-blue-500 focus:outline-none text-white"
          rows={2}
        />
        <div className="flex justify-end mt-2">
          <button
            onClick={handleAddNoteSubmit}
            disabled={!newNote.trim() || isAddingNote}
            className={`px-3 py-1 rounded-md flex items-center text-white ${
              !newNote.trim() || isAddingNote
                ? "bg-gray-600 cursor-not-allowed"
                : "bg-blue-600 hover:bg-blue-500"
            }`}
          >
            {isAddingNote ? (
              <>
                <svg
                  className="animate-spin -ml-1 mr-2 h-4 w-4 text-white"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  ></circle>
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  ></path>
                </svg>
                Ajout...
              </>
            ) : (
              <>
                <svg
                  className="w-4 h-4 mr-1"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M12 6v6m0 0v6m0-6h6m-6 0H6"
                  ></path>
                </svg>
                Ajouter
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
