// Niveaux du score de pertinence hybride (backend : offer_scoring RELEVANCE_LEVELS).
// Affichés sans pourcentage : forte en vert, moyenne en bleu, faible en gris.
export const RELEVANCE_LEVEL_OPTIONS = [
  {
    value: "strong",
    label: "Pertinence forte",
    className: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
  },
  {
    value: "medium",
    label: "Pertinence moyenne",
    className: "bg-blue-500/10 text-blue-300 border-blue-500/30",
  },
  {
    value: "weak",
    label: "Pertinence faible",
    className: "bg-slate-700/40 text-slate-300 border-slate-600/50",
  },
] as const;

export type RelevanceLevel = (typeof RELEVANCE_LEVEL_OPTIONS)[number]["value"];

export function getRelevanceLevelOption(level: string | null | undefined) {
  return RELEVANCE_LEVEL_OPTIONS.find((option) => option.value === level);
}
