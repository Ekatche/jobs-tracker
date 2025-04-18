"use client";

import { useState, useEffect, useCallback } from 'react';
import { applicationApi } from '@/lib/api';
import { useNotification } from '@/contexts/NotificationContext';
import { FiEdit } from 'react-icons/fi';

// Définir l'interface pour une candidature conforme au backend
interface Application {
  _id: string;
  user_id: string;
  company: string;
  position: string;
  location?: string;
  url?: string;
  application_date: string;
  status: string;
  description?: string;
  notes?: string[];
  created_at: string;
  updated_at?: string;
}

// Type pour les applications groupées par statut
type GroupedApplications = {
  [key: string]: Application[];
};

// Fonction pour normaliser les données de l'API
const normalizeApiData = (apiData: Partial<Application> & { id?: string }): Application => ({
  _id: apiData._id || apiData.id || '',
  user_id: apiData.user_id || '',
  company: apiData.company || '',
  position: apiData.position || '',
  location: apiData.location,
  url: apiData.url,
  application_date: apiData.application_date || '',
  status: apiData.status || '',
  description: apiData.description,
  notes: Array.isArray(apiData.notes) ? apiData.notes : [],
  created_at: apiData.created_at || '',
  updated_at: apiData.updated_at
});

export default function Dashboard() {
  const [applications, setApplications] = useState<Application[]>([]);
  const [selectedApplication, setSelectedApplication] = useState<Application | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const { addNotification } = useNotification();
  const [newNote, setNewNote] = useState<string>('');
  const [isAddingNote, setIsAddingNote] = useState<boolean>(false);
  const [isDeletingNote, setIsDeletingNote] = useState<boolean>(false);
  const [deletingNoteIndex, setDeletingNoteIndex] = useState<number | null>(null);
  // Ajoutez ces états pour gérer l'édition de notes
  const [isEditingNote, setIsEditingNote] = useState<boolean>(false);
  const [editingNoteIndex, setEditingNoteIndex] = useState<number | null>(null);
  const [editedNoteText, setEditedNoteText] = useState<string>('');
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState<boolean>(false);
  const [originalApplication, setOriginalApplication] = useState<Application | null>(null);

  // Fonction réutilisable pour mettre à jour l'application sélectionnée après un rafraîchissement des données
  const updateSelectedApplication = (apps: Application[]) => {
    if (selectedApplication) {
      const updatedApp = apps.find(app => app._id === selectedApplication._id);
      if (updatedApp) {
        setSelectedApplication(updatedApp);
        setOriginalApplication(JSON.parse(JSON.stringify(updatedApp)));
      }
    }
  };

  // Fonction pour récupérer les données depuis l'API
  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      
      // Appel à l'API pour récupérer les candidatures
      const apiData = await applicationApi.getAll();
      
      if (apiData && Array.isArray(apiData)) {
        // Transformer les données de l'API en objets Application
        const transformedData: Application[] = apiData.map(item => 
          normalizeApiData(item as Partial<Application> & { id?: string })
        );
        setApplications(transformedData);
        updateSelectedApplication(transformedData);
        return transformedData; // Retourner les données pour permettre la chaîne de promesses
      } else {
        throw new Error("Format de données invalide retourné par l'API");
      }
    } catch (error) {
      console.error('Erreur lors de la récupération des données:', error);
      setError(error instanceof Error ? error.message : 'Une erreur est survenue lors de la communication avec le serveur');
      return [];
    } finally {
      setLoading(false);
    }
  },[applicationApi, selectedApplication?._id]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    // Fonction pour rafraîchir les données quand une nouvelle candidature est ajoutée
    const handleApplicationCreated = () => {
      fetchData();
    };
    
    // Ajouter l'écouteur d'événement
    window.addEventListener('application-created', handleApplicationCreated);
    
    // Nettoyer l'écouteur lors du démontage du composant
    return () => {
      window.removeEventListener('application-created', handleApplicationCreated);
    };
  }, [fetchData]); // Ajouter fetchData comme dépendance

  const handleCardClick = (application: Application): void => {
    // Ouvrir la sidebar au lieu de la modal d'édition
    setSelectedApplication(application);
    // Conserver une copie de l'application originale pour comparaison/reversion
    setOriginalApplication(JSON.parse(JSON.stringify(application)));
    setHasUnsavedChanges(false);
  };

  const handleBackClick = (): void => {
    // Si des modifications non enregistrées, demander confirmation
    if (hasUnsavedChanges) {
      if (window.confirm("Vous avez des modifications non enregistrées. Êtes-vous sûr de vouloir quitter sans enregistrer ?")) {
        setSelectedApplication(null);
        setHasUnsavedChanges(false);
      }
    } else {
      setSelectedApplication(null);
    }
  };

  // Fonction pour ajouter une note
  const handleAddNote = async () => {
    if (!selectedApplication || !newNote.trim()) return;
    
    try {
      setIsAddingNote(true);
      
      // Appel à l'API pour ajouter une note
      await applicationApi.addNote(selectedApplication._id, newNote);
      
      // Rafraîchir les données pour afficher la nouvelle note
      await fetchData();
      
      // Réinitialiser le formulaire
      setNewNote('');
      
      // Notification de succès
      addNotification('success', 'Note ajoutée avec succès');
      
    } catch (error) {
      console.error('Erreur lors de l\'ajout de la note:', error);
      addNotification('error', 'Erreur lors de l\'ajout de la note');
    } finally {
      setIsAddingNote(false);
    }
  };

  // Ajouter cette fonction pour gérer la suppression d'une note
  const handleDeleteNote = async (noteIndex: number) => {
    if (!selectedApplication) return;
    
    try {
      setIsDeletingNote(true);
      setDeletingNoteIndex(noteIndex);
      
      // Appel à l'API pour supprimer la note
      await applicationApi.deleteNote(selectedApplication._id, noteIndex);
      
      // Rafraîchir les données pour refléter la suppression
      const updatedData = await applicationApi.getAll();
      if (updatedData && Array.isArray(updatedData)) {
        const transformedData = updatedData.map(item => 
          normalizeApiData(item as Partial<Application> & { id?: string })
        );
        setApplications(transformedData);
        
        // Mettre à jour selectedApplication avec la version mise à jour
        const updatedApplication = transformedData.find(app => app._id === selectedApplication._id);
        if (updatedApplication) {
          setSelectedApplication(updatedApplication);
        }
      }
      
      // Notification de succès
      addNotification('success', 'Note supprimée avec succès');
      
    } catch (error) {
      console.error('Erreur lors de la suppression de la note:', error);
      addNotification('error', 'Erreur lors de la suppression de la note');
    } finally {
      setIsDeletingNote(false);
      setDeletingNoteIndex(null);
    }
  };

  // Fonction pour commencer l'édition d'une note
  const handleStartEditNote = (index: number, noteText: string) => {
    setEditingNoteIndex(index);
    setEditedNoteText(noteText);
    setIsEditingNote(true);
  };

  // Fonction pour sauvegarder une note modifiée
  const handleSaveEditNote = async () => {
    if (!selectedApplication || editingNoteIndex === null || !editedNoteText.trim()) return;
    
    try {
      setIsEditingNote(true);
      
      // Créer une copie des notes actuelles
      const updatedNotes = [...(selectedApplication.notes || [])];
      // Mettre à jour la note à l'index spécifié
      updatedNotes[editingNoteIndex] = editedNoteText;
      
      // Appel à l'API pour mettre à jour toutes les notes
      await applicationApi.updateNotes(selectedApplication._id, updatedNotes);
      
      // Rafraîchir les données
      const updatedData = await applicationApi.getAll();
      if (updatedData && Array.isArray(updatedData)) {
        const transformedData = updatedData.map(item => 
          normalizeApiData(item as Partial<Application> & { id?: string })
        );
        setApplications(transformedData);
        
        // Mettre à jour selectedApplication avec la version mise à jour
        const updatedApplication = transformedData.find(app => app._id === selectedApplication._id);
        if (updatedApplication) {
          setSelectedApplication(updatedApplication);
        }
      }
      
      // Notification de succès
      addNotification('success', 'Note modifiée avec succès');
      
      // Réinitialiser l'état d'édition
      setIsEditingNote(false);
      setEditingNoteIndex(null);
      setEditedNoteText('');
      
    } catch (error) {
      console.error('Erreur lors de la modification de la note:', error);
      addNotification('error', 'Erreur lors de la modification de la note');
    } finally {
      setIsEditingNote(false);
    }
  };

  // Fonction pour annuler l'édition d'une note
  const handleCancelEditNote = () => {
    setIsEditingNote(false);
    setEditingNoteIndex(null);
    setEditedNoteText('');
  };

  // Nouvelle fonction pour sauvegarder toutes les modifications
  const handleSaveAllChanges = async () => {
    try {
      // Vérifier si l'application est sélectionnée
      if (!selectedApplication) return;
      
      // Appel à l'API pour mettre à jour l'application
      await applicationApi.update(selectedApplication._id, selectedApplication);
      
      // Rafraîchir les données
      await fetchData();
      
      // Mettre à jour l'application originale
      setOriginalApplication(JSON.parse(JSON.stringify(selectedApplication)));
      
      // Réinitialiser le statut des modifications
      setHasUnsavedChanges(false);
      
      // Notification de succès
      addNotification('success', 'Candidature mise à jour avec succès');
      
    } catch (error) {
      console.error('Erreur lors de la mise à jour de la candidature:', error);
      addNotification('error', 'Erreur lors de la mise à jour de la candidature');
    }
  };

  // Ajoutez une fonction pour annuler les modifications
  const handleCancelChanges = () => {
    if (originalApplication) {
      setSelectedApplication(JSON.parse(JSON.stringify(originalApplication)));
      setHasUnsavedChanges(false);
      addNotification('info', 'Modifications annulées');
    }
  };

  // Ajouter cette fonction de gestion de la suppression

