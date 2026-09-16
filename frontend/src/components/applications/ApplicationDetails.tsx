import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Application, formatDate, calculateDays } from "@/types/application";
import { applicationApi, type OfferEvaluation } from "@/lib/api";
import StatusSelect from "./StatusSelect";
import CoverLetterPanel from "./CoverLetterPanel";
import {
  FiExternalLink,
  FiRefreshCw,
  FiLink,
  FiX,
  FiMapPin,
  FiCalendar,
  FiClock,
  FiZap,
  FiCheckCircle,
  FiAlertTriangle,
  FiArchive,
  FiTrash2,
  FiPlus,
  FiEdit2,
  FiSave,
  FiArrowRight,
  FiShield,
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
  originalApplication,
  onClose,
  onChange,
  onSave,
  onCancel,
  onDelete,
  onArchive,
  hasUnsavedChanges,
}: ApplicationDetailsProps) {
  // Local notes state
  const [localNotes, setLocalNotes] = useState<string[]>([]);
  const [newNote, setNewNote] = useState<string>("");
  const [isAddingLocalNote, setIsAddingLocalNote] = useState<boolean>(false);
  const [editingNoteIndex, setEditingNoteIndex] = useState<number | null>(null);
  const [editedNoteText, setEditedNoteText] = useState<string>("");
  const [isRegeneratingDesc, setIsRegeneratingDesc] = useState<boolean>(false);

  // AI Evaluation state
  const [evaluation, setEvaluation] = useState<OfferEvaluation | null>(null);
  const [loadingEvaluation, setLoadingEvaluation] = useState<boolean>(false);
  const [isScoring, setIsScoring] = useState<boolean>(false);
  const [scoringError, setScoringError] = useState<string | null>(null);
  const [scoreSuccessMessage, setScoreSuccessMessage] = useState<string | null>(null);

  // Load existing evaluation for this application
  const fetchEvaluation = useCallback(async (appId: string) => {
    setLoadingEvaluation(true);
    setScoringError(null);
    try {
      const evalData = await applicationApi.getEvaluation(appId);
      setEvaluation(evalData);
    } catch (err) {
      console.warn("Could not fetch evaluation for application:", err);
      setEvaluation(null);
    } finally {
      setLoadingEvaluation(false);
    }
  }, []);

  // Sync notes and fetch evaluation whenever application changes
  useEffect(() => {
    if (application?.notes) {
      setLocalNotes([...application.notes]);
    } else {
      setLocalNotes([]);
    }

    if (application?._id) {
      fetchEvaluation(application._id);
    } else {
      setEvaluation(null);
    }
    setScoringError(null);
    setScoreSuccessMessage(null);
  }, [application, fetchEvaluation]);

  // Handle Escape key to close drawer
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  if (!application) return null;

  const handleStatusChange = (newStatus: string) => {
    onChange("status", newStatus);
  };

  // Local notes handlers
  const handleAddLocalNote = () => {
    if (!newNote.trim()) return;
    const updatedNotes = [...localNotes, newNote.trim()];
    setLocalNotes(updatedNotes);
    setNewNote("");
    setIsAddingLocalNote(false);
    onChange("notes", JSON.stringify(updatedNotes));
  };

  const handleEditLocalNote = (index: number, noteText: string) => {
    setEditingNoteIndex(index);
    setEditedNoteText(noteText);
  };

  const handleSaveEditNote = () => {
    if (editingNoteIndex === null || !editedNoteText.trim()) return;
    const updatedNotes = [...localNotes];
    updatedNotes[editingNoteIndex] = editedNoteText.trim();
    setLocalNotes(updatedNotes);
    setEditingNoteIndex(null);
    setEditedNoteText("");
    onChange("notes", JSON.stringify(updatedNotes));
  };

  const handleDeleteLocalNote = (index: number) => {
    const updatedNotes = [...localNotes];
    updatedNotes.splice(index, 1);
    setLocalNotes(updatedNotes);
    onChange("notes", JSON.stringify(updatedNotes));
  };

  // AI Description regeneration handler
  const handleRegenerateDescription = async () => {
    if (!application?._id || !application.url) return;
    try {
      setIsRegeneratingDesc(true);
      const updated = await applicationApi.regenerateDescription(application._id);
      if (updated?.description) {
        onChange("description", updated.description);
      }
    } catch (err) {
      console.error("Erreur régénération description:", err);
    } finally {
      setIsRegeneratingDesc(false);
    }
  };

  // Trigger Two-Pass AI Evaluation
  const handleScoreApplication = async () => {
    if (!application?._id || isScoring) return;
    setIsScoring(true);
    setScoringError(null);
    setScoreSuccessMessage(null);

    try {
      const result = await applicationApi.evaluate(application._id);
      setEvaluation(result);
      setScoreSuccessMessage("Scoring IA Two-Pass terminé avec succès !");

      // If application didn't have an offer_id linked, link it now
      if (result.offer_id && !application.offer_id) {
        onChange("offer_id", result.offer_id);
      }
      setTimeout(() => setScoreSuccessMessage(null), 4000);
    } catch (err: unknown) {
      console.error("Erreur lors du scoring de la candidature:", err);
      let errorMsg = "Impossible de générer le scoring IA pour cette offre.";
      if (err && typeof err === "object" && "response" in err) {
        const responseData = (err as { response?: { data?: { detail?: string } } }).response?.data;
        if (responseData?.detail) {
          errorMsg = responseData.detail;
        }
      } else if (err instanceof Error) {
        errorMsg = err.message;
      }
      setScoringError(errorMsg);
    } finally {
      setIsScoring(false);
    }
  };

  const days = application.days_since_application ?? calculateDays(application.application_date);
  const isRelanceDue =
    application.follow_up_alert === "relance_due" ||
    (application.status === "Candidature envoyée" && days >= 7);
  const isRemerciementDue =
    application.follow_up_alert === "remerciement_due" ||
    (application.status === "Entretien" && days >= 1);

  // Score color helper
  const getScoreBadgeStyles = (s: number) => {
    if (s >= 4.0) {
      return {
        bg: "bg-emerald-500/10 border-emerald-500/30 text-emerald-300",
        pill: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
        label: "Excellent match",
      };
    }
    if (s >= 3.0) {
      return {
        bg: "bg-amber-500/10 border-amber-500/30 text-amber-300",
        pill: "bg-amber-500/20 text-amber-300 border-amber-500/40",
        label: "Match partiel",
      };
    }
    return {
      bg: "bg-rose-500/10 border-rose-500/30 text-rose-300",
      pill: "bg-rose-500/20 text-rose-300 border-rose-500/40",
      label: "Écart significatif",
    };
  };

  return (
    <div className="fixed inset-0 z-50 pointer-events-none">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-slate-950/70 backdrop-blur-sm pointer-events-auto transition-opacity"
        onClick={onClose}
      />

      {/* Slide-over Modern Drawer */}
      <div
        className="absolute right-0 top-0 bottom-0 w-full max-w-xl bg-slate-900/95 backdrop-blur-2xl border-l border-slate-700/60 shadow-2xl flex flex-col pointer-events-auto overflow-hidden animate-in slide-in-from-right duration-200"
      >
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
              <span>{days} {days > 1 ? "jours" : "jour"}</span>
            </div>

            {application.url && (
              <a
                href={application.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/30 text-blue-300 transition-colors font-medium"
              >
                <FiExternalLink className="w-3.5 h-3.5" />
                <span>Voir annonce</span>
              </a>
            )}

            {(application.offer_id || evaluation?.offer_id) && (
              <Link
                href={`/offers/${application.offer_id || evaluation?.offer_id}`}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/30 text-indigo-300 transition-colors font-medium"
              >
                <FiLink className="w-3.5 h-3.5" />
                <span>Offre scrapée</span>
              </Link>
            )}
          </div>
        </div>

        {/* Scrollable Content Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">

          {/* AI SCORING TWO-PASS CARD */}
          <div className="rounded-2xl border border-slate-700/70 bg-slate-800/40 p-5 shadow-lg relative overflow-hidden backdrop-blur-sm">
            <div className="absolute top-0 right-0 w-36 h-36 bg-blue-500/5 rounded-full blur-2xl pointer-events-none" />

            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2 text-sm font-bold text-white">
                <span className="p-1.5 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20">
                  <FiZap className="w-4 h-4" />
                </span>
                <span>Scoring IA Two-Pass (Gemini 3.7 Flash)</span>
              </div>

              {evaluation && (
                <button
                  type="button"
                  onClick={handleScoreApplication}
                  disabled={isScoring}
                  className="inline-flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 px-2 py-1 rounded bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/30 transition-all font-medium disabled:opacity-50"
                  title="Recalculer le scoring d'adéquation"
                >
                  <FiRefreshCw className={`w-3 h-3 ${isScoring ? "animate-spin" : ""}`} />
                  <span>{isScoring ? "Calcul..." : "Ré-évaluer"}</span>
                </button>
              )}
            </div>

            {/* Error banner */}
            {scoringError && (
              <div className="mb-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start gap-2">
                <FiAlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="font-semibold">Échec du scoring IA</p>
                  <p className="mt-0.5">{scoringError}</p>
                </div>
              </div>
            )}

            {/* Success message */}
            {scoreSuccessMessage && (
              <div className="mb-4 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-center gap-2">
                <FiCheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>{scoreSuccessMessage}</span>
              </div>
            )}

            {loadingEvaluation ? (
              <div className="py-6 flex flex-col items-center justify-center gap-2 text-slate-400 text-xs">
                <FiRefreshCw className="w-5 h-5 animate-spin text-blue-400" />
                <span>Chargement de l'évaluation IA...</span>
              </div>
            ) : evaluation ? (
              // SCORED VIEW
              <div>
                <div className="flex items-center gap-4 bg-slate-900/60 rounded-xl p-4 border border-slate-700/50">
                  {/* Gauge */}
                  <div
                    className={`flex flex-col items-center justify-center p-3 rounded-xl border ${
                      getScoreBadgeStyles(evaluation.score).bg
                    } min-w-[90px] text-center shadow-inner`}
                  >
                    <div className="flex items-baseline gap-0.5">
                      <span className="text-3xl font-extrabold tracking-tight">
                        {evaluation.score.toFixed(1)}
                      </span>
                      <span className="text-[11px] text-slate-400 font-medium">/ 5.0</span>
                    </div>
                    <span className="text-[10px] font-semibold mt-0.5">
                      {getScoreBadgeStyles(evaluation.score).label}
                    </span>
                  </div>

                  {/* Headline & Archetype */}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-white leading-snug line-clamp-2">
                      {evaluation.headline || "Évaluation de profil complétée"}
                    </p>
                    {evaluation.bloc_a?.archetype && (
                      <p className="text-xs text-slate-400 mt-1 line-clamp-1">
                        Archétype : <span className="text-indigo-300 font-medium">{evaluation.bloc_a.archetype}</span>
                      </p>
                    )}

                    {/* Quick matches / red flags pill row */}
                    <div className="flex flex-wrap items-center gap-2 mt-2">
                      {evaluation.bloc_b?.matched_requirements && (
                        <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 flex items-center gap-1">
                          <FiCheckCircle className="w-3 h-3 text-emerald-400" />
                          {evaluation.bloc_b.matched_requirements.length} match
                        </span>
                      )}
                      {evaluation.bloc_b?.missing_requirements && evaluation.bloc_b.missing_requirements.length > 0 && (
                        <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-slate-700/40 text-slate-300 border border-slate-600/40">
                          {evaluation.bloc_b.missing_requirements.length} écarts
                        </span>
                      )}
                      {evaluation.bloc_a?.red_flags && evaluation.bloc_a.red_flags.length > 0 && (
                        <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/30 flex items-center gap-1">
                          <FiAlertTriangle className="w-3 h-3 text-rose-400" />
                          {evaluation.bloc_a.red_flags.length} red flag
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Link to full report */}
                <div className="mt-3 flex items-center justify-end">
                  <Link
                    href={`/offers/${evaluation.offer_id || application.offer_id}`}
                    className="inline-flex items-center gap-1.5 text-xs font-semibold text-blue-400 hover:text-blue-300 transition-colors"
                  >
                    <span>Consulter l'analyse détaillée complète</span>
                    <FiArrowRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
              </div>
            ) : (
              // UNSCORED VIEW
              <div className="flex flex-col items-start gap-3 py-1">
                <p className="text-xs text-slate-300 leading-relaxed">
                  Mesurez instantanément la pertinence de votre candidature grâce à l'analyse en profondeur
                  Two-Pass (Blocs A, B et G) confrontant votre profil aux exigences réelles du poste.
                </p>

                <button
                  type="button"
                  onClick={handleScoreApplication}
                  disabled={isScoring}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white text-xs font-bold shadow-md shadow-blue-500/20 transition-all disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  <FiZap className={`w-4 h-4 ${isScoring ? "animate-spin" : ""}`} />
                  <span>{isScoring ? "Analyse Two-Pass en cours (Gemini 3.7)..." : "✨ Lancer le scoring IA"}</span>
                </button>
              </div>
            )}
          </div>

          {/* STATUS & DATE GRID */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                Étape dans le pipeline
              </label>
              <StatusSelect
                currentStatus={application.status}
                onChange={handleStatusChange}
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

          {/* URL FIELD IF NOT FILLED */}
          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
              Lien vers l'annonce
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

          {/* JOB DESCRIPTION */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <FiFileText className="w-3.5 h-3.5 text-blue-400" />
                <span>Description de l'offre</span>
              </label>

              {application.url && (
                <button
                  type="button"
                  onClick={handleRegenerateDescription}
                  disabled={isRegeneratingDesc}
                  className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1.5 px-2.5 py-1 rounded bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/30 transition-colors disabled:opacity-50 font-medium"
                  title="Régénérer le résumé de l'offre depuis son URL"
                >
                  <FiRefreshCw className={`w-3 h-3 ${isRegeneratingDesc ? "animate-spin" : ""}`} />
                  <span>{isRegeneratingDesc ? "Régénération..." : "Régénérer par IA"}</span>
                </button>
              )}
            </div>

            <textarea
              value={application.description || ""}
              onChange={(e) => onChange("description", e.target.value)}
              placeholder="Description détaillée ou résumé des missions et exigences..."
              className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 text-slate-200 text-sm focus:outline-none transition-all leading-relaxed"
              rows={4}
            />
          </div>

          {/* NOTES SECTION */}
          <div className="pt-2 border-t border-slate-800/80">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <FiEdit2 className="w-3.5 h-3.5 text-indigo-400" />
                <span>Notes & Suivi ({localNotes.length})</span>
              </h3>

              {!isAddingLocalNote && (
                <button
                  type="button"
                  onClick={() => setIsAddingLocalNote(true)}
                  className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1 px-2.5 py-1 rounded bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/30 font-medium transition-colors"
                >
                  <FiPlus className="w-3.5 h-3.5" />
                  <span>Ajouter une note</span>
                </button>
              )}
            </div>

            {/* Add note card */}
            {isAddingLocalNote && (
              <div className="mb-4 p-3.5 bg-slate-800/80 border border-indigo-500/30 rounded-xl animate-in fade-in">
                <textarea
                  value={newNote}
                  onChange={(e) => setNewNote(e.target.value)}
                  placeholder="Écrivez votre note (contact RH, date d'échange, question technique...)..."
                  className="w-full px-3 py-2 rounded-lg bg-slate-900/90 border border-slate-700 focus:border-indigo-500 text-white text-xs focus:outline-none leading-relaxed"
                  rows={3}
                  autoFocus
                />
                <div className="flex justify-end gap-2 mt-2">
                  <button
                    type="button"
                    onClick={() => {
                      setIsAddingLocalNote(false);
                      setNewNote("");
                    }}
                    className="px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-300 text-xs font-medium transition-colors"
                  >
                    Annuler
                  </button>
                  <button
                    type="button"
                    onClick={handleAddLocalNote}
                    disabled={!newNote.trim()}
                    className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition-colors disabled:opacity-50"
                  >
                    Enregistrer la note
                  </button>
                </div>
              </div>
            )}

            {/* Existing notes list */}
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
                          onChange={(e) => setEditedNoteText(e.target.value)}
                          className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-600 focus:border-blue-500 text-white text-xs focus:outline-none leading-relaxed"
                          rows={3}
                          autoFocus
                        />
                        <div className="flex justify-end mt-2 space-x-2">
                          <button
                            type="button"
                            onClick={() => {
                              setEditingNoteIndex(null);
                              setEditedNoteText("");
                            }}
                            className="px-2.5 py-1 bg-slate-700 hover:bg-slate-600 rounded-md text-xs text-slate-300 transition-colors"
                          >
                            Annuler
                          </button>
                          <button
                            type="button"
                            onClick={handleSaveEditNote}
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
                            onClick={() => handleEditLocalNote(index, note)}
                            className="p-1 rounded-md text-slate-400 hover:text-blue-300 hover:bg-blue-900/40 transition-colors"
                            title="Modifier"
                          >
                            <FiEdit2 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDeleteLocalNote(index)}
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

          {/* COVER LETTER PANEL */}
          <div className="pt-2 border-t border-slate-800/80">
            <CoverLetterPanel
              applicationId={application._id}
              isEtudeStatus={application.status === "En étude"}
            />
          </div>

          {/* METRICS & HISTORY */}
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
              <span className="hidden sm:inline">Supprimer</span>
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
