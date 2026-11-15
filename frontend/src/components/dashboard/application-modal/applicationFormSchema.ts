import { z } from "zod";

export const applicationSchema = z.object({
  company: z.string().min(1, "Le nom de l'entreprise est requis"),
  position: z.string().min(1, "Le poste est requis"),
  location: z.string().optional(),
  status: z.string().min(1, "Le statut est requis"),
  url: z.string().url("URL invalide").optional().or(z.literal("")),
  application_date: z.string().min(1, "La date de candidature est requise"),
  description: z.string().optional(),
  offer_id: z.string().optional(),
  archived: z.boolean().optional(),
});

export type ApplicationFormData = z.infer<typeof applicationSchema>;

export const NEW_APP_STATUSES = [
  "En étude",
  "Candidature envoyée",
  "Première sélection",
  "Entretien",
  "Offre reçue",
  "Refusée",
];

export const EDIT_APP_STATUSES = [
  "En étude",
  "Candidature envoyée",
  "Première sélection",
  "Entretien",
  "Test technique",
  "Négociation",
  "Offre reçue",
  "Offre acceptée",
  "Refusée",
];
