// Niveaux du score de pertinence hybride (backend : offer_scoring RELEVANCE_LEVELS).
// Affichés sans pourcentage, en pastilles pleines (vert, ambre, gris) pour ressortir
// parmi les badges translucides de la carte (Match IA, Évaluée, contrat...).
export const RELEVANCE_LEVEL_OPTIONS = [
  {
    value: "strong",
    label: "Pertinence forte",
    className: "bg-emerald-500 text-emerald-950 border-emerald-300",
    dotClassName: "bg-emerald-400",
  },
  {
    value: "medium",
    label: "Pertinence moyenne",
    className: "bg-amber-400 text-amber-950 border-amber-200",
    dotClassName: "bg-amber-400",
  },
  {
    value: "weak",
    label: "Pertinence faible",
    className: "bg-slate-500 text-white border-slate-300",
    dotClassName: "bg-slate-400",
  },
] as const;

export type RelevanceLevel = (typeof RELEVANCE_LEVEL_OPTIONS)[number]["value"];

export function getRelevanceLevelOption(level: string | null | undefined) {
  return RELEVANCE_LEVEL_OPTIONS.find((option) => option.value === level);
}
