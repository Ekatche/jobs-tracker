"use client";

import { useState, useEffect } from "react";
import { Task, TaskStatus } from "@/types/tasks";
import {
  FiX,
  FiSave,
  FiTrash2,
  FiCalendar,
  FiTag,
  FiBriefcase,
  FiAlertCircle,
} from "react-icons/fi";
import { taskApi } from "@/lib/api";

interface EdittaskModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: (updatedTask: Task) => void;
  onDelete?: (taskId: string) => void;
  task: Task | null;
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
  { value: "haute", label: "Haute priorité" },
  { value: "normale", label: "Priorité normale" },
  { value: "basse", label: "Basse priorité" },
];

export default function EdittaskModal({
  isOpen,
  onClose,
  onSuccess,
  onDelete,
  task,
}: EdittaskModalProps) {
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

  useEffect(() => {
    if (task) {
      const formattedDueDate = task.due_date
        ? new Date(task.due_date).toISOString().split("T")[0]
        : "";

      setForm({
        title: task.title || "",
        description: task.description || "",
        status: (task.status as TaskStatus) || TaskStatus.TODO,
        priority: task.priority || "normale",
        category: task.category || "Général",
        company: task.company || "",
        due_date: formattedDueDate,
      });
    }
  }, [task]);

  if (!isOpen || !task) return null;

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
      setError("Le titre est requis.");
      return;
    }
    setIsSubmitting(true);

    try {
      const payload: Partial<Task> = {
        title: form.title.trim(),
        description: form.description?.trim() || undefined,
        status: form.status,
        priority: form.priority,
        category: form.category,
        company: form.company?.trim() || undefined,
        due_date: form.due_date ? new Date(form.due_date).toISOString() : undefined,
      };

      const updated = await taskApi.update(task._id!, payload);
      if (onSuccess) onSuccess(updated);
      onClose();
    } catch (err: unknown) {
      console.error("Error updating task:", err);
      const msg = err instanceof Error ? err.message : "Erreur lors de la mise à jour de la démarche.";
      setError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!task?._id) return;
    const id = task._id;
    if (!window.confirm("Êtes-vous sûr de vouloir supprimer cette démarche ?")) return;

    setIsSubmitting(true);
    try {
      await taskApi.delete(id);
      if (onDelete) {
        onDelete(id);
      }
      onClose();
    } catch (err) {
      setError("Erreur lors de la suppression de la démarche.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="relative bg-slate-900 rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden border border-slate-800 animate-in fade-in zoom-in-95 duration-200">
        <div className="flex justify-between items-center px-6 py-4 border-b border-slate-800 bg-slate-950/40">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <FiSave className="text-indigo-400" />
            <span>Modifier la démarche</span>
          </h2>
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

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              Intitulé *
            </label>
            <input
              name="title"
              value={form.title}
              onChange={handleChange}
              className="w-full rounded-xl bg-slate-950 border border-slate-800 py-2.5 px-3.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
              required
            />
          </div>

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
                Urgence
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

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1.5">
                <FiBriefcase className="text-slate-400" />
                <span>Entreprise / Contexte</span>
              </label>
              <input
                name="company"
                value={form.company}
                onChange={handleChange}
                className="w-full rounded-xl bg-slate-950 border border-slate-800 py-2.5 px-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1.5">
                <FiCalendar className="text-indigo-400" />
                <span>Date d'échéance</span>
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

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              Notes & Détails
            </label>
            <textarea
              name="description"
              value={form.description}
              onChange={handleChange}
              rows={3}
              className="w-full rounded-xl bg-slate-950 border border-slate-800 py-2.5 px-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              Statut d'avancement
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

          <div className="flex items-center justify-between pt-4 border-t border-slate-800">
            <button
              type="button"
              onClick={handleDelete}
              className="px-3.5 py-2 bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 text-xs font-semibold rounded-xl transition-colors flex items-center gap-1.5"
              disabled={isSubmitting}
            >
              <FiTrash2 />
              <span>Supprimer</span>
            </button>
            <div className="flex items-center gap-2">
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
                className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl transition-all shadow-md shadow-indigo-500/20 flex items-center gap-1.5"
                disabled={isSubmitting}
              >
                <FiSave />
                <span>Enregistrer</span>
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
