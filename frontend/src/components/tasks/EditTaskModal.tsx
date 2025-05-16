"use client";

import { useState, useEffect } from "react";
import { Task, TaskStatus } from "@/types/tasks";
import { FiX, FiSave, FiTrash2 } from "react-icons/fi";
import { taskApi } from "@/lib/api";

interface EdittaskModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: (updatedTask: Task) => void;
  onDelete?: (taskId: string) => void;
  task: Task | null;
}

type TaskFormData = {
  title: string;
  description: string;
  status: string;
};

export default function EdittaskModal({
  isOpen,
  onClose,
  onSuccess,
  onDelete,
  task,
}: EdittaskModalProps) {
  const [form, setForm] = useState<TaskFormData>({
    title: "",
    description: "",
    status: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (task) {
      setForm({
        title: task.title || "",
        description: task.description || "",
        status: task.status || "",
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
      const updated = await taskApi.update(task._id!, {
        ...form,
        status: form.status as unknown as TaskStatus,
      });
      if (onSuccess) onSuccess(updated);
      onClose();
    } catch (err) {
      setError("Erreur lors de la mise à jour de la tâche.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async () => {
  if (!task?._id) return;
  const id = task._id; 
  setIsSubmitting(true);
  try {
    await taskApi.delete(id);
    if (onDelete) {
      onDelete(id);
    }
    onClose();
  } catch (err) {
    setError("Erreur lors de la suppression de la tâche.");
  } finally {
    setIsSubmitting(false);
  }
};

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center">
      <div className="relative bg-blue-night-lighter rounded-lg shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto border border-gray-700">
        <div className="flex justify-between items-center px-6 py-4 border-b border-gray-700">
          <h2 className="text-xl font-semibold text-white flex items-center">
            <FiSave className="mr-2" /> Modifier la tâche
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors"
            disabled={isSubmitting}
          >
            <FiX className="text-xl" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
  <div className="bg-red-900/40 border border-red-600 text-red-200 p-3 rounded-md mb-2">
    {error}
  </div>
)}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Titre *
            </label>
            <input
              name="title"
              value={form.title}
              onChange={handleChange}
              className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Description
            </label>
            <textarea
              name="description"
              value={form.description}
              onChange={handleChange}
              rows={3}
              className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Statut
            </label>
            <select
              name="status"
              value={form.status}
              onChange={handleChange}
              className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Sélectionner un statut</option>
              <option value="en attente">En attente</option>
              <option value="en cours">En cours</option>
              <option value="terminée">Terminée</option>
            </select>
          </div>
          <div className="flex justify-between space-x-3 pt-4 border-t border-gray-700">
            <button
              type="button"
              onClick={handleDelete}
              className="px-4 py-2 bg-red-700 text-white rounded-md hover:bg-red-600 transition-colors flex items-center"
              disabled={isSubmitting}
            >
              <FiTrash2 className="mr-2" />
              Supprimer
            </button>
            <div className="flex space-x-3">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 bg-gray-700 text-white rounded-md hover:bg-gray-600 transition-colors"
                disabled={isSubmitting}
              >
                Annuler
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-500 transition-colors flex items-center"
                disabled={isSubmitting}
              >
                {isSubmitting ? (
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
                    Enregistrement...
                  </>
                ) : (
                  <>
                    <FiSave className="mr-2" />
                    Enregistrer
                  </>
                )}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
