const LEGACY_PROJECT_CONTEXT_LABELS: Record<string, string> = {
  perso: "Perso",
  client: "Client",
  recherche: "Recherche",
  consortium: "Consortium",
  associatif: "Associatif",
  evenement: "Événement",
};

const FRENCH_MONTHS = [
  "Janv.",
  "Févr.",
  "Mars",
  "Avril",
  "Mai",
  "Juin",
  "Juil.",
  "Août",
  "Sept.",
  "Oct.",
  "Nov.",
  "Déc.",
];

export function projectContextLabel(context?: string | null): string {
  if (!context) return "";
  return LEGACY_PROJECT_CONTEXT_LABELS[context] ?? context;
}

export function formatMonthYear(val?: string | null): string {
  if (!val) return "";
  const match = val.match(/^(\d{4})(?:-(\d{2}))?$/);
  if (!match) return val;
  const year = match[1];
  const monthNum = match[2];
  if (!monthNum) return year;
  const idx = parseInt(monthNum, 10) - 1;
  return idx >= 0 && idx < 12 ? `${FRENCH_MONTHS[idx]} ${year}` : `${monthNum}/${year}`;
}

export function formatPeriod(start?: string | null, end?: string | null): string {
  const startFmt = formatMonthYear(start);
  const endFmt = end ? formatMonthYear(end) : "Présent";
  if (!startFmt && !endFmt) return "Période non renseignée";
  if (!startFmt) return `Jusqu'à ${endFmt}`;
  return `${startFmt} — ${endFmt}`;
}

export function isLikelyBrokenLink(url?: string | null): boolean {
  if (!url) return false;
  try {
    return !/^https?:$/.test(new URL(url).protocol);
  } catch {
    return true;
  }
}

export function stringifySkillsMap(skills?: Record<string, string[]>): string {
  if (!skills) return "";
  return Object.entries(skills)
    .map(([category, list]) => `${category}: ${list.join(", ")}`)
    .join("\n");
}

export function parseSkillsText(skillsText: string): Record<string, string[]> {
  const parsed: Record<string, string[]> = {};
  if (!skillsText.trim()) return parsed;

  skillsText.split("\n").forEach((line) => {
    const parts = line.split(":");
    if (parts.length === 2) {
      const category = parts[0].trim().toLowerCase();
      const items = parts[1]
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      if (category && items.length > 0) {
        parsed[category] = items;
      }
    } else if (line.trim()) {
      const defaultCat = "principales";
      const items = line
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      parsed[defaultCat] = [...(parsed[defaultCat] || []), ...items];
    }
  });
  return parsed;
}
