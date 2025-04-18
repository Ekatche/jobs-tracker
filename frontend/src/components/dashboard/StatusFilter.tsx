'use client';

import { useState } from 'react';
import { FiFilter } from 'react-icons/fi';

// Liste des statuts disponibles
const statusOptions = [
  "En étude",
  'Candidature envoyée',
  'Première sélection',
  'Entretien',
  'Test technique',
  'Négociation',
  'Offre reçue',
  'Offre acceptée',
  'Refusée',
  'Retirée'
];

interface StatusFilterProps {
  activeFilter: string | null;
  onFilterChange: (status: string | null) => void;
}

export default function StatusFilter({ activeFilter, onFilterChange }: StatusFilterProps) {
  const [isOpen, setIsOpen] = useState(false);

  // Fonction pour obtenir la couleur basée sur le statut
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'Candidature envoyée':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'Première sélection':
        return 'bg-purple-100 text-purple-800 border-purple-200';
      case 'Entretien':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'Test technique':
        return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'Négociation':
        return 'bg-pink-100 text-pink-800 border-pink-200';
      case 'Offre reçue':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'Offre acceptée':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'Refusée':
        return 'bg-red-100 text-red-800 border-red-200';
      case 'Retirée':
        return 'bg-gray-100 text-gray-800 border-gray-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  return (
    <div className="relative">
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
        >
          <FiFilter />
          Filtrer par statut
        </button>
        
        {activeFilter && (
          <div className="flex items-center">
            <span className={`px-3 py-1 text-sm rounded-full ${getStatusColor(activeFilter)}`}>
              {activeFilter}
            </span>
            <button
              onClick={() => onFilterChange(null)}
              className="ml-2 text-sm text-gray-500 hover:text-gray-700"
            >
              × Effacer
            </button>
          </div>
        )}
      </div>

      {isOpen && (
        <div className="absolute left-0 z-10 mt-2 bg-white border border-gray-200 rounded-md shadow-lg w-64">
          <div className="py-1">
            {statusOptions.map((status) => (
              <button
                key={status}
                onClick={() => {
                  onFilterChange(status);
                  setIsOpen(false);
                }}
                className={`flex items-center w-full px-4 py-2 text-left text-sm hover:bg-gray-50 ${
                  activeFilter === status ? 'bg-gray-100' : ''
                }`}
              >
                <span className={`w-3 h-3 rounded-full mr-2 ${getStatusColor(status)}`}></span>
                {status}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}