// Fonction pour gérer la suppression d'une candidature
const handleDeleteApplication = async () => {
  if (!selectedApplication) return;
  
  // Demander confirmation avant suppression
  if (!window.confirm('Êtes-vous sûr de vouloir supprimer cette candidature ? Cette action est irréversible.')) {
    return;
  }
  
  try {
    // Appel à l'API pour supprimer la candidature
    await applicationApi.delete(selectedApplication._id);
    
    // Fermer la sidebar
    setSelectedApplication(null);
    
    // Rafraîchir les données pour mettre à jour la liste
    await fetchData();
    
    // Notification de succès
    addNotification('success', 'Candidature supprimée avec succès');
    
  } catch (error) {
    console.error('Erreur lors de la suppression de la candidature:', error);
    addNotification('error', 'Erreur lors de la suppression de la candidature');
  }
};

  // Statuts d'après le backend (classe ApplicationStatus)
  const statusOrder: string[] = [
    "Candidature envoyée", 
    "Entretien", 
    "Offre reçue", 
    "Refusée"
  ];

  // Groupe les applications par statut
  const groupedApplications: GroupedApplications = applications.reduce((acc: GroupedApplications, app) => {
    if (!acc[app.status]) {
      acc[app.status] = [];
    }
    acc[app.status].push(app);
    return acc;
  }, {} as GroupedApplications);

  // Définit les couleurs par statut
  const getStatusColor = (status: string): string => {
    switch (status) {
      case 'Candidature envoyée':
        return 'bg-blue-800';
      case 'Entretien':
        return 'bg-purple-800';
      case 'Offre reçue':
        return 'bg-green-800';
      case 'Refusée':
        return 'bg-red-800';
      default:
        return 'bg-gray-800';
    }
  };

  const getStatusBackgroundColor = (status: string): string => {
    switch (status) {
      case 'À l\'étude':
        return 'bg-amber-900/40';
      case 'Candidature envoyée':
        return 'bg-blue-900/40';
      case 'Entretien':
        return 'bg-purple-900/40';
      case 'Offre reçue':
        return 'bg-green-900/40';
      case 'Refusée':
        return 'bg-red-900/40';
      default:
        return 'bg-gray-800/40';
    }
  };

  // Formater la date
  const formatDate = (dateString: string | undefined): string => {
    if (!dateString) return "Non défini";
    const date = new Date(dateString);
    return date.toLocaleDateString('fr-FR', {
      day: 'numeric',
      month: 'long',
      year: 'numeric'
    });
  };
  // Fonction pour calculer le nombre de jours depuis la candidature
