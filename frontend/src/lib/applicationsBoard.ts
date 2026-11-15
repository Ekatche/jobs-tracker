import {
  Application,
  calculateDays,
  sortApplicationsChronologically,
} from "@/types/application";
import { applicationApi } from "@/lib/api";
import type { NotificationType } from "@/contexts/NotificationContext";

export interface KanbanColumnData {
  id: string;
  title: string;
  dotColor: string;
  badgeBg: string;
  apps: Application[];
}

type NotifyFn = (type: NotificationType, msg: string) => void;

export function filterBoardApplications(
  applications: Application[],
  searchTerm: string,
  filterAlertOnly: boolean
): Application[] {
  const query = searchTerm.trim().toLowerCase();
  return applications.filter((app) => {
    const matchesSearch =
      !query ||
      app.company.toLowerCase().includes(query) ||
      app.position.toLowerCase().includes(query);

    const days = app.days_since_application ?? calculateDays(app.application_date);
    const isRelanceDue =
      app.follow_up_alert === "relance_due" ||
      (app.status === "Candidature envoyée" && days >= 7);
    const isRemerciementDue =
      app.follow_up_alert === "remerciement_due" ||
      (app.status === "Entretien" && days >= 1);
    return matchesSearch && (!filterAlertOnly || isRelanceDue || isRemerciementDue);
  });
}

export function buildKanbanColumns(filteredApplications: Application[]): KanbanColumnData[] {
  const getAppsFor = (statuses: string[]) =>
    sortApplicationsChronologically(
      filteredApplications.filter((a) => !a.archived && statuses.includes(a.status)),
      "asc"
    );
  const closedApps = filteredApplications.filter(
    (a) => a.archived || a.status === "Refusée" || a.status === "Retirée"
  );

  return [
    {
      id: "etude",
      title: "En étude / À préparer",
      dotColor: "bg-amber-400",
      badgeBg: "bg-amber-500/20 text-amber-300 border-amber-500/30",
      apps: getAppsFor(["En étude"]),
    },
    {
      id: "applied",
      title: "Candidatures envoyées",
      dotColor: "bg-blue-500",
      badgeBg: "bg-blue-500/20 text-blue-300 border-blue-500/30",
      apps: getAppsFor(["Candidature envoyée"]),
    },
    {
      id: "screening",
      title: "1ère Sélection / RH",
      dotColor: "bg-cyan-400",
      badgeBg: "bg-cyan-500/20 text-cyan-300 border-cyan-500/30",
      apps: getAppsFor(["Première sélection"]),
    },
    {
      id: "interview",
      title: "Entretiens & Tests",
      dotColor: "bg-purple-400",
      badgeBg: "bg-purple-500/20 text-purple-300 border-purple-500/30",
      apps: getAppsFor(["Entretien", "Test technique"]),
    },
    {
      id: "offer",
      title: "Offres reçues",
      dotColor: "bg-emerald-400",
      badgeBg: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
      apps: getAppsFor(["Offre reçue", "Négociation", "Offre acceptée"]),
    },
    {
      id: "closed",
      title: "Clôturées",
      dotColor: "bg-rose-500",
      badgeBg: "bg-rose-500/20 text-rose-300 border-rose-500/30",
      apps: sortApplicationsChronologically(closedApps, "asc"),
    },
  ];
}

export async function mutateApplicationNotes(
  app: Application,
  updatedNotes: string[],
  successMessage: string,
  errorMessage: string,
  setSelectedApplication: (a: Application) => void,
  refreshBoard: () => Promise<void>,
  addNotification: NotifyFn
) {
  try {
    setSelectedApplication({ ...app, notes: updatedNotes });
    await applicationApi.update(app._id, { notes: updatedNotes });
    await refreshBoard();
    addNotification("success", successMessage);
  } catch (err) {
    console.error(errorMessage, err);
    addNotification("error", errorMessage);
  }
}
