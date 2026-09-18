"use client";

import { useState } from "react";
import { Task, TaskStatus } from "@/types/tasks";
import {
  FiX,
  FiPlus,
  FiCheck,
  FiCalendar,
  FiTag,
  FiAlertCircle,
  FiBriefcase,
} from "react-icons/fi";
import { taskApi } from "@/lib/api";

interface NewTaskModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: (task: Task) => void;
}

const CATEGORIES = [
  "Général",
  "Candidature",
  "Réseau",
  "Entretien",
  "Administratif",
  "Formation",
];

const PRIORITIES = [
  { value: "haute", label: "Haute priorité", color: "text-rose-400 border-rose-500/40 bg-rose-500/10" },
  { value: "normale", label: "Priorité normale", color: "text-blue-400 border-blue-500/40 bg-blue-500/10" },
  { value: "basse", label: "Basse priorité", color: "text-slate-400 border-slate-700 bg-slate-800/60" },
];

export default function NewTaskModal({
  isOpen,
  onClose,
  onSuccess,
}: NewTaskModalProps) {
  const [form, setForm] = useState({
    title: "",
    description: "",
    status: TaskStatus.TODO,
    priority: "normale",
    category: "Général",
    company: "",
    due_date: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);

  if (!isOpen) return null;

  const handleChange = (
    e: React.ChangeEvent<
      HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
    >,
  ) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!form.title.trim()) {
      setError("Le titre de la démarche est requis.");
      return;
    }
    setIsSubmitting(true);

    try {
      const payload: Omit<Task, "_id" | "user_id" | "created_at" | "updated_at"> = {
        title: form.title.trim(),
        description: form.description?.trim() || undefined,
        status: form.status,
        priority: form.priority,
        category: form.category,
        company: form.company?.trim() || undefined,
        due_date: form.due_date ? new Date(form.due_date).toISOString() : undefined,
      };

      const created = await taskApi.create(payload);
      if (onSuccess) {
        onSuccess(created);
      }
      setShowSuccess(true);
      setTimeout(() => {
        setShowSuccess(false);
        onClose();
        setForm({
          title: "",
          description: "",
          status: TaskStatus.TODO,
          priority: "normale",
          category: "Général",
          company: "",
          due_date: "",
        });
      }, 700);
    } catch (err: unknown) {
      console.error("Error creating task:", err);
      const msg = err instanceof Error ? err.message : "Erreur lors de la création de la démarche.";
      setError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="relative bg-slate-900 rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden border border-slate-800 animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="flex justify-between items-center px-6 py-4 border-b border-slate-800 bg-slate-950/40">
          <div>
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <FiPlus className="text-indigo-400" />
              <span>Nouvelle démarche</span>
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Créez une démarche libre ou liée à votre recherche d'emploi.
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
            disabled={isSubmitting}
            type="button"
          >
            <FiX className="text-xl" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4 max-h-[80vh] overflow-y-auto custom-scrollbar">
          {error && (
            <div className="bg-rose-500/10 border border-rose-500/30 text-rose-300 p-3 rounded-xl text-xs flex items-center gap-2">
              <FiAlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {showSuccess && (
            <div className="bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 p-3 rounded-xl text-xs flex items-center gap-2">
              <FiCheck className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>Démarche ajoutée avec succès !</span>
            </div>
          )}

          {/* Titre */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              Intitulé de l'action *
            </label>
            <input
              name="title"
              value={form.title}
              onChange={handleChange}
              placeholder="Ex: Relancer l'équipe RH, Mettre à jour profil LinkedIn, Réviser Docker..."
              className="w-full rounded-xl bg-slate-950 border border-slate-800 py-2.5 px-3.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all"
              required
              autoFocus
            />
          </div>

          {/* Catégorie et Priorité */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1.5">
                <FiTag className="text-indigo-400" />
                <span>Catégorie</span>
              </label>
              <select
                name="category"
                value={form.category}
                onChange={handleChange}
                className="w-full rounded-xl bg-slate-950 border border-slate-800 py-2.5 px-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                {CATEGORIES.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Niveau d'urgence
              </label>
              <select
                name="priority"
                value={form.priority}
                onChange={handleChange}
                className="w-full rounded-xl bg-slate-950 border border-slate-800 py-2.5 px-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                {PRIORITIES.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Entreprise (optionnelle) et Date d'échéance */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1.5">
                <FiBriefcase className="text-slate-400" />
                <span>Entreprise / Contexte (optionnel)</span>
              </label>
              <input
                name="company"
                value={form.company}
                onChange={handleChange}
                placeholder="Ex: Google, Alan, Démarche perso..."
                className="w-full rounded-xl bg-slate-950 border border-slate-800 py-2.5 px-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1.5">
                <FiCalendar className="text-indigo-400" />
                <span>Date d'échéance (optionnel)</span>
              </label>
              <input
                type="date"
                name="due_date"
                value={form.due_date}
                onChange={handleChange}
                className="w-full rounded-xl bg-slate-950 border border-slate-800 py-2 px-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>

          {/* Description & Notes */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              Notes & Détails (optionnel)
            </label>
            <textarea
              name="description"
              value={form.description}
              onChange={handleChange}
              rows={3}
              placeholder="Précisez les points clés, contacts, liens ou informations importantes..."
              className="w-full rounded-xl bg-slate-950 border border-slate-800 py-2.5 px-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all"
            />
          </div>

          {/* Statut Initial */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              Statut initial
            </label>
            <div className="grid grid-cols-3 gap-2">
              {[TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.DONE].map((st) => (
                <button
                  key={st}
                  type="button"
                  onClick={() => setForm({ ...form, status: st })}
                  className={`py-2 px-3 rounded-xl text-xs font-semibold border transition-all ${
                    form.status === st
                      ? "bg-indigo-600 border-indigo-500 text-white shadow-sm shadow-indigo-500/20"
                      : "bg-slate-950 border-slate-800 text-slate-400 hover:text-white"
                  }`}
                >
                  {st}
                </button>
              ))}
            </div>
          </div>

          {/* Footer Actions */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-xl transition-colors"
              disabled={isSubmitting}
            >
              Annuler
            </button>
            <button
              type="submit"
              className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl transition-all shadow-md shadow-indigo-500/20 flex items-center gap-2"
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <span>Création...</span>
              ) : (
                <>
                  <FiPlus />
                  <span>Ajouter la démarche</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
