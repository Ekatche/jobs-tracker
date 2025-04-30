'use client';

import { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { FiX, FiSave, FiCalendar, FiCheck, FiArchive } from 'react-icons/fi';
import { applicationApi } from '@/lib/api';
import { format } from 'date-fns';
import { Application } from '@/types/application';

// Schéma de validation pour le formulaire (identique à NewApplicationModal)
const applicationSchema = z.object({
  company: z.string().min(1, 'Le nom de l\'entreprise est requis'),
  position: z.string().min(1, 'Le poste est requis'),
  location: z.string().optional(),
  status: z.string().min(1, 'Le statut est requis'),
  url: z.string().url('URL invalide').optional().or(z.literal('')),
  application_date: z.string().min(1, 'La date de candidature est requise'),
  description: z.string().optional(),
  archived: z.boolean().optional(), // Ajout du champ archived
});

type ApplicationFormData = z.infer<typeof applicationSchema>;


interface EditApplicationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  application: Application | null;
}

export default function EditApplicationModal({ isOpen, onClose, onSuccess, application }: EditApplicationModalProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showSuccessMessage, setShowSuccessMessage] = useState(false);
  const [actionType, setActionType] = useState<'update' | 'delete' | 'archive' | null>(null);

  const [notes, setNotes] = useState<string[]>([]);
  const [newNote, setNewNote] = useState<string>('');
  const [isAddingNote, setIsAddingNote] = useState<boolean>(false);
  const [editingNoteIndex, setEditingNoteIndex] = useState<number | null>(null);
  const [editedNoteText, setEditedNoteText] = useState<string>('');

  const { register, handleSubmit, reset, formState: { errors } } = useForm<ApplicationFormData>({
    resolver: zodResolver(applicationSchema),
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

  // Mettre à jour le formulaire quand une application est sélectionnée
  useEffect(() => {
    if (application) {
      reset({
        company: application.company,
        position: application.position,
        location: application.location || '',
        status: application.status,
        url: application.url || '',
        application_date: application.application_date.substring(0, 10), // Format YYYY-MM-DD
        description: application.description || '',
      });
    }
  }, [application, reset]);

  // Mettre à jour les notes lorsque l'application change
  useEffect(() => {
    if (application?.notes) {
      setNotes(application.notes);
    } else {
      setNotes([]);
    }
  }, [application]);

  // Fonction pour gérer la suppression d'une candidature
  const handleDeleteApplication = async () => {
    if (!application?._id) return;
    
    // Demander confirmation avant suppression
    if (!confirm('Êtes-vous sûr de vouloir supprimer cette candidature ? Cette action est irréversible.')) {
      return;
    }
    
    try {
      setIsSubmitting(true);
      setError(null);
      setActionType('delete');
      
      // Appel à l'API pour supprimer la candidature
      await applicationApi.delete(application._id);
      
      // Afficher un message de succès temporaire
      setShowSuccessMessage(true);
      
      // Fermer le modal et actualiser la liste des candidatures après un délai
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 1000);
      
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message || 'Une erreur est survenue lors de la suppression de la candidature');
      } else {
        setError('Une erreur est survenue lors de la suppression de la candidature');
      }
      setIsSubmitting(false);
    }
  };

  const onSubmit = async (data: ApplicationFormData) => {
    if (!application?._id) return;
    
    setIsSubmitting(true);
    setError(null);
    setShowSuccessMessage(false);
    setActionType('update');

    try {
      // Traitement des données avant envoi
      const formData = {
        ...data,
        url: data.url === '' ? undefined : data.url,
        notes: notes // Ajoutez les notes aux données du formulaire
      };

      // Appel à l'API pour mettre à jour la candidature
      await applicationApi.update(application._id, formData);
      
      // Afficher le message de succès
      setShowSuccessMessage(true);
      
      // Fermer le modal et actualiser la liste des candidatures après un délai
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 1500);
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message || 'Une erreur est survenue lors de la modification de la candidature');
      } else {
        setError('Une erreur est survenue lors de la modification de la candidature');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  // Ajouter une note
  const handleAddNote = () => {
    if (!newNote.trim()) return;
    
    const updatedNotes = [...notes, newNote];
    setNotes(updatedNotes);
    setNewNote('');
  };

  // Supprimer une note
  const handleDeleteNote = (index: number) => {
    const updatedNotes = [...notes];
    updatedNotes.splice(index, 1);
    setNotes(updatedNotes);
  };

  // Commencer l'édition d'une note
  const handleStartEditNote = (index: number, noteText: string) => {
    setEditingNoteIndex(index);
    setEditedNoteText(noteText);
  };

  // Sauvegarder une note modifiée
  const handleSaveEditNote = () => {
    if (editingNoteIndex === null || !editedNoteText.trim()) return;
    
    const updatedNotes = [...notes];
    updatedNotes[editingNoteIndex] = editedNoteText;
    setNotes(updatedNotes);
    
    setEditingNoteIndex(null);
    setEditedNoteText('');
  };

  // Annuler l'édition d'une note
  const handleCancelEditNote = () => {
    setEditingNoteIndex(null);
    setEditedNoteText('');
  };

  // Fonction pour gérer l'archivage/désarchivage d'une candidature
  const handleToggleArchive = async () => {
    if (!application) return;
    
    try {
      setIsSubmitting(true);
      setActionType('archive');
      
      // Mettre à jour l'état archivé
      await applicationApi.update(application._id, {
        ...application,
        archived: !application.archived
      });
      
      // Afficher le message de succès
      setShowSuccessMessage(true);
      
      // Appeler la fonction de succès après un délai
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 1500);
      
    } catch (error) {
      console.error("Erreur lors de l'archivage/désarchivage:", error);
      setError("Une erreur est survenue lors de l'archivage/désarchivage de la candidature");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen || !application) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black/60 backdrop-blur-sm flex items-center justify-center">
      <div className="relative bg-blue-night-lighter rounded-lg shadow-xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto border border-gray-700">
        <div className="flex justify-between items-center px-6 py-4 border-b border-gray-700">
          <h2 className="text-xl font-semibold text-white flex items-center">
            <FiSave className="mr-2" /> Modifier la candidature
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
            <div className={`${actionType === 'delete' ? 'bg-red-900/40 border-red-600' : 'bg-green-900/40 border-green-600'} border p-3 rounded-md mb-4 flex items-center text-white`}>
              <FiCheck className="mr-2" /> 
              {actionType === 'delete' 
                ? 'Candidature supprimée avec succès !' 
                : actionType === 'archive'
                ? 'Candidature archivée avec succès !'
                : 'Candidature modifiée avec succès !'}
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Entreprise */}
              <div className="col-span-1">
                <label htmlFor="company" className="block text-sm font-medium text-gray-300 mb-1">
                  Entreprise *
                </label>
                <input
                  id="company"
                  type="text"
                  {...register('company')}
                  className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                {errors.company && (
                  <p className="mt-1 text-sm text-red-400">{errors.company.message}</p>
                )}
              </div>

              {/* Poste */}
              <div className="col-span-1">
                <label htmlFor="position" className="block text-sm font-medium text-gray-300 mb-1">
                  Poste *
                </label>
                <input
                  id="position"
                  type="text"
                  {...register('position')}
                  className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                {errors.position && (
                  <p className="mt-1 text-sm text-red-400">{errors.position.message}</p>
                )}
              </div>

              {/* Localisation */}
              <div className="col-span-1">
                <label htmlFor="location" className="block text-sm font-medium text-gray-300 mb-1">
                  Localisation
                </label>
                <input
                  id="location"
                  type="text"
                  {...register('location')}
                  className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Ex: Paris, Remote, etc."
                />
              </div>

              {/* Statut */}
              <div className="col-span-1">
                <label htmlFor="status" className="block text-sm font-medium text-gray-300 mb-1">
                  Statut *
                </label>
                <select
                  id="status"
                  {...register('status')}
                  className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="En étude">En étude</option>
                  <option value="Candidature envoyée">Candidature envoyée</option>
                  <option value="Première sélection">Première sélection</option>
                  <option value="Entretien">Entretien</option>
                  <option value="Test technique">Test technique</option>
                  <option value="Négociation">Négociation</option>
                  <option value="Offre reçue">Offre reçue</option>
                  <option value="Offre acceptée">Offre acceptée</option>
                  <option value="Refusée">Refusée</option>
                </select>
                {errors.status && (
                  <p className="mt-1 text-sm text-red-400">{errors.status.message}</p>
                )}
              </div>

              {/* URL de l'offre */}
              <div className="col-span-1">
                <label htmlFor="url" className="block text-sm font-medium text-gray-300 mb-1">
                  URL de l'offre
                </label>
                <input
                  id="url"
                  type="text"
                  {...register('url')}
                  className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="https://..."
                />
                {errors.url && (
                  <p className="mt-1 text-sm text-red-400">{errors.url.message}</p>
                )}
              </div>

              {/* Date de candidature */}
              <div className="col-span-1">
                <label htmlFor="application_date" className="block text-sm font-medium text-gray-300 mb-1">
                  Date de candidature *
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <FiCalendar className="text-gray-400" />
                  </div>
                  <input
                    id="application_date"
                    type="date"
                    {...register('application_date')}
                    className="w-full rounded-md bg-blue-night border border-gray-700 py-2 pl-10 pr-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                {errors.application_date && (
                  <p className="mt-1 text-sm text-red-400">{errors.application_date.message}</p>
                )}
              </div>
            </div>

            {/* Description */}
            <div>
              <label htmlFor="description" className="block text-sm font-medium text-gray-300 mb-1">
                Description
              </label>
              <textarea
                id="description"
                {...register('description')}
                rows={4}
                placeholder="Informations supplémentaires sur le poste, exigences, etc."
                className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              ></textarea>
            </div>

            {/* Notes */}
            <div className="mt-4">
              <h3 className="text-lg font-semibold mb-2">Notes</h3>
              
              {/* Liste des notes existantes */}
              <div className="space-y-2 mb-4">
                {notes.map((note, index) => (
                  <div key={index} className="p-3 bg-blue-night-light rounded-md relative group">
                    {editingNoteIndex === index ? (
                      <div>
                        <textarea
                          value={editedNoteText}
                          onChange={(e) => setEditedNoteText(e.target.value)}
                          className="w-full px-2 py-1 rounded-md bg-blue-night border border-gray-700 focus:border-blue-500 focus:outline-none text-white"
                          rows={3}
                        />
                        <div className="flex justify-end mt-2 space-x-2">
                          <button
                            type="button"
                            onClick={handleCancelEditNote}
                            className="px-2 py-1 bg-gray-700 hover:bg-gray-600 rounded-md text-sm"
                          >
                            Annuler
                          </button>
                          <button
                            type="button"
                            onClick={handleSaveEditNote}
                            disabled={!editedNoteText.trim()}
                            className={`px-2 py-1 rounded-md text-sm text-white ${
                              !editedNoteText.trim() ? 'bg-gray-600 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-500'
                            }`}
                          >
                            Enregistrer
                          </button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <p className="text-gray-300 pr-12">{note}</p>
                        <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity flex space-x-1">
                          <button 
                            type="button"
                            onClick={() => handleStartEditNote(index, note)}
                            className="p-1 rounded-full text-gray-400 hover:text-blue-400 hover:bg-blue-900/30"
                          >
                            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"></path>
                            </svg>
                          </button>
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
                      </>
                    )}
                  </div>
                ))}
              </div>
              
              {/* Formulaire d'ajout de note */}
              <div>
                <textarea
                  value={newNote}
                  onChange={(e) => setNewNote(e.target.value)}
                  placeholder="Ajouter une nouvelle note..."
                  className="w-full px-3 py-2 rounded-md bg-blue-night border border-gray-700 focus:border-blue-500 focus:outline-none text-white"
                  rows={2}
                />
                <div className="flex justify-end mt-2">
                  <button
                    type="button"
                    onClick={handleAddNote}
                    disabled={!newNote.trim() || isAddingNote}
                    className={`px-3 py-1 rounded-md flex items-center text-white ${
                      !newNote.trim() || isAddingNote ? 'bg-gray-600 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-500'
                    }`}
                  >
                    <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path>
                    </svg>
                    Ajouter
                  </button>
                </div>
              </div>
            </div>

            <div className="flex justify-between space-x-3 pt-4 border-t border-gray-700">
              {/* Bouton de suppression (à gauche) */}
              <button
                type="button"
                onClick={handleDeleteApplication}
                className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors flex items-center"
                disabled={isSubmitting || showSuccessMessage}
              >
                <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                </svg>
                Supprimer
              </button>

              {/* Bouton d'archivage */}
              <button
                type="button"
                onClick={handleToggleArchive}
                className={`px-4 py-2 ${
                  application?.archived 
                    ? 'bg-blue-600 hover:bg-blue-700' 
                    : 'bg-gray-600 hover:bg-gray-700'
                } text-white rounded-md transition-colors flex items-center`}
                disabled={isSubmitting || showSuccessMessage}
              >
                <FiArchive className="mr-2" />
                {application?.archived ? 'Désarchiver' : 'Archiver'}
              </button>
              
              <div className="flex space-x-3">
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
                      {actionType === 'delete' ? 'Suppression...' : 'Enregistrement...'}
                    </>
                  ) : showSuccessMessage ? (
                    <>
                      <FiCheck className="mr-2" />
                      {actionType === 'delete' ? 'Supprimée' : 'Enregistrée'}
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
    </div>
  );
}