// Miroir du registre backend (backend/app/services/cv_templates.py).
// backend/tests/test_cv_registry_parity.py vérifie que clés, ordre et couleurs concordent.

export const CV_TEMPLATES = [
  {
    key: "sidebar_elegance", label: "Sidebar Elegance",
    hint: "2 colonnes · tech, data, profils riches en compétences", supportsPhoto: true,
  },
  {
    key: "executive_minimalist", label: "Executive Minimalist",
    hint: "1 colonne épurée · cadres, conseil, finance", supportsPhoto: true,
  },
  {
    key: "classique", label: "Classique",
    hint: "Sobre, sans photo · logistique, industrie, RH", supportsPhoto: false,
  },
  {
    key: "creatif", label: "Créatif",
    hint: "En-tête en carte, photo possible · marketing, communication", supportsPhoto: true,
  },
] as const;

export const CV_ACCENTS = [
  { key: "marine", label: "Marine", primary: "#1e3a8a" },
  { key: "bleu_vert", label: "Bleu-vert", primary: "#0f766e" },
  { key: "ardoise", label: "Ardoise", primary: "#4f6d8a" },
  { key: "sauge", label: "Sauge", primary: "#4d6b4f" },
  { key: "bordeaux", label: "Bordeaux", primary: "#8b1e3f" },
  { key: "graphite", label: "Graphite", primary: "#374151" },
] as const;

export type CvTemplate = (typeof CV_TEMPLATES)[number];
export type CvTemplateKey = CvTemplate["key"];
export type CvAccentKey = (typeof CV_ACCENTS)[number]["key"];

export const DEFAULT_TEMPLATE: CvTemplateKey = "sidebar_elegance";
export const DEFAULT_ACCENT: CvAccentKey = "marine";

export interface ResumeAppearance {
  template: CvTemplateKey;
  accent: CvAccentKey;
  withPhoto: boolean;
}

// Un document ancien ou corrompu peut porter une clé absente ou inconnue : même repli que le backend.
export function resolveTemplateKey(value?: string | null): CvTemplateKey {
  const key = (value ?? "").trim().toLowerCase();
  return CV_TEMPLATES.find((t) => t.key === key)?.key ?? DEFAULT_TEMPLATE;
}

export function resolveAccentKey(value?: string | null): CvAccentKey {
  const key = (value ?? "").trim().toLowerCase();
  return CV_ACCENTS.find((a) => a.key === key)?.key ?? DEFAULT_ACCENT;
}

export function getTemplate(key: CvTemplateKey): CvTemplate {
  return CV_TEMPLATES.find((t) => t.key === key) ?? CV_TEMPLATES[0];
}
