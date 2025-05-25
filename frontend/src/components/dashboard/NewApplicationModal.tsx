"use client";

import { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { FiX, FiPlus, FiCalendar, FiCheck } from "react-icons/fi";
import { applicationApi } from "@/lib/api";
import { format } from "date-fns";

// Schéma de validation pour le formulaire
const applicationSchema = z.object({
  company: z.string().min(1, "Le nom de l'entreprise est requis"),
  position: z.string().min(1, "Le poste est requis"),
  location: z.string().optional(),
  status: z.string().min(1, "Le statut est requis"),
  url: z.string().url("URL invalide").optional().or(z.literal("")),
  application_date: z.string().min(1, "La date de candidature est requise"),
  description: z.string().optional(),
});

type ApplicationFormData = z.infer<typeof applicationSchema>;

// Interface pour les données pré-remplies depuis une offre
export interface PrefilledData {
  company?: string;
  position?: string;
  location?: string;
  url?: string;
}

interface NewApplicationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  prefilledData?: PrefilledData; // Nouvelles données pré-remplies
}

export default function NewApplicationModal({
  isOpen,
  onClose,
  onSuccess,
  prefilledData,
}: NewApplicationModalProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showSuccessMessage, setShowSuccessMessage] = useState(false);

  // États pour la gestion des notes
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
    },
  });

  // Effet pour pré-remplir le formulaire quand prefilledData change
  useEffect(() => {
    if (prefilledData && isOpen) {
      if (prefilledData.company) setValue("company", prefilledData.company);
      if (prefilledData.position) setValue("position", prefilledData.position);
      if (prefilledData.location) setValue("location", prefilledData.location);
      if (prefilledData.url) setValue("url", prefilledData.url);

      // Réinitialiser les autres champs à leurs valeurs par défaut
      setValue("status", "Candidature envoyée");
      setValue("application_date", format(new Date(), "yyyy-MM-dd"));
      setValue("description", "");

      // Ajouter une note automatique si on vient d'une offre
      if (prefilledData.company || prefilledData.position) {
        const autoNote = `Candidature créée depuis une offre d'emploi le ${format(
          new Date(),
          "dd/MM/yyyy",
        )}`;
        setNotes([autoNote]);
      }
    }
  }, [prefilledData, isOpen, setValue]);

  // Réinitialiser le formulaire quand la modal se ferme
  useEffect(() => {
    if (!isOpen) {
      reset();
      setNotes([]);
      setNewNote("");
      setIsAddingNote(false);
      setError(null);
      setShowSuccessMessage(false);
    }
  }, [isOpen, reset]);

  // Fonction pour ajouter une note
  const handleAddNote = () => {
    if (!newNote.trim()) return;

    // Ajouter la note à la liste
    setNotes([...notes, newNote]);
    setNewNote("");
    setIsAddingNote(false);
  };

  // Fonction pour supprimer une note
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
      // Traitement des données avant envoi
      const formData = {
        ...data,
        url: data.url === "" ? undefined : data.url,
        notes: notes.length > 0 ? notes : undefined, // Inclure les notes s'il y en a
      };

      // Appel à l'API pour créer une nouvelle candidature
      await applicationApi.create(formData);

      // Afficher le message de succès
      setShowSuccessMessage(true);

      // Réinitialiser le formulaire et les notes
      reset();
      setNotes([]);

      // Appeler onSuccess pour déclencher le rafraîchissement et fermer la modal
      onSuccess();
    } catch (err) {
      if (err instanceof Error) {
        setError(
          err.message ||
            "Une erreur est survenue lors de la création de la candidature",
        );
      } else {
        setError(
          "Une erreur est survenue lors de la création de la candidature",
        );
      }
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
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <FiX className="w-5 h-5" />
          </button>
        </div>

        <div className="px-6 py-4">
          {/* Message de pré-remplissage */}
          {prefilledData && (
            <div className="bg-blue-900/40 border border-blue-600 text-blue-200 p-3 rounded-md mb-4 flex items-center">
              <FiCheck className="mr-2" />
              Informations pré-remplies depuis l'offre. Vérifiez et modifiez si
              nécessaire.
            </div>
          )}

          {/* Message d'erreur */}
          {error && (
            <div className="bg-red-900/40 border border-red-600 text-red-200 p-3 rounded-md mb-4">
              {error}
            </div>
          )}

          {/* Message de succès */}
          {showSuccessMessage && (
            <div className="bg-green-900/40 border border-green-600 text-green-200 p-3 rounded-md mb-4 flex items-center">
              <FiCheck className="mr-2" /> Candidature enregistrée avec succès !
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {Object.keys(errors).length > 0 && (
              <div className="bg-red-900/40 border border-red-600 text-red-200 p-3 rounded-md mb-4">
                <p className="font-medium">
                  Le formulaire contient des erreurs :
                </p>
                <ul className="list-disc pl-5 mt-1 text-sm">
                  {errors.company && <li>Le nom de l'entreprise est requis</li>}
                  {errors.position && <li>Le poste est requis</li>}
                  {errors.status && <li>Le statut est requis</li>}
                  {errors.url && <li>L'URL doit être valide</li>}
                  {errors.application_date && (
                    <li>La date de candidature est requise</li>
                  )}
                </ul>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Entreprise */}
              <div className="col-span-1">
                <label
                  htmlFor="company"
                  className="block text-sm font-medium text-gray-300 mb-1"
                >
                  Entreprise *
                </label>
                <input
                  id="company"
                  type="text"
                  {...register("company")}
                  className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                {errors.company && (
                  <p className="mt-1 text-sm text-red-400">
                    {errors.company.message}
                  </p>
                )}
              </div>

              {/* Poste */}
              <div className="col-span-1">
                <label
                  htmlFor="position"
                  className="block text-sm font-medium text-gray-300 mb-1"
                >
                  Poste *
                </label>
                <input
                  id="position"
                  type="text"
                  {...register("position")}
                  className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                {errors.position && (
                  <p className="mt-1 text-sm text-red-400">
                    {errors.position.message}
                  </p>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Localisation */}
              <div className="col-span-1">
                <label
                  htmlFor="location"
                  className="block text-sm font-medium text-gray-300 mb-1"
                >
                  Localisation
                </label>
                <input
                  id="location"
                  type="text"
                  {...register("location")}
                  className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {/* Statut */}
              <div className="col-span-1">
                <label
                  htmlFor="status"
                  className="block text-sm font-medium text-gray-300 mb-1"
                >
                  Statut *
                </label>
                <select
                  id="status"
                  {...register("status")}
                  className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="En étude">En étude</option>
                  <option value="Candidature envoyée">
                    Candidature envoyée
                  </option>
                  <option value="Première sélection">Première sélection</option>
                  <option value="Entretien">Entretien</option>
                  <option value="Offre reçue">Offre reçue</option>
                  <option value="Refusée">Refusée</option>
                </select>
                {errors.status && (
                  <p className="mt-1 text-sm text-red-400">
                    {errors.status.message}
                  </p>
                )}
              </div>
            </div>

            {/* URL de l'offre */}
            <div>
              <label
                htmlFor="url"
                className="block text-sm font-medium text-gray-300 mb-1"
              >
                URL de l'offre
              </label>
              <input
                id="url"
                type="url"
                {...register("url")}
                className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="https://exemple.com/offre"
              />
              {errors.url && (
                <p className="mt-1 text-sm text-red-400">
                  {errors.url.message}
                </p>
              )}
            </div>

            {/* Date de candidature */}
            <div>
              <label
                htmlFor="application_date"
                className="block text-sm font-medium text-gray-300 mb-1"
              >
                Date de candidature *
              </label>
              <div className="relative">
                <input
                  id="application_date"
                  type="date"
                  {...register("application_date")}
                  className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <FiCalendar className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 pointer-events-none" />
              </div>
              {errors.application_date && (
                <p className="mt-1 text-sm text-red-400">
                  {errors.application_date.message}
                </p>
              )}
            </div>

            {/* Description */}
            <div>
              <label
                htmlFor="description"
                className="block text-sm font-medium text-gray-300 mb-1"
              >
                Description
              </label>
              <textarea
                id="description"
                {...register("description")}
                rows={3}
                className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Description du poste, compétences requises, etc."
              />
            </div>

            {/* Section Notes */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Notes
              </label>

              {/* Liste des notes existantes */}
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
                          <svg
                            className="w-4 h-4"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                            ></path>
                          </svg>
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

              {/* Formulaire d'ajout de note */}
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

            {/* Boutons d'action */}
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
                {isSubmitting ? (
                  <>
                    <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white">
                      <circle
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                        fill="none"
                      />
                      <path
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      />
                    </svg>
                    Enregistrement...
                  </>
                ) : (
                  "Enregistrer la candidature"
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
