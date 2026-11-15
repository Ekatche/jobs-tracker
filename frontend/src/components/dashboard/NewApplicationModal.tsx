"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { FiX, FiPlus, FiCheck, FiFileText, FiTrash2 } from "react-icons/fi";
import { applicationApi } from "@/lib/api";
import { format } from "date-fns";
import {
  applicationSchema,
  type ApplicationFormData,
  NEW_APP_STATUSES,
} from "./application-modal/applicationFormSchema";
import ApplicationFormFields from "./application-modal/ApplicationFormFields";

export interface PrefilledData {
  company?: string;
  position?: string;
  location?: string;
  url?: string;
  description?: string;
  offer_id?: string;
}

interface NewApplicationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  prefilledData?: PrefilledData;
}

export default function NewApplicationModal({
  isOpen,
  onClose,
  onSuccess,
  prefilledData,
}: NewApplicationModalProps) {
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [showSuccessMessage, setShowSuccessMessage] = useState(false);

  const [notes, setNotes] = useState<string[]>([]);
  const [newNote, setNewNote] = useState<string>("");
  const [isAddingNote, setIsAddingNote] = useState<boolean>(false);

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    formState: { errors },
  } = useForm<ApplicationFormData>({
    resolver: zodResolver(applicationSchema),
    mode: "onChange",
    defaultValues: {
      company: "",
      position: "",
      location: "",
      status: "Candidature envoyée",
      url: "",
      application_date: format(new Date(), "yyyy-MM-dd"),
      description: "",
      offer_id: "",
    },
  });

  useEffect(() => {
    if (prefilledData && isOpen) {
      if (prefilledData.company) setValue("company", prefilledData.company);
      if (prefilledData.position) setValue("position", prefilledData.position);
      if (prefilledData.location) setValue("location", prefilledData.location);
      if (prefilledData.url) setValue("url", prefilledData.url);
      if (prefilledData.offer_id) setValue("offer_id", prefilledData.offer_id);
      setValue("description", prefilledData.description || "");
      setValue("status", "En étude");
      setValue("application_date", format(new Date(), "yyyy-MM-dd"));

      if (prefilledData.company || prefilledData.position) {
        setNotes([
          `Candidature créée depuis une offre d'emploi le ${format(new Date(), "dd/MM/yyyy")}`,
        ]);
      }
    }
  }, [prefilledData, isOpen, setValue]);

  useEffect(() => {
    if (!isOpen) {
      reset();
      setNotes([]);
      setNewNote("");
      setIsAddingNote(false);
      setError(null);
      setShowSuccessMessage(false);
      setIsSubmitting(false);
    }
  }, [isOpen, reset]);

  const handleAddNote = () => {
    if (!newNote.trim()) return;
    setNotes([...notes, newNote]);
    setNewNote("");
    setIsAddingNote(false);
  };

  const handleDeleteNote = (index: number) => {
    const updatedNotes = [...notes];
    updatedNotes.splice(index, 1);
    setNotes(updatedNotes);
  };

  const onSubmit = async (data: ApplicationFormData) => {
    setIsSubmitting(true);
    setError(null);
    setShowSuccessMessage(false);

    try {
      await applicationApi.create({
        ...data,
        url: data.url === "" ? undefined : data.url,
        offer_id: data.offer_id === "" ? undefined : data.offer_id,
        notes: notes.length > 0 ? notes : undefined,
      });
      setShowSuccessMessage(true);
      reset();
      setNotes([]);
      onSuccess();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Une erreur est survenue lors de la création de la candidature"
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black bg-opacity-60 flex items-center justify-center">
      <div className="relative bg-blue-night-lighter rounded-lg shadow-xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto border border-gray-700">
        <div className="flex justify-between items-center px-6 py-4 border-b border-gray-700">
          <h2 className="text-xl font-semibold text-white flex items-center">
            <FiPlus className="mr-2" />
            {prefilledData ? "Postuler à cette offre" : "Nouvelle candidature"}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
            <FiX className="w-5 h-5" />
          </button>
        </div>

        <div className="px-6 py-4">
          {prefilledData && (
            <div className="bg-blue-900/40 border border-blue-600/70 text-blue-200 p-3 rounded-lg mb-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center text-sm">
                <FiCheck className="mr-2 text-emerald-400 shrink-0" />
                <span>Informations pré-remplies depuis l&apos;offre.</span>
              </div>
              {prefilledData.offer_id && (
                <Link
                  href={`/resumes?generate_offer_id=${prefilledData.offer_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition-all shadow-sm shadow-indigo-500/30 shrink-0"
                  title="Générer un CV adapté sur-mesure pour cette offre (ouvre un nouvel onglet)"
                >
                  <FiFileText className="w-3.5 h-3.5" />
                  <span>CV Adapté</span>
                </Link>
              )}
            </div>
          )}

          {error && (
            <div className="bg-red-900/40 border border-red-600 text-red-200 p-3 rounded-md mb-4">
              {error}
            </div>
          )}

          {showSuccessMessage && (
            <div className="bg-green-900/40 border border-green-600 text-green-200 p-3 rounded-md mb-4 flex items-center">
              <FiCheck className="mr-2" /> Candidature enregistrée avec succès !
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <ApplicationFormFields
              register={register}
              errors={errors}
              statuses={NEW_APP_STATUSES}
              descriptionRows={3}
            />

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Notes</label>
              <div className="mb-4">
                {notes.length > 0 ? (
                  notes.map((note, index) => (
                    <div
                      key={index}
                      className="bg-blue-night/50 border border-gray-700 rounded-md p-3 mb-2"
                    >
                      <div className="flex justify-between items-start">
                        <p className="text-gray-200 flex-1">{note}</p>
                        <button
                          type="button"
                          onClick={() => handleDeleteNote(index)}
                          className="ml-2 text-red-400 hover:text-red-300 transition-colors"
                        >
                          <FiTrash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-gray-400 italic mb-4">
                    Aucune note pour cette candidature
                  </p>
                )}
              </div>

              <div>
                {isAddingNote ? (
                  <div className="mb-4">
                    <textarea
                      value={newNote}
                      onChange={(e) => setNewNote(e.target.value)}
                      placeholder="Tapez votre note ici..."
                      className="w-full px-3 py-2 rounded-md bg-blue-night border border-gray-700 focus:border-blue-500 focus:outline-none text-white"
                      rows={2}
                    />
                    <div className="flex justify-end gap-2 mt-2">
                      <button
                        type="button"
                        onClick={() => {
                          setIsAddingNote(false);
                          setNewNote("");
                        }}
                        className="px-3 py-1 rounded-md bg-gray-600 hover:bg-gray-500 text-white text-sm"
                      >
                        Annuler
                      </button>
                      <button
                        type="button"
                        onClick={handleAddNote}
                        disabled={!newNote.trim()}
                        className={`px-3 py-1 rounded-md text-white text-sm ${
                          !newNote.trim()
                            ? "bg-gray-600 cursor-not-allowed"
                            : "bg-blue-600 hover:bg-blue-500"
                        }`}
                      >
                        Ajouter
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => setIsAddingNote(true)}
                    className="flex items-center gap-2 px-3 py-2 rounded-md bg-blue-night border border-gray-700 hover:border-blue-500 text-gray-300 hover:text-white transition-colors"
                  >
                    <FiPlus className="w-4 h-4" />
                    Ajouter une note
                  </button>
                )}
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-4 border-t border-gray-700">
              <button
                type="button"
                onClick={onClose}
                disabled={isSubmitting}
                className="px-4 py-2 text-sm font-medium text-gray-300 bg-transparent border border-gray-600 rounded-md hover:bg-gray-800 transition-colors disabled:opacity-50"
              >
                Annuler
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors disabled:opacity-50 flex items-center"
              >
                {isSubmitting ? "Enregistrement..." : "Enregistrer la candidature"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