const calculateDays = (dateString: string): number => {
  const now = new Date();
  const applicationDate = new Date(dateString);
  const diffTime = Math.abs(now.getTime() - applicationDate.getTime());
  return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
};

  // Fonction pour calculer la progression en fonction du statut
  const calculateProgress = (status: string): number => {
    switch (status) {
      case 'Candidature envoyée':
        return 25;
      case 'Entretien':
        return 50;
      case 'Offre reçue':
        return 100;
      case 'Refusée':
        return 0;
      default:
        return 0;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900 text-white">
        <p className="text-xl">Chargement des données...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900 text-white">
        <p className="text-xl">Erreur: {error}</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-blue-night text-white p-6">
      <div className="p-6 relative">
        <div className="flex items-center space-x-2 mb-6">
          <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path d="M3.5 18.49l6-6.01 4 4L22 6.92l-1.41-1.41-7.09 7.97-4-4L2 16.99z"/>
          </svg>
          <h1 className="text-2xl font-semibold">Suivi des candidatures</h1>
        </div>

        {/* Affichage des colonnes Kanban */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          {statusOrder.map(status => (
            <div key={status} className="flex flex-col">
              <div className={`${getStatusColor(status)} rounded-md px-3 py-2 mb-4 text-white font-medium`}>
                {status}
              </div>
              <div className="space-y-4 max-h-[calc(100vh-180px)] overflow-y-auto pr-1">
                {groupedApplications[status]?.map(app => (
                  <div 
                    key={app._id} 
                    className={`${getStatusBackgroundColor(status)} rounded-md p-4 cursor-pointer hover:bg-opacity-80 transition-all`}
                    onClick={() => handleCardClick(app)}
                  >
                    <div className="flex items-center mb-2">
                      <div className="w-8 h-8 rounded-full bg-gray-600 flex items-center justify-center mr-2">
                        {app.company.charAt(0)}
                      </div>
                      <div>
                        <h3 className="font-semibold">{app.position}</h3>
                        <p className="text-sm text-gray-300">{app.company}</p>
                      </div>
                    </div>
                    <div className="mb-2">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm">{calculateProgress(app.status)} %</span>
                      </div>
                      <div className="w-full bg-gray-700 rounded-full h-1.5">
                        <div 
                          className="bg-green-500 h-1.5 rounded-full" 
                          style={{ width: `${calculateProgress(app.status)}%` }}
                        ></div>
                      </div>
                    </div>
                    <div className="text-sm text-gray-400">{calculateDays(app.application_date)} jours</div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Affichage des détails d'une candidature en sidebar */}
        {selectedApplication && (
          <div className="fixed inset-0 z-40 pointer-events-none">
            <div className="absolute inset-0 bg-black/50 pointer-events-auto" onClick={handleBackClick}></div>
            
            <div 
              className="absolute right-0 top-[64px] h-[calc(100vh-64px)] w-full max-w-md bg-blue-night-lighter shadow-xl transform transition-transform duration-300 ease-in-out overflow-y-auto pointer-events-auto"
              style={{ boxShadow: "-5px 0 25px rgba(0, 0, 0, 0.3)" }}
            >
              <div className="p-6">
                <div className="flex items-center justify-between mb-6">
                  <button
                    className="flex items-center text-gray-400 hover:text-white"
                    onClick={handleBackClick}
                  > 
                    <svg className="w-5 h-5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7-7 7M3 12h18"></path>
                    </svg>
                    Fermer
                  </button>
                  <button className="text-gray-400 hover:text-white">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 12h.01M12 12h.01M19 12h.01M6 12a1 1 0 11-2 0 1 1 0 012 0zm7 0a1 1 0 11-2 0 1 1 0 012 0zm7 0a1 1 0 11-2 0 1 1 0 012 0z"></path>
                    </svg>
                  </button>
                </div>

                <div className="flex items-center mb-6">
                  <div className="w-12 h-12 rounded-full bg-gray-600 flex items-center justify-center mr-4">
                    {selectedApplication.company.charAt(0)}
                  </div>
                  <div className="flex-grow">
                    <input 
                      type="text"
                      value={selectedApplication.position}
                      onChange={(e) => {
                        // Création d'une copie mise à jour de l'application
                        const updatedApp = { ...selectedApplication, position: e.target.value };
                        setSelectedApplication(updatedApp);
                        setHasUnsavedChanges(true);
                      }}
                      className="w-full text-xl font-bold bg-transparent border-b border-transparent hover:border-gray-600 focus:border-blue-500 focus:outline-none"
                    />
                  </div>
                </div>

                <input 
                  type="text"
                  value={selectedApplication.company}
                  onChange={(e) => {
                    const updatedApp = { ...selectedApplication, company: e.target.value };
                    setSelectedApplication(updatedApp);
                    setHasUnsavedChanges(true);
                  }}
                  className="text-gray-300 mb-6 w-full bg-transparent border-b border-transparent hover:border-gray-600 focus:border-blue-500 focus:outline-none"
                />

                {/* Ajoutez un sélecteur pour le statut */}
                <div className="mb-6">
                  <select
                    value={selectedApplication.status}
                    onChange={(e) => {
                      const updatedApp = { ...selectedApplication, status: e.target.value };
                      setSelectedApplication(updatedApp);
                      setHasUnsavedChanges(true);
                    }}
                    className={`${getStatusColor(selectedApplication.status)} px-3 py-1 rounded-md text-white font-medium bg-opacity-80 cursor-pointer`}
                  >
                    <option value="Candidature envoyée">Candidature envoyée</option>
                    <option value="Entretien">Entretien</option>
                    <option value="Offre reçue">Offre reçue</option>
                    <option value="Refusée">Refusée</option>
                  </select>
                </div>

                <div className="mb-6">
                  <p className="text-gray-400 mb-2 flex items-center">
                    <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h7"></path>
                    </svg>
                    Description
                  </p>
                  <textarea
                    value={selectedApplication.description || ''}
                    onChange={(e) => {
                      const updatedApp = { ...selectedApplication, description: e.target.value };
                      setSelectedApplication(updatedApp);
                      setHasUnsavedChanges(true);
                    }}
                    placeholder="Ajoutez une description..."
                    className="w-full px-3 py-2 rounded-md bg-blue-night border border-gray-700 focus:border-blue-500 focus:outline-none text-white"
                    rows={4}
                  />
                </div>

                <div className="border-t border-gray-700 py-4">
                  <h3 className="text-lg font-semibold mb-4">Notes</h3>
                  {selectedApplication.notes?.length ? (
                    selectedApplication.notes.map((note, index) => (
                      <div key={index} className="mb-3 p-3 bg-blue-night-light rounded-md relative group">
                        {isEditingNote && editingNoteIndex === index ? (
                          <div>
                            <textarea
                              value={editedNoteText}
                              onChange={(e) => setEditedNoteText(e.target.value)}
                              className="w-full px-2 py-1 rounded-md bg-blue-night border border-gray-700 focus:border-blue-500 focus:outline-none text-white"
                              rows={3}
                            />
                            <div className="flex justify-end mt-2 space-x-2">
                              <button
                                onClick={handleCancelEditNote}
                                className="px-2 py-1 bg-gray-700 hover:bg-gray-600 rounded-md text-sm"
                              >
                                Annuler
                              </button>
                              <button
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
                            <p className="text-gray-300 pr-8">{note}</p>
                            <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity flex space-x-1">
                              <button 
                                onClick={() => handleStartEditNote(index, note)}
                                className="p-1 rounded-full text-gray-400 hover:text-blue-400 hover:bg-blue-900/30"
                              >
                                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"></path>
                                </svg>
                              </button>
                              
                              <button 
                                onClick={() => handleDeleteNote(index)}
                                disabled={isDeletingNote && deletingNoteIndex === index}
                                className={`p-1 rounded-full ${
                                  isDeletingNote && deletingNoteIndex === index ? 'text-gray-500' : 'text-gray-400 hover:text-red-400 hover:bg-red-900/30'
                                }`}
                              >
                                {isDeletingNote && deletingNoteIndex === index ? (
                                  <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                  </svg>
                                ) : (
                                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                                  </svg>
                                )}
                              </button>
                            </div>
                          </>
                        )}
                      </div>
                    ))
                  ) : (
                    <p className="text-gray-400 italic mb-4">Aucune note pour cette candidature</p>
                  )}
                  
                  <div className="mt-3">
                    <textarea
                      value={newNote}
                      onChange={(e) => setNewNote(e.target.value)}
                      placeholder="Ajouter une nouvelle note..."
                      className="w-full px-3 py-2 rounded-md bg-blue-night border border-gray-700 focus:border-blue-500 focus:outline-none text-white"
                      rows={2}
                    />
                    <div className="flex justify-end mt-2">
                    <button
                      onClick={handleAddNote}
                      disabled={!newNote.trim() || isAddingNote}
                      className={`px-3 py-1 rounded-md flex items-center text-white ${
                        !newNote.trim() || isAddingNote ? 'bg-gray-600 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-500'
                      }`}
                    >
                      {isAddingNote ? (
                        <>
                          <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                          </svg>
                          Ajout...
                        </>
                      ) : (
                        <>
                          <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path>
                          </svg>
                          Ajouter
                        </>
                      )}
                    </button>
                    </div>
                  </div>
                </div>

                <div className="border-t border-gray-700 py-4">
                  <h3 className="text-lg font-semibold mb-4">Statistiques</h3>
                  
                  <div className="space-y-4">
                    <div className="flex justify-between items-center">
                      <p className="text-gray-400 flex items-center">
                        <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path>
                        </svg>
                        Jours depuis la candidature
                      </p>
                      <p className="font-medium">{calculateDays(selectedApplication.application_date)}</p>
                    </div>
                    <div className="flex justify-between items-center">
                      <p className="text-gray-400 flex items-center">
                        <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                        </svg>
                        Dernière modification
                      </p>
                      <p className="font-medium">{formatDate(selectedApplication.updated_at)}</p>
                    </div>
                    <div className="flex justify-between items-center">
                      <p className="text-gray-400 flex items-center">
                        <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path>
                        </svg>
                        Date de création
                      </p>
                      <p className="font-medium">{formatDate(selectedApplication.created_at)}</p>
                    </div>
                  </div>
                </div>

                <div className="border-t border-gray-700 pt-6 mt-4">
                  <div className="flex justify-between space-x-3">
                    <button 
                      className="w-1/2 px-4 py-2 bg-gray-600 hover:bg-gray-700 rounded-md transition-colors"
                      onClick={handleCancelChanges}
                      disabled={!hasUnsavedChanges}
                    >
                      Annuler
                    </button>
                    <button 
                      className={`w-1/2 px-4 py-2 rounded-md transition-colors ${
                        hasUnsavedChanges 
                          ? 'bg-blue-600 hover:bg-blue-700 text-white' 
                          : 'bg-gray-600 text-gray-300 cursor-not-allowed'
                      }`}
                      onClick={handleSaveAllChanges}
                      disabled={!hasUnsavedChanges}
                    >
                      Enregistrer
                    </button>
                  </div>
                </div>
                
                {/* Bouton de suppression séparé */}
                <div className="mt-4">
                  <button 
                    onClick={handleDeleteApplication}
                    className="w-full px-4 py-2 bg-red-600 hover:bg-red-700 rounded-md transition-colors flex items-center justify-center"
                  >
                    <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                    </svg>
                    Supprimer cette candidature
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}