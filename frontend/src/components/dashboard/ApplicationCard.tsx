'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { FiEdit2, FiExternalLink, FiMoreVertical, FiTrash2 } from 'react-icons/fi';

interface Application {
  id: string;
  company: string;
  position: string;
  status: string;
  application_date: string;
  location?: string;
  description?: string;
  url?: string;
}

interface ApplicationCardProps {
  application: Application;
  onUpdate: () => void;
}

export default function ApplicationCard({ application, onUpdate }: ApplicationCardProps) {
  const router = useRouter();
  const [showMenu, setShowMenu] = useState(false);
  
  // Get color based on status
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'Candidature envoyée':
        return 'bg-blue-100 text-blue-800';
      case 'Première sélection':
        return 'bg-purple-100 text-purple-800';
      case 'Entretien':
        return 'bg-yellow-100 text-yellow-800';
      case 'Test technique':
        return 'bg-orange-100 text-orange-800';
      case 'Négociation':
        return 'bg-pink-100 text-pink-800';
      case 'Offre reçue':
        return 'bg-green-100 text-green-800';
      case 'Offre acceptée':
        return 'bg-green-100 text-green-800';
      case 'Refusée':
        return 'bg-red-100 text-red-800';
      case 'Retirée':
        return 'bg-gray-100 text-gray-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };
  
  // Format date
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('fr-FR', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    }).format(date);
  };
  
  const handleDelete = async () => {
    if (!confirm('Êtes-vous sûr de vouloir supprimer cette candidature ?')) {
      return;
    }
    
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`http://localhost:8000/applications/${application.id}`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      
      if (!response.ok) {
        throw new Error('Failed to delete application');
      }
      
      onUpdate();
    } catch (error) {
      console.error('Error deleting application:', error);
    }
  };
  
  return (
    <div className="bg-white rounded-lg shadow-md overflow-hidden hover:shadow-lg transition-shadow">
      <div className="p-5">
        <div className="flex justify-between items-start mb-3">
          <h3 className="font-bold text-lg text-gray-800 truncate">{application.company}</h3>
          
          <div className="relative">
            <button 
              onClick={() => setShowMenu(!showMenu)}
              className="p-1 rounded-full hover:bg-gray-100"
            >
              <FiMoreVertical className="text-gray-600" />
            </button>
            
            {showMenu && (
              <div className="absolute right-0 mt-2 w-48 bg-white rounded-md shadow-lg z-10">
                <div className="py-1">
                  <button
                    onClick={() => {
                      router.push(`/dashboard/edit/${application.id}`);
                      setShowMenu(false);
                    }}
                    className="flex items-center px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 w-full text-left"
                  >
                    <FiEdit2 className="mr-2" />
                    Modifier
                  </button>
                  
                  <button
                    onClick={() => {
                      handleDelete();
                      setShowMenu(false);
                    }}
                    className="flex items-center px-4 py-2 text-sm text-red-600 hover:bg-gray-100 w-full text-left"
                  >
                    <FiTrash2 className="mr-2" />
                    Supprimer
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
        
        <p className="text-gray-600 mb-2">{application.position}</p>
        
        {application.location && (
          <p className="text-gray-500 text-sm mb-2">{application.location}</p>
        )}
        
        <div className="flex justify-between items-center mb-3">
          <span className="text-sm text-gray-500">
            Postuler le {formatDate(application.application_date)}
          </span>
        </div>
        
        <div className="flex justify-between items-center">
          <span className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(application.status)}`}>
            {application.status}
          </span>
          
          {application.url && (
            <a 
              href={application.url} 
              target="_blank" 
              rel="noopener noreferrer"
              className="text-primary-600 hover:text-primary-800"
            >
              <FiExternalLink />
            </a>
          )}
        </div>
      </div>
    </div>
  );
}