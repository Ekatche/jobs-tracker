"use client";

import Link from "next/link";
import {
  FiUserCheck,
  FiFileText,
  FiBriefcase,
  FiSliders,
  FiArrowRight,
  FiClock,
  FiSun,
  FiSunset,
  FiShield,
  FiCheck,
  FiGlobe,
  FiAward,
} from "react-icons/fi";

export default function GuideSections() {
  return (
    <>
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 sm:p-8 space-y-6 shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-blue-600/5 rounded-full blur-3xl pointer-events-none" />

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-5">
          <div>
            <div className="flex items-center gap-2.5 text-blue-400 text-xs font-bold uppercase tracking-wider mb-1">
              <FiClock className="text-sm" />
              <span>Orchestration Quotidienne (Apache Airflow)</span>
            </div>
            <h2 className="text-xl sm:text-2xl font-bold text-white">
              À quelle heure tournent les recherches automatiques ?
            </h2>
          </div>
          <div className="flex items-center gap-2 bg-slate-950 px-3.5 py-1.5 rounded-full border border-slate-800 text-xs text-slate-300">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>
              Cron automatique : <strong>Du lundi au vendredi</strong>
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
          <div className="bg-slate-950/80 border border-slate-800/80 rounded-xl p-5 relative group hover:border-slate-700 transition-all">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-mono font-bold text-slate-400 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
                06:00 UTC
              </span>
              <FiShield className="text-slate-400 text-lg" />
            </div>
            <h3 className="text-base font-bold text-white mb-1.5">Nettoyage &amp; Vérification</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Le robot vérifie les annonces existantes. Les offres pourvues, expirées ou dont les
              liens sont brisés sont archivées pour ne pas polluer votre tableau.
            </p>
          </div>

          <div className="bg-gradient-to-b from-blue-950/50 to-slate-950/90 border-2 border-blue-500/50 rounded-xl p-5 relative group shadow-lg shadow-blue-500/5">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-mono font-extrabold text-blue-300 bg-blue-900/60 px-2 py-0.5 rounded border border-blue-700/60 flex items-center gap-1.5">
                <FiSun className="text-amber-300 text-sm" />
                07:00 UTC
              </span>
              <span className="text-[10px] font-bold uppercase tracking-wider text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded-full border border-blue-500/20">
                Collecte du Matin
              </span>
            </div>
            <h3 className="text-base font-bold text-white mb-1.5">Nouvelles Offres au Réveil</h3>
            <p className="text-xs text-slate-300 leading-relaxed">
              Recherche exhaustive sur Indeed, LinkedIn, HelloWork et sites carrières. Vos nouvelles
              opportunités sont prêtes pour votre café du matin.
            </p>
          </div>

          <div className="bg-gradient-to-b from-indigo-950/50 to-slate-950/90 border-2 border-indigo-500/50 rounded-xl p-5 relative group shadow-lg shadow-indigo-500/5">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-mono font-extrabold text-indigo-300 bg-indigo-900/60 px-2 py-0.5 rounded border border-indigo-700/60 flex items-center gap-1.5">
                <FiSunset className="text-amber-400 text-sm" />
                16:00 UTC
              </span>
              <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded-full border border-indigo-500/20">
                Collecte de l&apos;Après-Midi
              </span>
            </div>
            <h3 className="text-base font-bold text-white mb-1.5">
              Annonces Publiées en Journée
            </h3>
            <p className="text-xs text-slate-300 leading-relaxed">
              Détection de toutes les annonces postées par les recruteurs en cours de journée.
              Postulez avant la fin de journée pour être parmi les 5 premiers CV reçus !
            </p>
          </div>
        </div>

        <div className="bg-slate-950/90 border border-slate-800 rounded-xl p-4 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 shrink-0">
              <FiSliders className="text-base" />
            </div>
            <div>
              <p className="font-semibold text-slate-200">
                Besoin de faire une pause dans vos recherches ?
              </p>
              <p className="text-slate-400">
                Désactivez simplement la veille dans votre profil. Airflow continue d&apos;exécuter
                ses routines sur le serveur mais ignore automatiquement votre compte jusqu&apos;à
                votre réactivation.
              </p>
            </div>
          </div>
          <Link
            href="/profile"
            className="shrink-0 bg-slate-800 hover:bg-slate-700 text-slate-200 px-3 py-1.5 rounded-lg border border-slate-700 font-medium transition-colors flex items-center gap-1.5"
          >
            <span>Vérifier mon statut</span>
            <FiArrowRight className="text-xs" />
          </Link>
        </div>
      </div>

      <div className="space-y-6">
        <div className="text-center sm:text-left space-y-1">
          <div className="inline-flex items-center gap-2 text-indigo-400 text-xs font-bold uppercase tracking-wider">
            <FiUserCheck className="text-sm" />
            <span>Optimisation Candidat</span>
          </div>
          <h2 className="text-2xl font-bold text-white">
            Comment configurer votre profil pour des résultats chirurgicaux ?
          </h2>
          <p className="text-slate-400 text-xs sm:text-sm">
            Quelques minutes de configuration suffisent pour alimenter les algorithmes de ciblage et
            de matching IA.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 flex flex-col justify-between hover:border-slate-700 transition-all">
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-400 flex items-center justify-center font-bold text-base">
                1
              </div>
              <h3 className="font-bold text-white text-base">Téléversez votre CV PDF</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Notre <strong>modèle de vision Mistral</strong> lit votre CV comme un humain. Les
                colonnes, timelines et badges sont extraits sans mélanger le texte.
              </p>
            </div>
            <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center gap-2 text-[11px] text-blue-300">
              <FiCheck className="text-blue-400" />
              <span>Extraction 100% visuelle fidèle</span>
            </div>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 flex flex-col justify-between hover:border-slate-700 transition-all">
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center font-bold text-base">
                2
              </div>
              <h3 className="font-bold text-white text-base">Liez vos Réalisations</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Renseignez votre <strong>site / portfolio</strong> ou votre compte{" "}
                <strong>GitHub</strong>. L&apos;IA extrait automatiquement vos projets concrets et
                langages de prédilection.
              </p>
            </div>
            <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center gap-2 text-[11px] text-indigo-300">
              <FiGlobe className="text-indigo-400" />
              <span>Multi-sources enrichi</span>
            </div>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 flex flex-col justify-between hover:border-slate-700 transition-all">
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400 flex items-center justify-center font-bold text-base">
                3
              </div>
              <h3 className="font-bold text-white text-base">Définissez vos Cibles</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Indiquez vos intitulés exacts (ex: <em>Data Engineer</em>), vos zones de mobilité
                (villes ou Full Remote) et vos contrats (CDI, Freelance).
              </p>
            </div>
            <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center gap-2 text-[11px] text-purple-300">
              <FiSliders className="text-purple-400" />
              <span>Filtre les annonces hors sujet</span>
            </div>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 flex flex-col justify-between hover:border-slate-700 transition-all">
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold text-base">
                4
              </div>
              <h3 className="font-bold text-white text-base">Arbitrage en 1 Clic</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Si un bandeau jaune de « divergence » s&apos;affiche, vos modifications manuelles
                ont toujours priorité. Cliquez sur « Masquer » une fois vos diplômes vérifiés.
              </p>
            </div>
            <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center gap-2 text-[11px] text-emerald-300">
              <FiShield className="text-emerald-400" />
              <span>Saisie manuelle toujours reine</span>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-6 space-y-4">
          <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/25 text-emerald-400 flex items-center justify-center text-lg">
            <FiAward />
          </div>
          <h3 className="text-lg font-bold text-white">Score de Matching / 5</h3>
          <p className="text-xs text-slate-300 leading-relaxed">
            Pour chaque offre détectée, l&apos;IA analyse les prérequis de l&apos;employeur et met en
            relief vos atouts clés ainsi que les points de vigilance à anticiper.
          </p>
          <div className="bg-slate-950 p-3 rounded-lg border border-slate-800/80 space-y-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Score ≥ 4.0</span>
              <span className="text-emerald-400 font-bold">Postulez immédiatement</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Score 3.0 à 3.9</span>
              <span className="text-amber-400 font-bold">À adapter avec l&apos;IA</span>
            </div>
          </div>
        </div>

        <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-6 space-y-4">
          <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/25 text-blue-400 flex items-center justify-center text-lg">
            <FiFileText />
          </div>
          <h3 className="text-lg font-bold text-white">CV &amp; Lettre sur-mesure</h3>
          <p className="text-xs text-slate-300 leading-relaxed">
            En un clic depuis une offre, générez un CV ciblé reprenant vos vraies expériences et une
            lettre de motivation rédigée selon votre ton naturel (Voice DNA).
          </p>
          <div className="bg-slate-950 p-3 rounded-lg border border-slate-800/80 text-xs text-slate-400">
            💡 <strong>ATS Friendly :</strong> Export PDF prêt à l&apos;emploi et lisible sans
            friction par les logiciels de recrutement.
          </div>
        </div>

        <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-6 space-y-4">
          <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/25 text-purple-400 flex items-center justify-center text-lg">
            <FiBriefcase />
          </div>
          <h3 className="text-lg font-bold text-white">Tableau Kanban &amp; Justificatifs</h3>
          <p className="text-xs text-slate-300 leading-relaxed">
            Suivez l&apos;avancée de vos candidatures d&apos;une colonne à l&apos;autre (À postuler,
            En étude, Entretien, Offre).
          </p>
          <div className="bg-slate-950 p-3 rounded-lg border border-slate-800/80 text-xs text-slate-400">
            📋 <strong>France Travail :</strong> Vos démarches sont horodatées et prêtes à être
            exportées pour vos actualisations sans stress.
          </div>
        </div>
      </div>
    </>
  );
}
