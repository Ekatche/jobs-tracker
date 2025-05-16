export enum TaskStatus {
  TODO = "À faire",
  IN_PROGRESS = "En cours",
  DONE = "Terminée"
}

export interface ApiTask {
  _id?: string;
  title: string;
  description?: string;
  status: string; 
  user_id?: string; // Rendre optionnel pour correspondre à Task
  created_at?: string;
  updated_at?: string;
  due_date?: string;
  archived?: boolean; 
}

export interface Task {
  _id?: string;
  user_id?: string;
  title: string;
  description?: string;
  status: TaskStatus;
  due_date?: string;
  created_at?: string;
  updated_at?: string;
  attached_files?: string[];
  archived?: boolean; // ← AJOUTE cette ligne si elle n'existe pas
}

export const getStatusColor = (status: string) => {
  switch (status.toLowerCase()) {
    case "terminée":
      return "bg-emerald-900";
    case "en cours":
      return "bg-blue-900 ";
    case "à faire":
      return "bg-violet-900 ";
    default:
      return "bg-blue-night-light";
  }
};

export const getStatusBackgroundColor = (status: string) => {
  switch (status.toLowerCase()) {
    case "terminée":
      return "bg-emerald-900/50";
    case "en cours":
      return "bg-blue-900/50";
    case "à faire":
      return "bg-violet-900/50";
    default:
      return "bg-blue-night-lighter/60";
  }
};

// Type pour les applications groupées par statut
export type GroupedTasks = {
  [key: string]: Task[];
};
export const STATUS_ORDER: string[] = ["à faire", "en cours", "terminée"];

export const calculateDays = (dateString?: string): number => {
  if (!dateString) return 0;
  const now = new Date();
  const createdDate = new Date(dateString);
  const diffTime = Math.abs(now.getTime() - createdDate.getTime());
  return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
};
