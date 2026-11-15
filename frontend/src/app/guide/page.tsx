"use client";

import Link from "next/link";
import { FiBookOpen, FiArrowRight } from "react-icons/fi";
import GuideSections from "@/components/guide/GuideSections";
import GuideFaqSection from "@/components/guide/GuideFaqSection";

export default function GuidePage() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 py-10 px-4 sm:px-6 lg:px-8">
      <div className="max-w-6xl mx-auto space-y-12">
        <div className="text-center space-y-4 max-w-3xl mx-auto">
          <div className="inline-flex items-center gap-2 bg-blue-500/10 border border-blue-500/25 px-3 py-1 rounded-full text-blue-400 text-xs font-semibold">
            <FiBookOpen className="text-sm" />
            <span>Documentation Fonctionnelle &amp; Guide Rapide</span>
          </div>
          <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-white">
            Comment fonctionne{" "}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-indigo-400">
              MonSuiviJob
            </span>{" "}
            ?
          </h1>
          <p className="text-slate-400 text-sm sm:text-base leading-relaxed">
            Pas besoin de lire des pages entières de documentation. Découvrez visuellement en 2
            minutes le cycle de collecte automatique, les clés pour un profil parfait et vos outils
            de candidature.
          </p>
        </div>

        <GuideSections />
        <GuideFaqSection />

        <div className="bg-gradient-to-r from-blue-900/40 via-slate-900/80 to-indigo-900/40 p-6 sm:p-8 rounded-2xl border border-blue-800/30 flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="space-y-1 text-center sm:text-left">
            <h3 className="text-lg font-bold text-white">Prêt à activer vos recherches ?</h3>
            <p className="text-xs sm:text-sm text-slate-400">
              Renseignez vos critères cibles dans votre profil ou importez votre CV pour lancer la
              machine.
            </p>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-3 shrink-0">
            <Link
              href="/profile"
              className="bg-blue-600 hover:bg-blue-500 text-white px-5 py-2.5 rounded-xl text-xs font-semibold shadow-lg shadow-blue-500/20 transition-colors flex items-center gap-2"
            >
              <span>Accéder à mon Profil</span>
              <FiArrowRight className="text-xs" />
            </Link>
            <Link
              href="/offers"
              className="bg-slate-800 hover:bg-slate-700 text-slate-200 px-4 py-2.5 rounded-xl text-xs font-semibold transition-colors border border-slate-700"
            >
              Explorer les Offres
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
