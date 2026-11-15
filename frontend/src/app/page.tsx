import type { Metadata } from "next";
import LandingHero from "@/components/landing/LandingHero";
import LandingToolsAndPipeline from "@/components/landing/LandingToolsAndPipeline";
import LandingRgpdFaqFooter from "@/components/landing/LandingRgpdFaqFooter";

export const metadata: Metadata = {
  title: "MonSuiviJob — Votre espace personnel de suivi de candidatures",
  description:
    "Organisez simplement vos démarches d'emploi, gardez le fil de vos relances et préparez vos entretiens dans un cadre respectueux de votre vie privée (RGPD).",
};

export default function Home() {
  return (
    <div className="min-h-screen bg-blue-night text-slate-100 selection:bg-blue-600 selection:text-white">
      <LandingHero />
      <LandingToolsAndPipeline />
      <LandingRgpdFaqFooter />
    </div>
  );
}
