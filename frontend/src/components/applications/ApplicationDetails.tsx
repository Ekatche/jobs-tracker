import React from "react";
import { Application, calculateDays } from "@/types/application";
import { useApplicationDrawer } from "@/hooks/useApplicationDrawer";
import { ApplicationEvalCard } from "./ApplicationEvalCard";
import { ApplicationDrawerBody } from "./ApplicationDrawerBody";
import {
  FiLink,
  FiX,
  FiMapPin,
  FiCalendar,
  FiClock,
  FiArchive,
  FiTrash2,
  FiSave,
  FiFileText,
} from "react-icons/fi";

interface ApplicationDetailsProps {
  application: Application | null;
  originalApplication: Application | null;
  onClose: () => void;
  onChange: (field: string, value: string) => void;
  onSave: () => Promise<void>;
  onCancel: () => void;
  onDelete: () => Promise<void>;
  onArchive: () => Promise<void>;
  onAddNote: (note: string) => Promise<void>;
  onEditNote: (index: number, text: string) => Promise<void>;
  onDeleteNote: (index: number) => Promise<void>;
  hasUnsavedChanges: boolean;
  isAddingNote: boolean;
  isDeletingNote: boolean;
  deletingNoteIndex: number | null;
}

export default function ApplicationDetails({
  application,
  onClose,
  onChange,
  onSave,
  onCancel,
  onDelete,
  onArchive,
  hasUnsavedChanges,
}: ApplicationDetailsProps) {
  const drawer = useApplicationDrawer(application, onChange, onClose);

  if (!application) return null;

  const days = application.days_since_application ?? calculateDays(application.application_date);
  const isRelanceDue =
    application.follow_up_alert === "relance_due" ||
    (application.status === "Candidature envoyée" && days >= 7);
  const isRemerciementDue =
    application.follow_up_alert === "remerciement_due" ||
    (application.status === "Entretien" && days >= 1);

  return (
    <div className="fixed inset-0 z-50 pointer-events-none">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-slate-950/70 backdrop-blur-sm pointer-events-auto transition-opacity"
        onClick={onClose}
      />

      {/* Slide-over Drawer */}
      <div className="absolute right-0 top-0 bottom-0 w-full max-w-xl bg-slate-900/95 backdrop-blur-2xl border-l border-slate-700/60 shadow-2xl flex flex-col pointer-events-auto overflow-hidden animate-in slide-in-from-right duration-200">
        {/* Drawer Header */}
        <div className="px-6 pt-5 pb-4 border-b border-slate-800/80 bg-slate-900/60 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
            <FiFileText className="w-4 h-4 text-blue-400" />
            <span>Fiche Candidature</span>
          </div>

          <div className="flex items-center gap-2">
            {isRelanceDue && (
              <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30 flex items-center gap-1.5 animate-pulse">
                <FiClock className="w-3.5 h-3.5" />
                Relance due ({days}j)
              </span>
            )}
            {isRemerciementDue && (
              <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 flex items-center gap-1.5">
                <FiClock className="w-3.5 h-3.5" />
                Remerciement J+1
              </span>
            )}

            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
              title="Fermer (Échap)"
            >
              <FiX className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Hero Position & Company Section */}
        <div className="px-6 py-5 border-b border-slate-800/60 bg-gradient-to-b from-slate-900/80 to-slate-900/30 shrink-0">
          <div className="flex items-start gap-4">
            <div className="w-13 h-13 min-w-[52px] min-h-[52px] rounded-2xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-purple-600 flex items-center justify-center text-white text-xl font-extrabold shadow-lg shadow-blue-500/20 border border-white/10 shrink-0">
              {application.company ? application.company.charAt(0).toUpperCase() : "?"}
            </div>

            <div className="flex-1 min-w-0">
              <input
                type="text"
                value={application.position}
                onChange={(e) => onChange("position", e.target.value)}
                placeholder="Intitulé du poste"
                className="w-full text-lg md:text-xl font-bold text-white bg-transparent border-b border-transparent hover:border-slate-600 focus:border-blue-500 focus:bg-slate-800/50 px-1 py-0.5 rounded transition-all focus:outline-none"
              />
              <input
                type="text"
                value={application.company}
                onChange={(e) => onChange("company", e.target.value)}
                placeholder="Entreprise"
                className="w-full text-sm font-medium text-slate-400 bg-transparent border-b border-transparent hover:border-slate-600 focus:border-blue-500 focus:bg-slate-800/50 px-1 py-0.5 rounded transition-all focus:outline-none mt-0.5"
              />
            </div>
          </div>

          {/* Quick Meta Chips */}
          <div className="flex flex-wrap items-center gap-2.5 mt-4 text-xs">
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-800/70 border border-slate-700/60 text-slate-300">
              <FiMapPin className="w-3.5 h-3.5 text-blue-400 shrink-0" />
              <input
                type="text"
                value={application.location || ""}
                onChange={(e) => onChange("location", e.target.value)}
                placeholder="Ville / Télétravail"
                className="bg-transparent text-slate-300 focus:text-white focus:outline-none w-32 placeholder:text-slate-500"
              />
            </div>

            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-800/70 border border-slate-700/60 text-slate-300">
              <FiCalendar className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
              <span>
                {days} {days > 1 ? "jours" : "jour"}
              </span>
            </div>

            {!application.offer_id && !drawer.evaluation?.offer_id && application.url && (
              <button
                type="button"
                onClick={drawer.handleLinkOffer}
                disabled={drawer.isLinkingOffer}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-800/70 hover:bg-slate-700/70 border border-slate-700/60 text-slate-300 transition-colors font-medium disabled:opacity-60"
                title="Créer/retrouver la fiche de l'offre sans lancer le scoring IA"
              >
                <FiLink className={`w-3.5 h-3.5 ${drawer.isLinkingOffer ? "animate-pulse" : ""}`} />
                <span>{drawer.isLinkingOffer ? "Liaison..." : "Voir l'offre"}</span>
              </button>
            )}

            {application.offer_id || drawer.evaluation?.offer_id ? (
              <>
                {!drawer.evaluation?.offer_id && (
                  <button
                    type="button"
                    onClick={() => drawer.handleOpenOffer()}
                    disabled={drawer.isLinkingOffer}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/30 text-blue-300 transition-colors font-medium disabled:opacity-60"
                  >
                    <FiLink className="w-3.5 h-3.5" />
                    <span>Offre scrapée</span>
                  </button>
                )}
                <button
                  type="button"
                  onClick={drawer.handleOpenTailoredResumeWithAutoLink}
                  disabled={drawer.isLinkingOffer}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/30 text-indigo-300 transition-colors font-medium disabled:opacity-60"
                  title="Générer un CV adapté sur-mesure pour cette offre (ouvre un nouvel onglet)"
                >
                  <FiFileText className="w-3.5 h-3.5" />
                  <span>CV Adapté</span>
                </button>
              </>
            ) : application.description && application.description.trim().length > 20 ? (
              <button
                type="button"
                onClick={drawer.handleOpenTailoredResumeWithAutoLink}
                disabled={drawer.isLinkingOffer}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/30 text-indigo-300 transition-colors font-medium disabled:opacity-60"
                title="Lier l'offre et générer un CV adapté sur-mesure"
              >
                <FiFileText className="w-3.5 h-3.5" />
                <span>{drawer.isLinkingOffer ? "Liaison..." : "CV Adapté"}</span>
              </button>
            ) : (
              <span
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-800/40 border border-slate-700/40 text-slate-500 cursor-not-allowed font-medium text-xs"
                title="Renseignez ou collez la description du poste ci-dessous pour pouvoir générer un CV adapté"
              >
                <FiFileText className="w-3.5 h-3.5 opacity-50" />
                <span>CV Adapté (Description requise)</span>
              </span>
            )}
          </div>
        </div>

        {/* Scrollable Content Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">
          <ApplicationEvalCard
            evaluation={drawer.evaluation}
            loadingEvaluation={drawer.loadingEvaluation}
            isScoring={drawer.isScoring}
            scoringError={drawer.scoringError}
            scoreSuccessMessage={drawer.scoreSuccessMessage}
            isLinkingOffer={drawer.isLinkingOffer}
            onScoreApplication={drawer.handleScoreApplication}
            onOpenOffer={drawer.handleOpenOffer}
          />

          <ApplicationDrawerBody
            application={application}
            days={days}
            onChange={onChange}
            localNotes={drawer.localNotes}
            newNote={drawer.newNote}
            onNewNoteChange={drawer.setNewNote}
            isAddingLocalNote={drawer.isAddingLocalNote}
            onSetAddingLocalNote={drawer.setIsAddingLocalNote}
            editingNoteIndex={drawer.editingNoteIndex}
            editedNoteText={drawer.editedNoteText}
            onEditedNoteTextChange={drawer.setEditedNoteText}
            onCancelEditNote={() => {
              drawer.setEditingNoteIndex(null);
              drawer.setEditedNoteText("");
            }}
            onAddLocalNote={drawer.handleAddLocalNote}
            onEditLocalNote={drawer.handleEditLocalNote}
            onSaveEditNote={drawer.handleSaveEditNote}
            onDeleteLocalNote={drawer.handleDeleteLocalNote}
            isRegeneratingDesc={drawer.isRegeneratingDesc}
            descError={drawer.descError}
            onRegenerateDescription={drawer.handleRegenerateDescription}
          />
        </div>

        {/* Sticky Action Footer */}
        <div className="border-t border-slate-800/90 bg-slate-900/95 backdrop-blur-xl px-6 py-4 flex items-center justify-between gap-3 shrink-0">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onArchive}
              className="px-3 py-2 rounded-xl bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-medium border border-slate-700 transition-colors flex items-center gap-1.5"
              title={application.archived ? "Désarchiver" : "Archiver"}
            >
              <FiArchive className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">
                {application.archived ? "Désarchiver" : "Archiver"}
              </span>
            </button>

            <button
              type="button"
              onClick={onDelete}
              className="px-3 py-2 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 hover:text-rose-300 text-xs font-medium border border-rose-500/20 transition-colors flex items-center gap-1.5"
              title="Supprimer la candidature"
            >
              <FiTrash2 className="w-3.5 h-3.5" />
              <span>Supprimer</span>
            </button>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={onCancel}
              disabled={!hasUnsavedChanges}
              className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Annuler
            </button>

            <button
              type="button"
              onClick={onSave}
              disabled={!hasUnsavedChanges}
              className={`px-5 py-2 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-all ${
                hasUnsavedChanges
                  ? "bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white shadow-lg shadow-blue-500/25"
                  : "bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700/50"
              }`}
            >
              <FiSave className="w-3.5 h-3.5" />
              <span>Enregistrer</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
