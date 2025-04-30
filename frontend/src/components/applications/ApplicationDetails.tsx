import React from 'react';
import { Application, formatDate, 
    calculateDays } from '@/types/application'

import ApplicationNotes from './ApplicationNotes';
import StatusSelect from './StatusSelect';
import { FiExternalLink } from 'react-icons/fi';

interface ApplicationDetailsProps {
  application: Application | null;
  originalApplication: Application | null;
  onClose: () => void;
  onChange: (field: string, value: string) => void;
  onSave: () => Promise<void>;
  onCancel: () => void;
  onDelete: () => Promise<void>;
  onArchive: () => Promise<void>; // Ajouter cette prop
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
  onAddNote,
  onEditNote,
  onDeleteNote,
  hasUnsavedChanges,
  isAddingNote,
  isDeletingNote,
  deletingNoteIndex
}: ApplicationDetailsProps) {
  if (!application) return null;
  
  const handleStatusChange = (newStatus: string) => {
    onChange('status', newStatus);
  };

  return (
    <div className="fixed inset-0 z-40 pointer-events-none">
      <div className="absolute inset-0 bg-black/50 pointer-events-auto" onClick={onClose}></div>
      
      <div 
        className="absolute right-0 top-[64px] h-[calc(100vh-64px)] w-full max-w-md bg-blue-night-lighter shadow-xl transform transition-transform duration-300 ease-in-out overflow-y-auto pointer-events-auto"
        style={{ boxShadow: "-5px 0 25px rgba(0, 0, 0, 0.3)" }}
      >
        <div className="p-6">
          <div className="flex items-center justify-between mb-6">
            <button
              className="flex items-center text-gray-400 hover:text-white"
              onClick={onClose}
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
              {application.company.charAt(0)}
            </div>
            <div className="flex-grow">
              <input 
                type="text"
                value={application.position}
                onChange={(e) => onChange('position', e.target.value)}
                className="w-full text-xl font-bold bg-transparent border-b border-transparent hover:border-gray-600 focus:border-blue-500 focus:outline-none"
              />
            </div>
          </div>

          <input 
            type="text"
            value={application.company}
            onChange={(e) => onChange('company', e.target.value)}
            className="text-gray-300 mb-6 w-full bg-transparent border-b border-transparent hover:border-gray-600 focus:border-blue-500 focus:outline-none"
          />
          <div className="mb-6 flex items-center">
          <input 
            type="text"
            value={application.url}
            onChange={(e) => onChange('url', e.target.value)}
            placeholder="Lien de l'offre"
            className="flex-1 text-gray-300 bg-transparent border-b border-transparent hover:border-gray-600 focus:border-blue-500 focus:outline-none"
          />
          {application.url && (
            <a
              href={application.url}
              target="_blank"
              rel="noopener noreferrer"
              className="ml-3 text-gray-400 hover:text-white transition-colors"
            >
              <FiExternalLink size={20} />
            </a>
          )}
        </div>
          {/* Ajoutez un sélecteur pour le statut */}
          <div className="mb-6">
            <StatusSelect 
              currentStatus={application.status} 
              onChange={handleStatusChange} 
            />
          </div>

          <div className="mb-6">
            <p className="text-gray-400 mb-2 flex items-center">
              <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h7"></path>
              </svg>
              Description
            </p>
            <textarea
              value={application.description || ''}
              onChange={(e) => onChange('description', e.target.value)}
              placeholder="Ajoutez une description..."
              className="w-full px-3 py-2 rounded-md bg-blue-night border border-gray-700 focus:border-blue-500 focus:outline-none text-white"
              rows={4}
            />
          </div>

          <ApplicationNotes 
            notes={application.notes || []}
            onAddNote={onAddNote}
            onEditNote={onEditNote}
            onDeleteNote={onDeleteNote}
            isAddingNote={isAddingNote}
            isDeletingNote={isDeletingNote}
            deletingNoteIndex={deletingNoteIndex}
          />

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
                <p className="font-medium">{calculateDays(application.application_date)}</p>
              </div>
              <div className="flex justify-between items-center">
                <p className="text-gray-400 flex items-center">
                  <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                  </svg>
                  Dernière modification
                </p>
                <p className="font-medium">{formatDate(application.updated_at)}</p>
              </div>
              <div className="flex justify-between items-center">
                <p className="text-gray-400 flex items-center">
                  <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path>
                  </svg>
                  Date de candidature
                </p>
                <p className="font-medium">{formatDate(application.application_date)}</p>
              </div>
            </div>
          </div>

          <div className="border-t border-gray-700 pt-6 mt-4">
            {/* Bouton d'archivage */}
            <button 
              onClick={onArchive}
              className="w-full px-4 py-2 bg-gray-600 hover:bg-gray-700 rounded-md transition-colors flex items-center justify-center mb-4"
            >
              <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4"></path>
              </svg>
              Archiver cette candidature
            </button>
            
            {/* Boutons d'enregistrement existants */}
            <div className="flex justify-between space-x-3">
              <button 
                className="w-1/2 px-4 py-2 bg-gray-600 hover:bg-gray-700 rounded-md transition-colors"
                onClick={onCancel}
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
                onClick={onSave}
                disabled={!hasUnsavedChanges}
              >
                Enregistrer
              </button>
            </div>
            
            {/* Bouton de suppression existant */}
            <div className="mt-4">
              <button 
                onClick={onDelete}
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
    </div>
  );
}