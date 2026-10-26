// Clés de la taxonomie backend (company_profiles.PREFERENCE_SECTORS / COMPANY_SIZES)
export const SECTOR_OPTIONS: { value: string; label: string; desc: string }[] = [
  { value: "tech_it", label: "Tech & Logiciel", desc: "Éditeurs de logiciels, produits et plateformes numériques, Télécoms" },
  { value: "finance_insurance", label: "Banque, Finance & Assurance", desc: "Banque, Finance, Assurance, Fintech" },
  { value: "healthcare_pharma", label: "Santé & Pharma", desc: "Santé, Pharmacie, Biotech, Médical" },
  { value: "consulting_services", label: "Conseil, Audit & ESN", desc: "Conseil, Audit, ESN, Services B2B" },
  { value: "retail_ecommerce", label: "Retail & E-commerce", desc: "E-commerce, Retail, Grande Distribution, Mode" },
  { value: "industry_aerospace", label: "Industrie & Aéronautique", desc: "Industrie, Aéronautique, Automobile, Défense" },
  { value: "energy_environment", label: "Énergie & Environnement", desc: "Énergie, Environnement, CleanTech, RSE" },
  { value: "media_communication", label: "Médias & Communication", desc: "Médias, Communication, Divertissement, Jeux vidéo" },
  { value: "public_education", label: "Secteur public & Éducation", desc: "Secteur Public, Administration, Éducation, Recherche" },
  { value: "construction_realestate", label: "Immobilier & BTP", desc: "Immobilier, Construction, BTP, Urbanisme" },
  { value: "logistics_transport", label: "Transport & Logistique", desc: "Transport, Logistique, Supply Chain" },
  { value: "agri_food", label: "Agroalimentaire & Agriculture", desc: "Agroalimentaire, Agriculture" },
  { value: "nonprofit", label: "Associations & ONG", desc: "Associations, Fondations, ONG, Économie sociale et solidaire" },
];
export const COMPANY_SIZE_OPTIONS: { value: string; label: string }[] = [
  { value: "startup_tpe", label: "Startup / TPE (< 20 salariés)" },
  { value: "pme", label: "PME (20 - 249 salariés)" },
  { value: "eti", label: "ETI (250 - 4 999 salariés)" },
  { value: "grand_groupe", label: "Grand Groupe (5 000+ salariés)" },
];
