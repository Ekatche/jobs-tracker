export interface Application {
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
  archived: boolean; // Ajoutez cette propriété (sans la rendre optionnelle)
}

// Type pour les applications groupées par statut
export type GroupedApplications = {
  [key: string]: Application[];
};

// Statuts d'après le backend (classe ApplicationStatus)
export const STATUS_ORDER: string[] = [
  "En étude",
  "Candidature envoyée", 
  "Première sélection", 
  "Entretien", 
  "Offre reçue", 
  "Refusée"
];

// Fonction pour obtenir la couleur de fond selon le statut
export const getStatusColor = (status: string): string => {
  switch (status) {
    case 'En étude':
      return 'bg-amber-700';
    case 'Candidature envoyée':
      return 'bg-blue-800';
    case 'Première sélection':
      return 'bg-cyan-700';
    case 'Entretien':
      return 'bg-purple-800';
    case 'Test technique': 
      return 'bg-indigo-700';
    case 'Offre reçue':
      return 'bg-green-800';
    case 'Refusée':
      return 'bg-red-800';
    default:
      return 'bg-gray-800';
  }
};

export const getStatusBackgroundColor = (status: string): string => {
  switch (status) {
    case "En étude":
      return 'bg-amber-900/40';
    case 'Candidature envoyée':
      return 'bg-blue-900/40';
    case 'Première sélection':
      return 'bg-cyan-900/40';
    case 'Entretien':
      return 'bg-purple-900/40';
    case 'Test technique':
      return 'bg-indigo-900/40';
    case 'Offre reçue':
      return 'bg-green-900/40';
    case 'Refusée':
      return 'bg-red-900/40';
    default:
      return 'bg-gray-800/40';
  }
};

// Fonction utilitaire pour formater les dates
export const formatDate = (dateString: string | undefined): string => {
  if (!dateString) return "Non défini";
  const date = new Date(dateString);
  return date.toLocaleDateString('fr-FR', {
    day: 'numeric',
    month: 'long',
    year: 'numeric'
  });
};

// Fonction pour calculer le nombre de jours depuis la candidature
export const calculateDays = (dateString: string): number => {
  const now = new Date();
  const applicationDate = new Date(dateString);
  const diffTime = Math.abs(now.getTime() - applicationDate.getTime());
  return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
};

// Fonction pour calculer la progression en fonction du statut
export const calculateProgress = (status: string): number => {
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

// Fonction pour normaliser les données de l'API
export const normalizeApiData = (apiData: Partial<Application> & { id?: string }): Application => ({
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
  updated_at: apiData.updated_at,
  archived: typeof apiData.archived === 'boolean' ? apiData.archived : false
});