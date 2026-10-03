"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  FiBookOpen,
  FiCpu,
  FiUserCheck,
  FiFileText,
  FiSearch,
  FiCheckCircle,
  FiAlertCircle,
  FiBriefcase,
  FiChevronDown,
  FiChevronUp,
  FiSliders,
  FiArrowRight,
  FiHelpCircle,
  FiClock,
  FiSun,
  FiSunset,
  FiUploadCloud,
  FiZap,
  FiShield,
  FiCheck,
  FiLayers,
  FiEye,
  FiGlobe,
  FiGithub,
  FiAward,
  FiSend,
} from "react-icons/fi";

interface FaqItem {
  id: string;
  category: "airflow" | "profile" | "matching" | "generation" | "kanban";
  question: string;
  summary: string;
  content: React.ReactNode;
}

const FAQ_ITEMS: FaqItem[] = [
  {
    id: "airflow-sources",
    category: "airflow",
    question: "D'où proviennent exactement les offres d'emploi collectées ?",
    summary: "Airflow interroge chaque jour France Travail, Indeed, LinkedIn et les sites carrières via Tavily AI.",
    content: (
      <div className="space-y-2 text-slate-300 text-sm">
        <p>Les pipelines automatisés (DAGs) regroupent 4 sources complémentaires :</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1 text-xs">
          <div className="bg-slate-900/90 p-2.5 rounded-lg border border-slate-800">
            <span className="font-semibold text-blue-400 block mb-0.5">🏛️ API France Travail</span>
            Flux officiel des offres certifiées en France, actualisé en temps réel.
          </div>
          <div className="bg-slate-900/90 p-2.5 rounded-lg border border-slate-800">
            <span className="font-semibold text-indigo-400 block mb-0.5">💼 Indeed & LinkedIn</span>
            Collecte et normalisation des offres des principales plateformes pro.
          </div>
          <div className="bg-slate-900/90 p-2.5 rounded-lg border border-slate-800">
            <span className="font-semibold text-purple-400 block mb-0.5">🔍 Moteur Web (Tavily AI)</span>
            Détection automatique des annonces sur les pages carrières d'entreprises.
          </div>
          <div className="bg-slate-900/90 p-2.5 rounded-lg border border-slate-800">
            <span className="font-semibold text-emerald-400 block mb-0.5">🛡️ Filtre Anti-Bruit</span>
            Élimination instantanée des doublons et des offres expirées.
          </div>
        </div>
      </div>
    ),
  },
  {
    id: "airflow-targeting",
    category: "airflow",
    question: "Comment le moteur sait-il quelles offres vous envoyer ?",
    summary: "La collecte lit directement vos critères définis dans l'onglet Profil (intitulés, villes, contrats).",
    content: (
      <div className="space-y-2 text-slate-300 text-sm">
        <p>
          Le système ne fait aucune recherche générique au hasard : il convertit vos critères de ciblage en requêtes de recherche spécialisées.
        </p>
        <ul className="list-disc pl-5 space-y-1 text-xs text-slate-400">
          <li>Vos <strong>intitulés ciblés</strong> (ex. <em>Data Scientist, Dev Fullstack</em>)</li>
          <li>Vos <strong>localisations et tolérance télétravail</strong> (ex. <em>Lyon, Télétravail partiel ou 100%</em>)</li>
          <li>Vos <strong>types de contrats</strong> retenus (CDI, CDD, Freelance, Alternance)</li>
        </ul>
      </div>
    ),
  },
  {
    id: "profile-vlm",
    category: "profile",
    question: "Pourquoi l'IA de vision (VLM) est-elle supérieure à un simple lecteur de PDF ?",
    summary: "Elle analyse visuellement votre CV pour ne pas mélanger les colonnes, dates et compétences.",
    content: (
      <div className="space-y-2 text-slate-300 text-sm">
        <p>
          Les parseurs traditionnels lisent de gauche à droite et mélangent le texte des barres latérales avec le texte principal.
        </p>
        <p className="text-xs text-slate-400">
          Notre modèle de vision (<strong>Mistral Pixtral VLM</strong>) « regarde » chaque page comme un humain : il identifie chaque bloc visuel, préserve la chronologie des postes et associe fidèlement vos compétences à leurs expériences.
        </p>
      </div>
    ),
  },
  {
    id: "profile-conflicts",
    category: "profile",
    question: "Que faire en cas de divergences ou doublons de diplômes ?",
    summary: "La saisie manuelle l'emporte toujours. Les diplômes similaires sont automatiquement rapprochés.",
    content: (
      <div className="space-y-2 text-slate-300 text-sm">
        <p>
          En cas de conflit entre deux sources (ex: libellé de contrat ou date différente), l'arbitrage est automatique : 
          <span className="font-mono text-xs text-emerald-400 ml-1 font-semibold">Manuel &gt; CV &gt; Site &gt; GitHub</span>.
        </p>
        <p className="text-xs text-slate-400">
          Les diplômes d'une même école avec des variantes d'intitulé sont fusionnés intelligemment pour retenir la version la plus complète. Vous pouvez masquer le bandeau des divergences d'un simple clic.
        </p>
      </div>
    ),
  },
  {
    id: "matching-score",
    category: "matching",
    question: "Comment interpréter votre Matching Score sur une annonce ?",
    summary: "Une note sur 5 calculée par IA avec analyse des points forts et points de vigilance.",
    content: (
      <div className="space-y-2 text-slate-300 text-sm">
        <div className="grid grid-cols-3 gap-2 text-center text-xs">
          <div className="p-2 bg-emerald-500/10 border border-emerald-500/30 rounded-lg">
            <span className="font-bold text-emerald-400 block text-sm">4.0 - 5.0</span>
            <span className="text-slate-300">Excellente adéquation</span>
          </div>
          <div className="p-2 bg-amber-500/10 border border-amber-500/30 rounded-lg">
            <span className="font-bold text-amber-400 block text-sm">3.0 - 3.9</span>
            <span className="text-slate-300">Adéquation partielle</span>
          </div>
          <div className="p-2 bg-rose-500/10 border border-rose-500/30 rounded-lg">
            <span className="font-bold text-rose-400 block text-sm">&lt; 3.0</span>
            <span className="text-slate-300">Profil trop éloigné</span>
          </div>
        </div>
        <p className="text-xs text-slate-400">
          L'analyse fournit aussi les compétences clés manquantes à mettre en avant ou à préparer pour votre entretien.
        </p>
      </div>
    ),
  },
];

