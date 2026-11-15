import { RemotePolicy } from "@/types/coverLetter";
import { SECTOR_OPTIONS } from "@/lib/companyTaxonomy";

export const REMOTE_OPTIONS: { value: RemotePolicy; label: string; desc: string; icon: string }[] = [
  { value: "full_remote", label: "Full Remote", desc: "100% télétravail", icon: "🏠" },
  { value: "hybrid", label: "Hybride", desc: "2 à 3 jours de remote / semaine", icon: "🏢" },
  { value: "on_site", label: "Sur site", desc: "Présentiel complet", icon: "📍" },
  { value: "flexible", label: "Flexible", desc: "Ouvert à toutes les options", icon: "🌐" },
];

export const CONTRACT_OPTIONS = ["CDI", "Freelance / Prestation", "CDD", "Alternance", "Stage"];
export const NOTICE_OPTIONS = ["Immédiat", "1 mois", "2 mois", "3 mois", "Plus de 3 mois"];
export const SECTOR_VALUES = new Set(SECTOR_OPTIONS.map((s) => s.value));

export const SENIORITY_OPTIONS = [
  { value: "junior", label: "Junior", desc: "0-2 ans d'expérience" },
  { value: "mid", label: "Intermédiaire", desc: "3-5 ans d'expérience" },
  { value: "senior", label: "Senior", desc: "6-8 ans d'expérience" },
  { value: "lead", label: "Lead / Staff", desc: "8+ ans d'expérience" },
  { value: "head_of", label: "Direction / Head of", desc: "Management & stratégie" },
];

export const SUGGESTED_LOCATIONS = [
  "Paris",
  "Lyon",
  "Toulouse",
  "Nantes",
  "Bordeaux",
  "Full Remote",
];

export const toggleStringValue = (list: string[], value: string): string[] =>
  list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
