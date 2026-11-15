"use client";

import React from "react";
import { Application, formatDate } from "@/types/application";
import StatusSelect from "./StatusSelect";
import CoverLetterPanel from "./CoverLetterPanel";
import { ApplicationNotesCard } from "./ApplicationNotesCard";
import {
  FiExternalLink,
  FiRefreshCw,
  FiClock,
  FiAlertTriangle,
  FiFileText,
} from "react-icons/fi";

interface ApplicationDrawerBodyProps {
  application: Application;
  days: number;
  onChange: (field: string, value: string) => void;
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
  isRegeneratingDesc: boolean;
  descError: string | null;
  onRegenerateDescription: () => void;
}

/**
 * Renders status, application date, URL, offer description, inline notes CRUD, cover letter, and metrics.
 */
export function ApplicationDrawerBody(props: ApplicationDrawerBodyProps) {
  const {
    application,
    days,
    onChange,
    isRegeneratingDesc,
    descError,
    onRegenerateDescription,
  } = props;

  return (
    <>
      {/* Status & Date grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
            Étape dans le pipeline
          </label>
          <StatusSelect
            currentStatus={application.status}
            onChange={(newStatus) => onChange("status", newStatus)}
          />
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
            Date de candidature
          </label>
          <div className="relative">
            <input
              type="date"
              value={application.application_date ? application.application_date.substring(0, 10) : ""}
              onChange={(e) => onChange("application_date", e.target.value)}
              className="w-full px-3.5 py-2 rounded-lg bg-slate-800/80 border border-slate-700 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 text-white text-sm focus:outline-none shadow-sm transition-all"
            />
          </div>
        </div>
      </div>

      {/* Offer URL field */}
      <div>
        <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
          Lien vers l&apos;annonce
        </label>
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={application.url || ""}
            onChange={(e) => onChange("url", e.target.value)}
            placeholder="https://..."
            className="flex-1 px-3 py-2 rounded-lg bg-slate-800/60 border border-slate-700 focus:border-blue-500 text-white text-xs focus:outline-none transition-all"
          />
          {application.url && (
            <a
              href={application.url}
              target="_blank"
              rel="noopener noreferrer"
              className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 transition-colors shrink-0"
              title="Ouvrir le lien"
            >
              <FiExternalLink className="w-4 h-4" />
            </a>
          )}
        </div>
      </div>

      {/* Job description */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
            <FiFileText className="w-3.5 h-3.5 text-blue-400" />
            <span>Description de l&apos;offre</span>
          </label>

          {application.url && (
            <button
              type="button"
              onClick={onRegenerateDescription}
              disabled={isRegeneratingDesc}
              className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1.5 px-2.5 py-1 rounded bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/30 transition-colors disabled:opacity-50 font-medium"
              title="Régénérer le résumé de l'offre depuis son URL"
            >
              <FiRefreshCw className={`w-3 h-3 ${isRegeneratingDesc ? "animate-spin" : ""}`} />
              <span>{isRegeneratingDesc ? "Régénération..." : "Régénérer par IA"}</span>
            </button>
          )}
        </div>

        {descError && (
          <div className="mb-2 p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-200 text-xs flex items-start gap-2">
            <FiAlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <div className="flex-1">
              <span>{descError}</span>
              <p className="mt-1 text-slate-400 text-[11px]">
                💡 <strong>Contournement :</strong> Vous pouvez coller le texte de l&apos;annonce directement ci-dessous pour débloquer automatiquement le bouton <strong>CV Adapté</strong>.
              </p>
            </div>
          </div>
        )}

        <textarea
          value={application.description || ""}
          onChange={(e) => onChange("description", e.target.value)}
          placeholder="Description détaillée ou résumé des missions et exigences..."
          className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 text-slate-200 text-sm focus:outline-none transition-all leading-relaxed"
          rows={4}
        />
      </div>

      <ApplicationNotesCard
        localNotes={props.localNotes}
        newNote={props.newNote}
        onNewNoteChange={props.onNewNoteChange}
        isAddingLocalNote={props.isAddingLocalNote}
        onSetAddingLocalNote={props.onSetAddingLocalNote}
        editingNoteIndex={props.editingNoteIndex}
        editedNoteText={props.editedNoteText}
        onEditedNoteTextChange={props.onEditedNoteTextChange}
        onCancelEditNote={props.onCancelEditNote}
        onAddLocalNote={props.onAddLocalNote}
        onEditLocalNote={props.onEditLocalNote}
        onSaveEditNote={props.onSaveEditNote}
        onDeleteLocalNote={props.onDeleteLocalNote}
      />

      {/* Cover letter panel */}
      <div className="pt-2 border-t border-slate-800/80">
        <CoverLetterPanel
          applicationId={application._id}
          isEtudeStatus={application.status === "En étude"}
        />
      </div>

      {/* Metrics & history */}
      <div className="pt-4 border-t border-slate-800/80 pb-2">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
          <FiClock className="w-3.5 h-3.5 text-slate-400" />
          <span>Historique & Métriques</span>
        </h3>

        <div className="grid grid-cols-2 gap-3 text-xs">
          <div className="p-3 rounded-xl bg-slate-800/40 border border-slate-700/50">
            <span className="text-slate-400 block text-[11px]">Jours écoulés</span>
            <span className="text-sm font-bold text-white mt-0.5 block">{days} jours</span>
          </div>
          <div className="p-3 rounded-xl bg-slate-800/40 border border-slate-700/50">
            <span className="text-slate-400 block text-[11px]">Dernière modification</span>
            <span className="text-sm font-bold text-white mt-0.5 block truncate">
              {formatDate(application.updated_at)}
            </span>
          </div>
        </div>
      </div>
    </>
  );
}
