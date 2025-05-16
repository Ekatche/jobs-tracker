import { Application } from "@/types/application";

export interface StatusData {
  name: string;
  value: number;
  color: string;
}

export interface PositionData {
  name: string;
  value: number;
}

export function processStatusData(
  applications: Application[],
  statusColors: Record<string, string>,
): StatusData[] {
  // Calculer la distribution par statut
  const statusCounts: Record<string, number> = {};
  applications.forEach((app) => {
    statusCounts[app.status] = (statusCounts[app.status] || 0) + 1;
  });

  return Object.keys(statusCounts).map((status) => ({
    name: status,
    value: statusCounts[status],
    color: statusColors[status] || "#CCCCCC",
  }));
}

export function processPositionData(
  applications: Application[],
): PositionData[] {
  // Calculer la distribution par intitulé de poste
  const positionCounts: Record<string, number> = {};
  applications.forEach((app) => {
    positionCounts[app.position] = (positionCounts[app.position] || 0) + 1;
  });

  // Trier par nombre d'occurrences et prendre les 10 plus fréquents
  return Object.keys(positionCounts)
    .sort((a, b) => positionCounts[b] - positionCounts[a])
    .slice(0, 10)
    .map((position) => ({
      name: position,
      value: positionCounts[position],
    }));
}
