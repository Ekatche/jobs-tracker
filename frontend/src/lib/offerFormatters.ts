export const ITEMS_PER_PAGE = 16;

export const FAILED_CONDITION_LABELS: Record<string, string> = {
  geo: "Hors de votre zone géographique",
  contract: "Contrat différent de vos préférences",
};

export function cleanDescriptionPreview(text: string | undefined): string {
  if (!text || text === "Non spécifié") return "";
  return text
    .replace(/^\s*\d+\.\s*\*\*.*?\*\*\s*:?/gim, "")
    .replace(/\*\*.*?\*\*\s*:?/gi, "")
    .replace(/^\s*[•\-\*]\s+/gm, "")
    .replace(/\n\s*\n/g, "\n")
    .trim();
}

export function getRecentBadgeInfo(
  createdAtStr?: string
): { label: string; isFresh: boolean } | null {
  if (!createdAtStr) return null;
  const createdDate = new Date(createdAtStr);
  if (isNaN(createdDate.getTime())) return null;

  const diffHours = (Date.now() - createdDate.getTime()) / (1000 * 60 * 60);
  if (diffHours <= 24) return { label: "Nouveau (< 24h)", isFresh: true };
  if (diffHours <= 48) return { label: "Nouveau (< 48h)", isFresh: false };
  if (diffHours <= 7 * 24) return { label: "Récent (< 7j)", isFresh: false };
  return null;
}

export function formatAddedDate(createdAtStr?: string): string | null {
  if (!createdAtStr) return null;
  try {
    const d = new Date(createdAtStr);
    if (isNaN(d.getTime())) return null;
    const diffHours = (Date.now() - d.getTime()) / (1000 * 60 * 60);
    if (diffHours < 1) return "Ajoutée à l'instant";
    if (diffHours < 24) return `Ajoutée il y a ${Math.max(1, Math.round(diffHours))}h`;
    if (diffHours < 48) return "Ajoutée hier";
    return `Ajoutée le ${d.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit" })}`;
  } catch {
    return null;
  }
}

export function formatCollectionTime(isoUtc: string): string {
  return new Date(isoUtc).toLocaleString("fr-FR", {
    weekday: "long",
    day: "numeric",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Paris",
  });
}

export function formatOfferDate(dateString: string): string {
  if (!dateString || dateString === "Non spécifié") {
    return "Date non spécifiée";
  }
  if (dateString.includes("il y a") || dateString.includes("ago")) {
    return dateString;
  }
  try {
    const date = new Date(dateString);
    if (!isNaN(date.getTime())) {
      return date.toLocaleDateString("fr-FR");
    }
    return dateString;
  } catch {
    return dateString;
  }
}
