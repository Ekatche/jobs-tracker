"use client";

import { useState, useEffect, useCallback } from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts';
import { applicationApi } from '@/lib/api';
import EditApplicationModal from '@/components/applications/EditApplicationModal';

// Une seule interface pour représenter une candidature
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

// Interface pour les données de statut
interface StatusData {
  name: string;
  value: number;
  color: string;
}

// Interface pour les données de position
interface PositionData {
  name: string;
  value: number;
}

export default function ApplicationsPage() {
  // États avec types corrects
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [statusData, setStatusData] = useState<StatusData[]>([]);
  const [positionData, setPositionData] = useState<PositionData[]>([]);
  
  // État pour la pagination
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [itemsPerPage, setItemsPerPage] = useState<number>(5);

  // États pour gérer la modal
  const [isEditModalOpen, setIsEditModalOpen] = useState<boolean>(false);
  const [applicationToEdit, setApplicationToEdit] = useState<Application | null>(null);

  // Ajouter cet état avec les autres
  const [searchTerm, setSearchTerm] = useState<string>('');

  // Statuts basés sur le backend
  const statusColors: Record<string, string> = {
    "En étude": "#F9A03F",
    "Candidature envoyée": "#4A90E2",
    "Première sélection": "#6E90DB",
    "Entretien": "#9C5AC7",
    "Test technique": "#C75A99",
    "Négociation": "#C7935A",
    "Offre reçue": "#67C779",
    "Offre acceptée": "#4AB060",
    "Refusée": "#E27A7A",
    "Retirée": "#888888"
  };

  /// Fonction pour normaliser les données de l'API en utilisant Partial<Application>
  const normalizeApiData = (apiData: Partial<Application> & { id?: string }): Application => ({
    _id: apiData._id || apiData.id || '',
    user_id: apiData.user_id || '',
    company: apiData.company || '',
    position: apiData.position || '',
    location: apiData.location || '', // Conversion explicite pour éviter undefined
    url: apiData.url,
    application_date: apiData.application_date || '',
    status: apiData.status || '',
    description: apiData.description,
    notes: Array.isArray(apiData.notes) ? apiData.notes : [],
    created_at: apiData.created_at || '',
    updated_at: apiData.updated_at
  });

  // Définir fetchData en dehors des useEffect, ou utiliser useCallback
  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      
      // Appel à l'API pour récupérer les candidatures
      const apiData = await applicationApi.getAll();
      console.log("Données brutes de l'API:", apiData);
      
      if (apiData && Array.isArray(apiData)) {
        // Normaliser les données de l'API
        const applicationsData = apiData.map(item => 
          normalizeApiData(item as Partial<Application> & { id?: string })
        );
        
        setApplications(applicationsData);
        
        // On ne définit plus setTotalPages ici car totalPages est calculé dynamiquement
        // en fonction des applications filtrées
        
        // Traitement des données pour les graphiques
        processDataForCharts(applicationsData);
      } else {
        throw new Error("Format de données invalide retourné par l'API");
      }
    } catch (error) {
      // Gestion des erreurs...
      console.error("Erreur lors du chargement des données:", error);
      setError("Impossible de charger les candidatures. Veuillez réessayer plus tard.");
    } finally {
      setLoading(false);
    }
  }, [itemsPerPage]); // inclure toutes les dépendances nécessaires

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

  // Fonction pour traiter les données pour les graphiques
  const processDataForCharts = (data: Application[]) => {
    // Calculer la distribution par statut
    const statusCounts: Record<string, number> = {};
    data.forEach(app => {
      statusCounts[app.status] = (statusCounts[app.status] || 0) + 1;
    });

    const statusChartData = Object.keys(statusCounts).map(status => ({
      name: status,
      value: statusCounts[status],
      color: statusColors[status] || "#CCCCCC"
    }));
    setStatusData(statusChartData);

    // Calculer la distribution par intitulé de poste exact
    const positionCounts: Record<string, number> = {};
    data.forEach(app => {
      positionCounts[app.position] = (positionCounts[app.position] || 0) + 1;
    });

    // Trier par nombre d'occurrences et prendre les 10 plus fréquents
    const positionChartData = Object.keys(positionCounts)
      .sort((a, b) => positionCounts[b] - positionCounts[a])
      .slice(0, 10) // Limiter aux 10 postes les plus fréquents pour la lisibilité
      .map(position => ({
        name: position,
        value: positionCounts[position]
      }));
    
    setPositionData(positionChartData);
  };

  // Calculer le nombre total de pages basé sur les applications filtrées
  const getFilteredApplications = () => {
    if (!searchTerm) return applications;
    
    return applications.filter(app => {
      const searchLower = searchTerm.toLowerCase();
      return (
        app.company.toLowerCase().includes(searchLower) ||
        app.position.toLowerCase().includes(searchLower) ||
        app.status.toLowerCase().includes(searchLower) ||
        (app.location && app.location.toLowerCase().includes(searchLower))
      );
    });
  };

  // Utiliser cette fonction dans le rendu pour calculer la pagination
  const filteredApplications = getFilteredApplications();
  const totalPages = Math.ceil(filteredApplications.length / itemsPerPage);

  // Obtenir les éléments de la page courante
  const getCurrentItems = () => {
    // Utiliser directement les applications filtrées
    const indexOfLastItem = currentPage * itemsPerPage;
    const indexOfFirstItem = indexOfLastItem - itemsPerPage;
    return filteredApplications.slice(indexOfFirstItem, indexOfLastItem);
  };

  // Fonction pour changer de page
  const paginate = (pageNumber: number) => setCurrentPage(pageNumber);

  // Fonction pour obtenir la couleur du statut
  const getStatusColor = (status: string): string => {
    const baseColor = statusColors[status] || "#CCCCCC";
    return baseColor.replace("#", "bg-[#") + "]";
  };

  // Fonction pour mettre en forme la date
  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('fr-FR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    }).format(date);
  };

  // Fonction pour calculer le temps écoulé depuis la candidature
  const getDaysSinceApplication = (dateString: string): string => {
    const applicationDate = new Date(dateString);
    const now = new Date();
    const diffTime = Math.abs(now.getTime() - applicationDate.getTime());
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    return diffDays === 1 ? "1 jour" : `${diffDays} jours`;
  };

  // Amélioration de la fonction getLocationColor pour toujours retourner une couleur valide
  const getLocationColor = (location: string): string => {
    if (!location || location.trim() === '') return "bg-gray-500";
    
    const lowerLocation = location.toLowerCase();
    
    if (lowerLocation.includes('remote') || lowerLocation.includes('télétravail')) {
      return "bg-green-600";
    } else if (lowerLocation.includes('france') || lowerLocation.includes('paris')) {
      return "bg-blue-600";
    } else if (
      lowerLocation.includes('lyon') || 
      lowerLocation.includes('marseille') || 
      lowerLocation.includes('bordeaux') ||
      lowerLocation.includes('lille') ||
      lowerLocation.includes('toulouse') ||
      lowerLocation.includes('nantes') ||
      lowerLocation.includes('strasbourg')
    ) {
      return "bg-indigo-600";
    } else if (lowerLocation.includes('étranger')) {
      return "bg-violet-600";
    } else {
      // Couleur par défaut pour TOUTES les autres localisations
      return "bg-purple-600";
    }
  };

  // Fonction pour gérer le clic sur une ligne du tableau
  const handleRowClick = (application: Application) => {
    setApplicationToEdit(application);
    setIsEditModalOpen(true);
  };

  // Fonction pour gérer le succès après modification
  const handleEditSuccess = async () => {
    // Rafraîchir les données après modification
    try {
      setLoading(true);
      const apiData = await applicationApi.getAll();
      
      if (apiData && Array.isArray(apiData)) {
        const applicationsData = apiData.map(item => 
          normalizeApiData(item as Partial<Application> & { id?: string })
        );
        
        setApplications(applicationsData);
        // Ne pas utiliser setTotalPages ici
        processDataForCharts(applicationsData);
      }
    } catch (error) {
      console.error("Erreur lors du rafraîchissement des données:", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-blue-night text-white">
        <p className="text-xl">Chargement des données...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-blue-night text-white">
        <p className="text-xl text-red-500">Erreur: {error}</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-blue-night text-white p-6">
      <div className="max-w-7xl mx-auto">
        <div className="grid grid-cols-1 gap-6 mb-6">
          {/* Tableau des offres d'emploi */}
          <div className="bg-blue-night-lighter rounded-lg shadow-lg overflow-hidden">
            <div className="p-4 border-b border-gray-700 flex justify-between items-center">
              <div className="flex items-center space-x-2">
                <svg className="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path>
                </svg>
                <h2 className="text-xl font-semibold">Mes candidatures</h2>
              </div>

              {/* Champ de recherche */}
              <div className="relative">
                <input
                  type="text"
                  placeholder="Rechercher..."
                  value={searchTerm}
                  onChange={(e) => {
                    setSearchTerm(e.target.value);
                    setCurrentPage(1); // Retour à la première page lors d'une recherche
                  }}
                  className="px-3 py-2 pl-10 bg-blue-night border border-gray-700 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-white"
                />
                <svg 
                  className="w-5 h-5 text-gray-400 absolute left-3 top-1/2 transform -translate-y-1/2" 
                  fill="none" 
                  stroke="currentColor" 
                  viewBox="0 0 24 24" 
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
                </svg>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left bg-blue-night-lighter">
                    <th className="p-4 font-medium text-gray-400">Entreprise</th>
                    <th className="p-4 font-medium text-gray-400">Poste</th>
                    <th className="p-4 font-medium text-gray-400">Statut</th>
                    <th className="p-4 font-medium text-gray-400">Localisation</th>
                    <th className="p-4 font-medium text-gray-400">URL</th>
                    <th className="p-4 font-medium text-gray-400">Date de candidature</th>
                  </tr>
                </thead>
                <tbody>
                  {getCurrentItems().map((app) => (
                    <tr 
                      key={app._id} 
                      className="border-t border-gray-700 hover:bg-blue-night-light cursor-pointer" 
                      onClick={() => handleRowClick(app)}
                    >
                      <td className="p-4">
                        <div className="flex items-center">
                          <div className="w-8 h-8 flex items-center justify-center rounded-full bg-blue-900/40 text-white font-medium mr-2">
                            {app.company.charAt(0)}
                          </div>
                          {app.company}
                        </div>
                      </td>
                      <td className="p-4">{app.position}</td>
                      <td className="p-4">
                        <div className="flex items-center">
                          <div className={`w-3 h-3 rounded-full mr-2 ${getStatusColor(app.status)}`}></div>
                          {app.status}
                        </div>
                      </td>
                      <td className="p-4">
                        {app.location && app.location.trim() !== '' ? (
                          <span className={`px-3 py-1 text-sm rounded-full text-white ${getLocationColor(app.location)}`}>
                            {app.location}
                          </span>
                        ) : (
                          <span className="text-gray-500">Non spécifiée</span>
                        )}
                      </td>
                      <td className="p-4">
                        {app.url && (
                          <a 
                            href={app.url} 
                            target="_blank" 
                            rel="noopener noreferrer" 
                            className="text-blue-400 hover:underline"
                            onClick={(e) => e.stopPropagation()} // Empêche le déclenchement du handleRowClick
                          >
                            <svg className="w-5 h-5 inline-block" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path>
                            </svg>
                          </a>
                        )}
                      </td>
                      <td className="p-4">
                        <div>
                          {formatDate(app.application_date)}
                          <div className="text-xs text-gray-400">
                            {getDaysSinceApplication(app.application_date)}
                          </div>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="p-4 border-t border-gray-700 flex justify-between items-center">
                <span className="text-sm text-gray-400">
                  Affichage de {filteredApplications.length > 0 ? Math.min((currentPage - 1) * itemsPerPage + 1, filteredApplications.length) : 0} à {Math.min(currentPage * itemsPerPage, filteredApplications.length)} sur {filteredApplications.length} candidatures
                  {applications.length !== filteredApplications.length && (
                    <span className="ml-1">
                      (filtrées sur {applications.length} au total)
                    </span>
                  )}
                </span>
                <div className="flex space-x-2">
                  <button 
                    onClick={() => paginate(currentPage - 1)} 
                    disabled={currentPage === 1}
                    className={`px-3 py-1 rounded ${currentPage === 1 ? 'bg-gray-800 text-gray-500' : 'bg-blue-900 text-white hover:bg-blue-800'}`}
                  >
                    Précédent
                  </button>
                  {Array.from({ length: totalPages }, (_, i) => i + 1).map(number => (
                    <button
                      key={number}
                      onClick={() => paginate(number)}
                      className={`px-3 py-1 rounded ${currentPage === number ? 'bg-blue-600' : 'bg-blue-900 hover:bg-blue-800'}`}
                    >
                      {number}
                    </button>
                  ))}
                  <button 
                    onClick={() => paginate(currentPage + 1)} 
                    disabled={currentPage === totalPages}
                    className={`px-3 py-1 rounded ${currentPage === totalPages ? 'bg-gray-800 text-gray-500' : 'bg-blue-900 text-white hover:bg-blue-800'}`}
                  >
                    Suivant
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Graphiques */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Graphique de répartition par statut */}
          <div className="bg-blue-night-lighter rounded-lg shadow-lg p-6">
            <div className="flex items-center space-x-2 mb-6">
              <svg className="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 3.055A9.001 9.001 9.001 0 1020.945 13H11V3.055z"></path>
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z"></path>
              </svg>
              <h2 className="text-xl font-semibold">Répartition par statut</h2>
            </div>
            
            <div className="h-64 mb-6">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={statusData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={80}
                    paddingAngle={2}
                    dataKey="value"
                    labelLine={false} // Gardez ceci pour éviter les lignes de connexion
                  >
                    {statusData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip 
                    content={({ active, payload }) => {
                      if (active && payload && payload.length) {
                        const data = payload[0].payload;
                        return (
                          <div className="bg-blue-night-light p-2 rounded border border-gray-700 shadow-lg">
                            <p className="font-semibold text-white">{data.name}</p>
                            <p className="text-sm text-gray-300">
                              {data.value} candidature{data.value > 1 ? 's' : ''}
                              <span className="ml-1 text-gray-400">
                                ({((data.value / applications.length) * 100).toFixed(1)}%)
                              </span>
                            </p>
                          </div>
                        );
                      }
                      return null;
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>

            <div className="text-center mb-6">
              <div className="text-4xl font-bold">{applications.length}</div>
              <div className="text-sm text-gray-400">Candidatures totales</div>
            </div>

            {/* Légende améliorée avec pourcentages */}
            <div className="grid grid-cols-2 gap-2">
              {statusData.map((status, index) => {
                // Calculer le pourcentage pour chaque statut
                const percentage = applications.length > 0 
                  ? ((status.value / applications.length) * 100).toFixed(1) 
                  : '0';
                
                return (
                  <div key={index} className="flex items-center space-x-2">
                    <div className="w-3 h-3 rounded-full" style={{ backgroundColor: status.color }}></div>
                    <span className="text-sm">
                      {status.name} ({status.value} - {percentage}%)
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Graphique des types de postes */}
          <div className="bg-blue-night-lighter rounded-lg shadow-lg p-6">
            <div className="flex items-center space-x-2 mb-6">
              <svg className="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
              </svg>
              <h2 className="text-xl font-semibold">Types de postes</h2>
            </div>
            
            {/* Conteneur avec défilement pour le graphique */}
            <div className="h-80 overflow-y-auto pr-2 custom-scrollbar">
              <div style={{ height: `${Math.max(250, positionData.length * 40)}px` }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={positionData}
                    layout="vertical"
                    margin={{ top: 5, right: 30, left: 120, bottom: 5 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#444" />
                    <XAxis type="number" stroke="#888" />
                    <YAxis 
                      type="category" 
                      dataKey="name" 
                      stroke="#888" 
                      width={120} 
                      tick={{ fontSize: 12 }}
                      tickFormatter={(value) => value.length > 18 ? `${value.substring(0, 18)}...` : value}
                    />
                    <Tooltip 
                      content={({ active, payload }) => {
                        if (active && payload && payload.length) {
                          const data = payload[0].payload;
                          return (
                            <div className="bg-blue-night-light p-2 rounded border border-gray-700 shadow-lg">
                              <p className="font-semibold text-white">{data.name}</p>
                              <p className="text-sm text-gray-300">
                                {data.value} candidature{data.value > 1 ? 's' : ''}
                              </p>
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <Bar dataKey="value" fill="#4A90E2" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="text-center mt-4">
              <div className="text-sm text-gray-400">Postes les plus fréquents</div>
              {positionData.length > 6 && (
                <p className="text-xs text-gray-500 mt-1">Faites défiler pour voir tous les types de postes</p>
              )}
            </div>
          </div>
        </div>
      </div>
      <EditApplicationModal 
        isOpen={isEditModalOpen}
        onClose={() => setIsEditModalOpen(false)}
        onSuccess={handleEditSuccess}
        application={applicationToEdit}
      />
    </div>
  );
}