export default function GuidePage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [openItems, setOpenItems] = useState<Record<string, boolean>>({});

  const toggleItem = (id: string) => {
    setOpenItems((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const filteredFaq = FAQ_ITEMS.filter((item) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return item.question.toLowerCase().includes(q) || item.summary.toLowerCase().includes(q);
  });

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 py-10 px-4 sm:px-6 lg:px-8">
      <div className="max-w-6xl mx-auto space-y-12">
        {/* En-tête / Hero */}
        <div className="text-center space-y-4 max-w-3xl mx-auto">
          <div className="inline-flex items-center gap-2 bg-blue-500/10 border border-blue-500/25 px-3 py-1 rounded-full text-blue-400 text-xs font-semibold">
            <FiBookOpen className="text-sm" />
            <span>Documentation Fonctionnelle & Guide Rapide</span>
          </div>
          <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-white">
            Comment fonctionne <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-indigo-400">MonSuiviJob</span> ?
          </h1>
          <p className="text-slate-400 text-sm sm:text-base leading-relaxed">
            Pas besoin de lire des pages entières de documentation. Découvrez visuellement en 2 minutes le cycle de collecte automatique, les clés pour un profil parfait et vos outils de candidature.
          </p>
        </div>

        {/* ========================================================================= */}
        {/* SECTION 1 : LE RYTHME DE L'AUTOMATISATION AIRFLOW (TIMELINE VISUELLE) */}
        {/* ========================================================================= */}
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
              <span>Cron automatique : <strong>Du lundi au vendredi</strong></span>
            </div>
          </div>

          {/* Timeline Visuelle Horaires Clés */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
            {/* 06:00 */}
            <div className="bg-slate-950/80 border border-slate-800/80 rounded-xl p-5 relative group hover:border-slate-700 transition-all">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-mono font-bold text-slate-400 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
                  06:00 UTC
                </span>
                <FiShield className="text-slate-400 text-lg" />
              </div>
              <h3 className="text-base font-bold text-white mb-1.5 flex items-center gap-2">
                <span>Nettoyage & Vérification</span>
              </h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Le robot vérifie les annonces existantes. Les offres pourvues, expirées ou dont les liens sont brisés sont archivées pour ne pas polluer votre tableau.
              </p>
            </div>

            {/* 07:00 (PRINCIPALE DU MATIN) */}
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
              <h3 className="text-base font-bold text-white mb-1.5">
                Nouvelles Offres au Réveil
              </h3>
              <p className="text-xs text-slate-300 leading-relaxed">
                Recherche exhaustive sur France Travail, Indeed, LinkedIn et sites carrières. Vos nouvelles opportunités sont prêtes pour votre café du matin.
              </p>
            </div>

            {/* 16:00 (PRINCIPALE DE L'APREM) */}
            <div className="bg-gradient-to-b from-indigo-950/50 to-slate-950/90 border-2 border-indigo-500/50 rounded-xl p-5 relative group shadow-lg shadow-indigo-500/5">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-mono font-extrabold text-indigo-300 bg-indigo-900/60 px-2 py-0.5 rounded border border-indigo-700/60 flex items-center gap-1.5">
                  <FiSunset className="text-amber-400 text-sm" />
                  16:00 UTC
                </span>
                <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded-full border border-indigo-500/20">
                  Collecte de l'Après-Midi
                </span>
              </div>
              <h3 className="text-base font-bold text-white mb-1.5">
                Annonces Publiées en Journée
              </h3>
              <p className="text-xs text-slate-300 leading-relaxed">
                Détection de toutes les annonces postées par les recruteurs en cours de journée. Postulez avant la fin de journée pour être parmi les 5 premiers CV reçus !
              </p>
            </div>
          </div>

          {/* Bannière explicative "Mise en pause" */}
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
                  Désactivez simplement la veille dans votre profil. Airflow continue d'exécuter ses routines sur le serveur mais ignore automatiquement votre compte jusqu'à votre réactivation.
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

        {/* ========================================================================= */}
        {/* SECTION 2 : COMMENT REMPLIR AU MIEUX SON PROFIL (GUIDE EN 4 ÉTAPES) */}
        {/* ========================================================================= */}
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
              Quelques minutes de configuration suffisent pour alimenter les algorithmes de ciblage et de matching IA.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Étape 1 */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 flex flex-col justify-between hover:border-slate-700 transition-all">
              <div className="space-y-3">
                <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-400 flex items-center justify-center font-bold text-base">
                  1
                </div>
                <h3 className="font-bold text-white text-base">Téléversez votre CV PDF</h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Notre modèle de vision <strong>Mistral Pixtral VLM</strong> lit votre CV comme un humain. Les colonnes, timelines et badges sont extraits sans mélanger le texte.
                </p>
              </div>
              <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center gap-2 text-[11px] text-blue-300">
                <FiCheck className="text-blue-400" />
                <span>Extraction 100% visuelle fidèle</span>
              </div>
            </div>

            {/* Étape 2 */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 flex flex-col justify-between hover:border-slate-700 transition-all">
              <div className="space-y-3">
                <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center font-bold text-base">
                  2
                </div>
                <h3 className="font-bold text-white text-base">Liez vos Réalisations</h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Renseignez votre <strong>site / portfolio</strong> ou votre compte <strong>GitHub</strong>. L'IA extrait automatiquement vos projets concrets et langages de prédilection.
                </p>
              </div>
              <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center gap-2 text-[11px] text-indigo-300">
                <FiGlobe className="text-indigo-400" />
                <span>Multi-sources enrichi</span>
              </div>
            </div>

            {/* Étape 3 */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 flex flex-col justify-between hover:border-slate-700 transition-all">
              <div className="space-y-3">
                <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400 flex items-center justify-center font-bold text-base">
                  3
                </div>
                <h3 className="font-bold text-white text-base">Définissez vos Cibles</h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Indiquez vos intitulés exacts (ex: <em>Data Engineer</em>), vos zones de mobilité (villes ou Full Remote) et vos contrats (CDI, Freelance).
                </p>
              </div>
              <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center gap-2 text-[11px] text-purple-300">
                <FiSliders className="text-purple-400" />
                <span>Filtre les annonces hors sujet</span>
              </div>
            </div>

            {/* Étape 4 */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 flex flex-col justify-between hover:border-slate-700 transition-all">
              <div className="space-y-3">
                <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold text-base">
                  4
                </div>
                <h3 className="font-bold text-white text-base">Arbitrage en 1 Clic</h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Si un bandeau jaune de « divergence » s'affiche, vos modifications manuelles ont toujours priorité. Cliquez sur « Masquer » une fois vos diplômes vérifiés.
                </p>
              </div>
              <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center gap-2 text-[11px] text-emerald-300">
                <FiShield className="text-emerald-400" />
                <span>Saisie manuelle toujours reine</span>
              </div>
            </div>
          </div>
        </div>

        {/* ========================================================================= */}
        {/* SECTION 3 : BENTO GRID FONCTIONNELLES (MATCHING, CV ADAPTÉ, KANBAN) */}
        {/* ========================================================================= */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Carte 1 : Matching IA */}
          <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-6 space-y-4">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/25 text-emerald-400 flex items-center justify-center text-lg">
              <FiAward />
            </div>
            <h3 className="text-lg font-bold text-white">Score de Matching / 5</h3>
            <p className="text-xs text-slate-300 leading-relaxed">
              Pour chaque offre détectée, l'IA analyse les prérequis de l'employeur et met en relief vos atouts clés ainsi que les points de vigilance à anticiper.
            </p>
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800/80 space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Score ≥ 4.0</span>
                <span className="text-emerald-400 font-bold">Postulez immédiatement</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Score 3.0 à 3.9</span>
                <span className="text-amber-400 font-bold">À adapter avec l'IA</span>
              </div>
            </div>
          </div>

          {/* Carte 2 : Génération CV & Lettre */}
          <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-6 space-y-4">
            <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/25 text-blue-400 flex items-center justify-center text-lg">
              <FiFileText />
            </div>
            <h3 className="text-lg font-bold text-white">CV & Lettre sur-mesure</h3>
            <p className="text-xs text-slate-300 leading-relaxed">
              En un clic depuis une offre, générez un CV ciblé reprenant vos vraies expériences et une lettre de motivation rédigée selon votre ton naturel (Voice DNA).
            </p>
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800/80 text-xs text-slate-400">
              💡 <strong>ATS Friendly :</strong> Export PDF prêt à l'emploi et lisible sans friction par les logiciels de recrutement.
            </div>
          </div>

          {/* Carte 3 : Suivi Kanban & Preuves */}
          <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-6 space-y-4">
            <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/25 text-purple-400 flex items-center justify-center text-lg">
              <FiBriefcase />
            </div>
            <h3 className="text-lg font-bold text-white">Tableau Kanban & Justificatifs</h3>
            <p className="text-xs text-slate-300 leading-relaxed">
              Suivez l'avancée de vos candidatures d'une colonne à l'autre (À postuler, En étude, Entretien, Offre).
            </p>
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800/80 text-xs text-slate-400">
              📋 <strong>France Travail :</strong> Vos démarches sont horodatées et prêtes à être exportées pour vos actualisations sans stress.
            </div>
          </div>
        </div>

        {/* ========================================================================= */}
        {/* SECTION 4 : QUESTIONS FRÉQUENTES / ACCORDÉONS COMPACTS */}
        {/* ========================================================================= */}
        <div className="bg-slate-900/40 border border-slate-800/80 rounded-2xl p-6 sm:p-8 space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 text-blue-400 text-xs font-bold uppercase tracking-wider mb-1">
                <FiHelpCircle className="text-sm" />
                <span>Questions Précises</span>
              </div>
              <h2 className="text-xl sm:text-2xl font-bold text-white">FAQ & Détails Techniques</h2>
            </div>

            {/* Barre de recherche compacte */}
            <div className="relative w-full sm:w-72">
              <FiSearch className="absolute left-3.5 top-3 text-slate-400 text-sm" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Filtrer une question..."
                className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
          </div>

          <div className="space-y-3">
            {filteredFaq.length === 0 ? (
              <p className="text-center py-6 text-xs text-slate-400">Aucune question ne correspond à votre recherche.</p>
            ) : (
              filteredFaq.map((item) => {
                const isOpen = !!openItems[item.id];
                return (
                  <div
                    key={item.id}
                    className="bg-slate-950/70 border border-slate-800/90 rounded-xl overflow-hidden transition-all hover:border-slate-700/80"
                  >
                    <button
                      type="button"
                      onClick={() => toggleItem(item.id)}
                      className="w-full px-4 py-3.5 text-left flex items-center justify-between gap-4 focus:outline-none"
                    >
                      <div>
                        <h4 className="text-sm font-semibold text-white">{item.question}</h4>
                        <p className="text-[11px] text-slate-400 mt-0.5">{item.summary}</p>
                      </div>
                      <div className="text-slate-400 shrink-0">
                        {isOpen ? <FiChevronUp className="w-4 h-4" /> : <FiChevronDown className="w-4 h-4" />}
                      </div>
                    </button>
                    {isOpen && (
                      <div className="px-4 pb-4 pt-1 border-t border-slate-800/60 mt-1">
                        {item.content}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* ========================================================================= */}
        {/* BANNIÈRE FINALE / CALL TO ACTION */}
        {/* ========================================================================= */}
        <div className="bg-gradient-to-r from-blue-900/40 via-slate-900/80 to-indigo-900/40 p-6 sm:p-8 rounded-2xl border border-blue-800/30 flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="space-y-1 text-center sm:text-left">
            <h3 className="text-lg font-bold text-white">Prêt à activer vos recherches ?</h3>
            <p className="text-xs sm:text-sm text-slate-400">
              Renseignez vos critères cibles dans votre profil ou importez votre CV pour lancer la machine.
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
