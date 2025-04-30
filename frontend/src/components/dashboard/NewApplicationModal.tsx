'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { FiX, FiPlus, FiCalendar, FiCheck } from 'react-icons/fi';
import { applicationApi } from '@/lib/api';
import { format } from 'date-fns';

// Schéma de validation pour le formulaire (inchangé)
const applicationSchema = z.object({
  company: z.string().min(1, 'Le nom de l\'entreprise est requis'),
  position: z.string().min(1, 'Le poste est requis'),
  location: z.string().optional(),
  status: z.string().min(1, 'Le statut est requis'),
  url: z.string().url('URL invalide').optional().or(z.literal('')),
  application_date: z.string().min(1, 'La date de candidature est requise'),
  description: z.string().optional(),
});

type ApplicationFormData = z.infer<typeof applicationSchema>;

interface NewApplicationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export default function NewApplicationModal({ isOpen, onClose, onSuccess }: NewApplicationModalProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showSuccessMessage, setShowSuccessMessage] = useState(false);
  
  // États pour la gestion des notes
  const [notes, setNotes] = useState<string[]>([]);
  const [newNote, setNewNote] = useState<string>('');
  const [isAddingNote, setIsAddingNote] = useState<boolean>(false);

  const { register, handleSubmit, reset, formState: { errors } } = useForm<ApplicationFormData>({
    resolver: zodResolver(applicationSchema),
    mode: 'onChange',
    defaultValues: {
      company: '',
      position: '',
      location: '',
      status: 'Candidature envoyée',
      url: '',
      application_date: format(new Date(), 'yyyy-MM-dd'),
      description: '',
    }
  });

  // Fonction pour ajouter une note
  const handleAddNote = () => {
    if (!newNote.trim()) return;
    
    // Ajouter la note à la liste
    setNotes([...notes, newNote]);
    setNewNote('');
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
        url: data.url === '' ? undefined : data.url,
        notes: notes.length > 0 ? notes : undefined // Inclure les notes s'il y en a
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
        setError(err.message || 'Une erreur est survenue lors de la création de la candidature');
      } else {
        setError('Une erreur est survenue lors de la création de la candidature');
      }
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black bg-opacity-60 flex items-center justify-center">
      <div className="relative bg-blue-night-lighter rounded-lg shadow-xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center px-6 py-4 border-b border-gray-700">
          <h2 className="text-xl font-semibold text-white flex items-center">
            <FiPlus className="mr-2" /> Nouvelle candidature
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors"
            disabled={isSubmitting}
          >
            <FiX className="text-xl" />
          </button>
        </div>

        <div className="p-6">
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
            {Object.keys(errors).length > 0 && (
              <div className="bg-red-900/40 border border-red-600 text-red-200 p-3 rounded-md mb-4">
                <p className="font-medium">Le formulaire contient des erreurs :</p>
                <ul className="list-disc pl-5 mt-1 text-sm">
                  {errors.company && <li>Le nom de l'entreprise est requis</li>}
                  {errors.position && <li>Le poste est requis</li>}
                  {errors.status && <li>Le statut est requis</li>}
                  {errors.application_date && <li>La date de candidature est requise</li>}
                  {errors.url && <li>L'URL n'est pas valide</li>}
                </ul>
              </div>
            )}
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Entreprise */}
              <div className="col-span-1">
                <label htmlFor="company" className={`block text-sm font-medium mb-1 ${
                  errors.company ? 'text-red-400' : 'text-gray-300'
                }`}>
                  Entreprise *
                </label>
                <input
                  id="company"
                  type="text"
                  {...register('company')}
                  className={`w-full rounded-md bg-blue-night border py-2 px-3 text-white focus:outline-none focus:ring-2 ${
                    errors.company ? 'border-red-500 shadow-[0_0_0_1px_rgba(239,68,68,0.5)] focus:ring-red-500' : 'border-gray-700 focus:ring-blue-500'
                  }`}
                />
                {errors.company && (
                  <p className="mt-1 text-sm text-red-400">{errors.company.message}</p>
                )}
              </div>

              {/* Poste */}
              <div className="col-span-1">
                <label htmlFor="position" className={`block text-sm font-medium mb-1 ${
                  errors.position ? 'text-red-400' : 'text-gray-300'
                }`}>
                  Poste *
                </label>
                <input
                  id="position"
                  type="text"
                  {...register('position')}
                  className={`w-full rounded-md bg-blue-night border py-2 px-3 text-white focus:outline-none focus:ring-2 ${
                    errors.position ? 'border-red-500 shadow-[0_0_0_1px_rgba(239,68,68,0.5)] focus:ring-red-500' : 'border-gray-700 focus:ring-blue-500'
                  }`}
                />
                {errors.position && (
                  <p className="mt-1 text-sm text-red-400">{errors.position.message}</p>
                )}
              </div>

              {/* Localisation */}
              <div className="col-span-1">
                <label htmlFor="location" className={`block text-sm font-medium mb-1 ${
                  errors.location ? 'text-red-400' : 'text-gray-300'
                }`}>
                  Localisation
                </label>
                <input
                  id="location"
                  type="text"
                  {...register('location')}
                  placeholder="Ex: Paris, Remote, etc."
                  className={`w-full rounded-md bg-blue-night border py-2 px-3 text-white focus:outline-none focus:ring-2 ${
                    errors.location ? 'border-red-500 shadow-[0_0_0_1px_rgba(239,68,68,0.5)] focus:ring-red-500' : 'border-gray-700 focus:ring-blue-500'
                  }`}
                />
                {errors.location && (
                  <p className="mt-1 text-sm text-red-400">{errors.location.message}</p>
                )}
              </div>

              {/* Date de candidature */}
              <div className="col-span-1">
                <label htmlFor="application_date" className={`block text-sm font-medium mb-1 ${
                  errors.application_date ? 'text-red-400' : 'text-gray-300'
                }`}>
                  Date de candidature *
                </label>
                <div className="relative">
                  <input
                    id="application_date"
                    type="date"
                    {...register('application_date')}
                    className={`w-full rounded-md bg-blue-night border py-2 px-3 text-white focus:outline-none focus:ring-2 ${
                      errors.application_date ? 'border-red-500 shadow-[0_0_0_1px_rgba(239,68,68,0.5)] focus:ring-red-500' : 'border-gray-700 focus:ring-blue-500'
                    }`}
                  />
                  <FiCalendar className={`absolute right-3 top-3 ${errors.application_date ? 'text-red-400' : 'text-gray-400'}`} />
                </div>
                {errors.application_date && (
                  <p className="mt-1 text-sm text-red-400">{errors.application_date.message}</p>
                )}
              </div>

              {/* Statut */}
              <div className="col-span-1">
                <label htmlFor="status" className={`block text-sm font-medium mb-1 ${
                  errors.status ? 'text-red-400' : 'text-gray-300'
                }`}>
                  Statut *
                </label>
                <select
                  id="status"
                  {...register('status')}
                  className={`w-full rounded-md bg-blue-night border py-2 px-3 text-white focus:outline-none focus:ring-2 ${
                    errors.status ? 'border-red-500 shadow-[0_0_0_1px_rgba(239,68,68,0.5)] focus:ring-red-500' : 'border-gray-700 focus:ring-blue-500'
                  }`}
                >
                  <option value="En étude">En étude</option>
                  <option value="Candidature envoyée">Candidature envoyée</option>
                  <option value="Première sélection">Première sélection</option>
                  <option value="Entretien">Entretien</option>
                  {/* <option value="Test technique">Test technique</option> */}
                  {/* <option value="Négociation">Négociation</option> */}
                  <option value="Offre reçue">Offre reçue</option>
                  {/* <option value="Offre acceptée">Offre acceptée</option> */}
                  <option value="Refusée">Refusée</option>
                </select>
                {errors.status && (
                  <p className="mt-1 text-sm text-red-400">{errors.status.message}</p>
                )}
              </div>

              {/* URL de l'offre */}
              <div className="col-span-1">
                <label htmlFor="url" className={`block text-sm font-medium mb-1 ${
                  errors.url ? 'text-red-400' : 'text-gray-300'
                }`}>
                  URL de l'offre
                </label>
                <input
                  id="url"
                  type="url"
                  {...register('url')}
                  placeholder="https://example.com/job"
                  className={`w-full rounded-md bg-blue-night border py-2 px-3 text-white focus:outline-none focus:ring-2 ${
                    errors.url ? 'border-red-500 shadow-[0_0_0_1px_rgba(239,68,68,0.5)] focus:ring-red-500' : 'border-gray-700 focus:ring-blue-500'
                  }`}
                />
                {errors.url && (
                  <p className="mt-1 text-sm text-red-400">{errors.url.message}</p>
                )}
              </div>
            </div>

            {/* Description */}
            <div className="col-span-2">
              <label htmlFor="description" className={`block text-sm font-medium mb-1 ${
                errors.description ? 'text-red-400' : 'text-gray-300'
              }`}>
                Description
              </label>
              <textarea
                id="description"
                {...register('description')}
                rows={4}
                placeholder="Informations supplémentaires sur le poste, exigences, etc."
                className={`w-full rounded-md bg-blue-night border py-2 px-3 text-white focus:outline-none focus:ring-2 ${
                  errors.description ? 'border-red-500 shadow-[0_0_0_1px_rgba(239,68,68,0.5)] focus:ring-red-500' : 'border-gray-700 focus:ring-blue-500'
                }`}
              ></textarea>
              {errors.description && (
                <p className="mt-1 text-sm text-red-400">{errors.description.message}</p>
              )}
            </div>

            {/* Section des notes - à ajouter */}
            <div className="mt-6">
              <h3 className="text-lg font-semibold mb-2 text-white">Notes</h3>
              
              {/* Liste des notes existantes */}
              <div className="space-y-2 mb-4">
                {notes.length > 0 ? (
                  notes.map((note, index) => (
                    <div key={index} className="p-3 bg-blue-night-light rounded-md relative group">
                      <p className="text-gray-300 pr-12">{note}</p>
                      <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button 
                          type="button"
                          onClick={() => handleDeleteNote(index)}
                          className="p-1 rounded-full text-gray-400 hover:text-red-400 hover:bg-red-900/30"
                        >
                          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                          </svg>
                        </button>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-gray-400 italic mb-4">Aucune note pour cette candidature</p>
                )}
              </div>
              
              {/* Formulaire d'ajout de note */}
              <div>
                {isAddingNote ? (
                  <div className="mb-4">
                    <textarea
                      value={newNote}
                      onChange={(e) => setNewNote(e.target.value)}
                      placeholder="Détails sur la candidature, contacts, préparation d'entretien..."
                      className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                      rows={3}
                    ></textarea>
                    <div className="flex space-x-2 mt-2">
                      <button
                        type="button"
                        onClick={handleAddNote}
                        className="px-3 py-1 bg-blue-600 text-white rounded-md hover:bg-blue-500 transition-colors flex items-center text-sm"
                      >
                        <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
                        </svg>
                        Ajouter
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setIsAddingNote(false);
                          setNewNote('');
                        }}
                        className="px-3 py-1 bg-gray-700 text-white rounded-md hover:bg-gray-600 transition-colors flex items-center text-sm"
                      >
                        <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                        Annuler
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => setIsAddingNote(true)}
                    className="mt-2 px-3 py-1 bg-blue-900/50 hover:bg-blue-900 text-white rounded-md transition-colors flex items-center text-sm"
                  >
                    <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path>
                    </svg>
                    Ajouter une note
                  </button>
                )}
              </div>
            </div>

            <div className="flex justify-end space-x-3 pt-4 border-t border-gray-700">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 bg-gray-700 text-white rounded-md hover:bg-gray-600 transition-colors"
                disabled={isSubmitting || showSuccessMessage}
              >
                Annuler
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-500 transition-colors flex items-center"
                disabled={isSubmitting || showSuccessMessage}
              >
                {isSubmitting ? (
                  <>
                    <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Création en cours...
                  </>
                ) : (
                  'Créer la candidature'
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}