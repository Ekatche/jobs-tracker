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
  FiRefreshCw,
  FiLayers,
  FiEye,
  FiBriefcase,
  FiGlobe,
  FiGithub,
  FiChevronDown,
  FiChevronUp,
  FiSliders,
  FiSend,
  FiArrowRight,
  FiHelpCircle,
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
    question: "Comment fonctionne la collecte automatique des offres d'emploi (CRONs / Airflow) ?",
    summary: "Airflow orchestre des robots de collecte chaque jour sur France Travail, Indeed, LinkedIn et le web.",
    content: (
      <div className="space-y-3 text-slate-300">
        <p>
          Un orchestrateur <strong className="text-white">Apache Airflow</strong> tourne en continu sur le serveur et déclenche des pipelines automatisés (DAGs) à intervalles réguliers (toutes les nuits et en journée).
        </p>
        <p>Il collecte les nouvelles annonces depuis :</p>
        <ul className="list-disc pl-5 space-y-1 text-slate-300">
          <li><strong className="text-blue-400">L'API France Travail</strong> (offres officielles certifiées en temps réel).</li>
          <li><strong className="text-blue-400">Indeed & LinkedIn</strong> (collecteurs spécialisés et normalisation des URLs).</li>
          <li><strong className="text-blue-400">Moteurs de recherche web (Tavily AI)</strong> (détection d'offres directement sur les sites carrières d'entreprises).</li>
        </ul>
        <p className="text-xs text-slate-400 bg-slate-900/90 p-3 rounded-lg border border-slate-800">
          💡 <strong className="text-slate-200">Anti-bruit :</strong> Un filtre de pertinence écarte automatiquement les annonces hors-domaine, les doublons multi-plateformes et les liens morts avant de vous les présenter.
        </p>
      </div>
    ),
  },
  {
    id: "airflow-targeting",
    category: "airflow",
    question: "Comment la collecte sait-elle quelles offres me correspondent ?",
    summary: "Elle lit directement vos critères de recherche configurés dans votre Profil.",
    content: (
      <div className="space-y-3 text-slate-300">
        <p>
          La collecte n'est pas générique : elle est <strong className="text-white">pilotée par vos critères de ciblage</strong> renseignés dans votre onglet <Link href="/profile" className="text-blue-400 underline hover:text-blue-300">Profil & Ciblage</Link>.
        </p>
        <ul className="list-disc pl-5 space-y-1">
          <li><strong className="text-white">Intitulés ciblés :</strong> ex. <em>Data Engineer</em>, <em>Machine Learning Engineer</em>, etc.</li>
          <li><strong className="text-white">Localisation & Télétravail :</strong> vos villes préférées (ex. Lyon, Paris) ou votre souhait de Full Remote.</li>
          <li><strong className="text-white">Types de contrats :</strong> CDI, CDD, Freelance, VIE, Alternance.</li>
        </ul>
        <p>
          Airflow normalise ces critères et génère des requêtes intelligentes qui mutualisent la collecte tout en rattachant automatiquement chaque offre trouvée à votre compte.
        </p>
      </div>
    ),
  },
  {
    id: "airflow-toggle",
    category: "airflow",
    question: "Puis-je mettre en pause la veille automatique sans supprimer mon profil ?",
    summary: "Oui, grâce à l'interrupteur « Veille active / En pause » dans votre profil.",
    content: (
      <div className="space-y-3 text-slate-300">
        <p>
          Dans la section <strong className="text-white">« Critères de recherche & Veille »</strong> de votre profil, vous disposez d'un interrupteur :
        </p>
        <div className="bg-slate-900 p-3 rounded-lg border border-slate-800 text-xs flex items-center justify-between">
          <span className="font-medium text-slate-200">Veille automatique des offres</span>
          <span className="bg-emerald-500/20 text-emerald-300 px-2.5 py-1 rounded-full font-semibold border border-emerald-500/30">
            Active / En pause
          </span>
        </div>
        <p>
          En basculant sur <strong className="text-amber-300">En pause</strong>, Airflow cesse d'interroger les plateformes pour votre profil. Vos offres déjà collectées et votre historique de candidatures restent intacts. Vous pouvez la réactiver d'un clic dès que vous reprenez vos recherches.
        </p>
      </div>
    ),
  },
  {
    id: "profile-multisource",
    category: "profile",
    question: "Comment fonctionne la fusion multi-sources du profil candidat ?",
    summary: "MonSuiviJob consolide 4 sources (CV PDF, site web, GitHub, manuel) avec une priorité stricte.",
    content: (
      <div className="space-y-3 text-slate-300">
        <p>
          Votre profil est alimenté par jusqu'à 4 canaux complémentaires :
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
          <div className="bg-slate-900 p-2.5 rounded-lg border border-slate-800">
            <span className="font-bold text-blue-400 block mb-1">📄 1. CV PDF (Mistral VLM)</span>
            Extraction visuelle fidèle des colonnes, timelines et badges.
          </div>
          <div className="bg-slate-900 p-2.5 rounded-lg border border-slate-800">
            <span className="font-bold text-indigo-400 block mb-1">🌐 2. Site Web / Portfolio</span>
            Scraping des réalisations et projets en ligne.
          </div>
          <div className="bg-slate-900 p-2.5 rounded-lg border border-slate-800">
            <span className="font-bold text-purple-400 block mb-1">🐙 3. GitHub</span>
            Analyse des dépôts publics, technologies et langages maîtrisés.
          </div>
          <div className="bg-slate-900 p-2.5 rounded-lg border border-slate-800">
            <span className="font-bold text-emerald-400 block mb-1">✍️ 4. Saisie Manuelle</span>
            Vos corrections directes dans l'interface MonSuiviJob.
          </div>
        </div>
        <div className="bg-blue-950/40 p-3 rounded-lg border border-blue-800/40 text-xs">
          <p className="font-semibold text-blue-300 mb-1">Ordre de priorité d'arbitrage :</p>
          <p className="font-mono text-white">Manual (gagne toujours) &gt; CV &gt; Website &gt; GitHub</p>
          <p className="text-slate-400 mt-1">Si vous modifiez manuellement un champ, cette valeur prime définitivement sur les données extraites automatiquement.</p>
        </div>
      </div>
    ),
  },
  {
    id: "profile-vlm",
    category: "profile",
    question: "Quel est le rôle du modèle VLM (Vision Language Model) ?",
    summary: "Il « regarde » votre CV PDF comme un œil humain pour ne pas mélanger les colonnes.",
    content: (
      <div className="space-y-3 text-slate-300">
        <p>
          Lors du téléversement de votre CV, le backend convertit chaque page en image et fait appel à <strong className="text-white">Mistral Pixtral (VLM)</strong>.
        </p>
        <p>
          Contrairement aux parseurs PDF textuels traditionnels qui lisent de gauche à droite et mélangent le texte des colonnes parallèles, le modèle VLM comprend la <strong className="text-white">mise en page graphique</strong> :
        </p>
        <ul className="list-disc pl-5 space-y-1">
          <li>Il sépare distinctement la barre latérale (compétences, contact) du corps principal (timeline d'expériences).</li>
          <li>Il lit correctement les dates, durées et intitulés exacts de diplômes.</li>
          <li>Il préserve l'association exacte entre les missions et les technologies associées.</li>
        </ul>
      </div>
    ),
  },
  {
    id: "profile-conflicts",
    category: "profile",
    question: "Que signifient les « Divergences détectées entre vos sources » ?",
    summary: "Un indicateur de transparence qui vous montre ce qui a été choisi et écarté entre vos sources.",
    content: (
      <div className="space-y-3 text-slate-300">
        <p>
          Si votre CV mentionne par exemple <em>« VIE — Île Maurice »</em> et que votre saisie manuelle indique <em>« CDI — Mauritius (Remote) »</em>, le système arbitre en faveur de votre saisie manuelle.
        </p>
        <p>
          Pour éviter tout effet « boîte noire », l'encadré jaune des divergences vous informe précisément de :
        </p>
        <ul className="list-disc pl-5 space-y-1">
          <li>La valeur retenue et sa source d'origine.</li>
          <li>La valeur écartée et la source qui la contenait.</li>
        </ul>
        <p className="text-xs text-slate-400">
          Vous pouvez cliquer sur <strong className="text-amber-300">« Masquer »</strong> à tout moment pour alléger l'affichage une fois vos informations vérifiées.
        </p>
      </div>
    ),
  },
  {
    id: "profile-education-dedup",
    category: "profile",
    question: "Comment sont gérés les doublons de diplômes et d'écoles ?",
    summary: "Un système de rapprochement intelligent fusionne les variations de libellés sans perte d'information.",
    content: (
      <div className="space-y-3 text-slate-300">
        <p>
          Deux sources écrivent rarement une formation exactement de la même manière (ex. <em>« Université Lyon 1 »</em> vs <em>« Université Claude Bernard Lyon 1 »</em>, ou <em>« Master Informatique »</em> vs <em>« Master en Informatique / Data Science »</em>).
        </p>
        <p>MonSuiviJob applique des règles intelligentes :</p>
        <ul className="list-disc pl-5 space-y-1">
          <li><strong className="text-white">Rapprochement par entité :</strong> il identifie qu'il s'agit de la même école et du même cursus.</li>
          <li><strong className="text-white">Conservation de la richesse :</strong> il sélectionne le libellé le plus complet et l'intervalle d'années le plus précis.</li>
          <li><strong className="text-white">Fusion des matières :</strong> les compétences, cours et spécialisations listés dans chaque source sont réunis sans doublon.</li>
          <li><strong className="text-white">Respect des niveaux :</strong> une Licence et un Master obtenus dans la même université restent deux formations distinctes.</li>
        </ul>
      </div>
    ),
  },
  {
    id: "matching-score",
    category: "matching",
    question: "Comment est calculé le score d'adéquation d'une offre d'emploi (Matching IA) ?",
    summary: "L'IA évalue en 2 passes la correspondance entre votre profil et les exigences du recruteur.",
    content: (
      <div className="space-y-3 text-slate-300">
        <p>
          Pour chaque offre, l'intelligence artificielle compare votre profil réel aux prérequis du recruteur :
        </p>
        <div className="space-y-2 text-xs">
          <div className="bg-slate-900 p-2.5 rounded-lg border border-slate-800 flex items-start gap-2">
            <span className="bg-emerald-500/20 text-emerald-300 font-bold px-2 py-0.5 rounded border border-emerald-500/30 shrink-0">4.0 à 5.0</span>
            <span><strong className="text-white">Forte adéquation :</strong> vous maîtrisez la stack cœur et vos expériences passées répondent directement aux missions.</span>
          </div>
          <div className="bg-slate-900 p-2.5 rounded-lg border border-slate-800 flex items-start gap-2">
            <span className="bg-amber-500/20 text-amber-300 font-bold px-2 py-0.5 rounded border border-amber-500/30 shrink-0">3.0 à 3.9</span>
            <span><strong className="text-white">Adéquation partielle :</strong> bonne base de compétences, mais certains critères secondaires ou années d'expérience manquent.</span>
          </div>
          <div className="bg-slate-900 p-2.5 rounded-lg border border-slate-800 flex items-start gap-2">
            <span className="bg-red-500/20 text-red-300 font-bold px-2 py-0.5 rounded border border-red-500/30 shrink-0">&lt; 3.0</span>
            <span><strong className="text-white">Écart significatif :</strong> profil trop éloigné du domaine attendu ou de la séniorité exigée.</span>
          </div>
        </div>
        <p>
          L'analyse fournit également la liste de vos <strong className="text-emerald-400">Points forts</strong>, de vos <strong className="text-amber-400">Points de vigilance</strong>, ainsi que les compétences manquantes recommandées pour adapter votre discours.
        </p>
      </div>
    ),
  },
  {
    id: "generation-cv",
    category: "generation",
    question: "Comment fonctionne la génération de CV adaptés aux offres ?",
    summary: "Générez un CV ciblé reprenant vos vraies expériences et le vocabulaire précis de l'offre.",
    content: (
      <div className="space-y-3 text-slate-300">
        <p>
          Depuis la page <Link href="/resumes" className="text-blue-400 underline hover:text-blue-300">CV Adaptés</Link> ou directement depuis une offre d'emploi :
        </p>
        <ul className="list-disc pl-5 space-y-1">
          <li>L'IA analyse les mots-clés clés de l'annonce visée.</li>
          <li>Elle réorganise vos missions réelles pour mettre en avant celles qui résonnent le plus avec le besoin du recruteur.</li>
          <li>Vous choisissez votre modèle visuel (Moderne, Classique, Minimaliste) et votre couleur d'accentuation.</li>
          <li>Vous pouvez prévisualiser et exporter le résultat final en <strong className="text-white">PDF imprimable</strong> conforme aux standards des ATS (Applicant Tracking Systems).</li>
        </ul>
      </div>
    ),
  },
  {
    id: "generation-letter",
    category: "generation",
    question: "Comment sont générées les lettres de motivation (Voice DNA) ?",
    summary: "Une lettre sobre et percutante respectant les normes françaises et votre style d'écriture.",
    content: (
      <div className="space-y-3 text-slate-300">
        <p>
          Fini les lettres génériques qui commencent par des formules creuses ou des superlatifs artificiels. Le générateur de MonSuiviJob applique une méthodologie éprouvée :
        </p>
        <ul className="list-disc pl-5 space-y-1">
          <li><strong className="text-white">Recherche entreprise :</strong> analyse de la culture et des projets publics de l'entreprise cible.</li>
          <li><strong className="text-white">Voice DNA personnel :</strong> vous pouvez renseigner dans votre profil des extraits de vos vrais écrits pour que l'IA adopte votre ton naturel.</li>
          <li><strong className="text-white">Normes françaises :</strong> accroche sobre et directe, argumentation concrète basée sur vos projets, et formule de politesse soignée.</li>
        </ul>
      </div>
    ),
  },
  {
    id: "kanban-tracking",
    category: "kanban",
    question: "Comment suivre ses candidatures et démarches (France Travail) ?",
    summary: "Un tableau Kanban intuitif pour suivre vos statuts, relances et justificatifs de recherche d'emploi.",
    content: (
      <div className="space-y-3 text-slate-300">
        <p>
          Sur la page <Link href="/applications" className="text-blue-400 underline hover:text-blue-300">Mes candidatures</Link>, vous disposez d'un tableau Kanban visuel :
        </p>
        <ul className="list-disc pl-5 space-y-1">
          <li>Déplacez vos candidatures d'une colonne à l'autre (<em>À postuler &gt; En étude &gt; Entretien &gt; Offre reçue / Refusée</em>).</li>
          <li>Consignez chaque interaction (date d'envoi, contacts RH, retours d'entretiens).</li>
          <li>Les démarches enregistrées dans <Link href="/tasks" className="text-blue-400 underline hover:text-blue-300">Mes démarches</Link> vous fournissent un historique complet et daté pour vos bilans d'actualisation France Travail.</li>
        </ul>
      </div>
    ),
  },
];

const CATEGORIES = [
  { id: "all", label: "Toutes les questions", icon: FiHelpCircle },
  { id: "airflow", label: "Veille & Airflow (CRONs)", icon: FiCpu },
  { id: "profile", label: "Profil Multi-Sources & VLM", icon: FiUserCheck },
  { id: "matching", label: "Matching IA & Scores", icon: FiSliders },
  { id: "generation", label: "Génération CV & Lettres", icon: FiFileText },
  { id: "kanban", label: "Suivi & Démarches", icon: FiBriefcase },
];

export default function GuidePage() {
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [openItems, setOpenItems] = useState<Record<string, boolean>>({
    "airflow-sources": true,
    "profile-multisource": true,
  });

  const toggleItem = (id: string) => {
    setOpenItems((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const filteredItems = FAQ_ITEMS.filter((item) => {
    const matchesCategory =
      selectedCategory === "all" || item.category === selectedCategory;
    const query = searchQuery.trim().toLowerCase();
    const matchesSearch =
      !query ||
      item.question.toLowerCase().includes(query) ||
      item.summary.toLowerCase().includes(query);
    return matchesCategory && matchesSearch;
  });

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 py-10 px-4 sm:px-6 lg:px-8">
      <div className="max-w-5xl mx-auto space-y-10">
        {/* En-tête de la page */}
        <div className="text-center space-y-4">
          <div className="inline-flex items-center gap-2 bg-blue-500/10 border border-blue-500/20 px-3 py-1 rounded-full text-blue-400 text-xs font-semibold">
            <FiBookOpen className="text-sm" />
            <span>Guide d'utilisation & FAQ MonSuiviJob</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white">
            Comment fonctionne votre assistant d'emploi ?
          </h1>
          <p className="text-slate-400 max-w-2xl mx-auto text-sm sm:text-base leading-relaxed">
            Retrouvez toutes les explications sur la collecte automatique d'offres (Airflow),
            la synchronisation multi-sources avec vision IA (VLM) et la préparation de vos candidatures.
          </p>
        </div>

        {/* Barre de recherche */}
        <div className="relative max-w-xl mx-auto">
          <FiSearch className="absolute left-4 top-3.5 text-slate-400 text-lg" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Rechercher une question, mot-clé (Airflow, VLM, veille, CV, diplômes...)..."
            className="w-full bg-slate-900/90 border border-slate-800 rounded-xl pl-11 pr-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all shadow-inner"
          />
        </div>

        {/* Filtres par catégorie */}
        <div className="flex flex-wrap items-center justify-center gap-2">
          {CATEGORIES.map((cat) => {
            const Icon = cat.icon;
            const isSelected = selectedCategory === cat.id;
            return (
              <button
                key={cat.id}
                onClick={() => setSelectedCategory(cat.id)}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-medium transition-all ${
                  isSelected
                    ? "bg-blue-600 text-white shadow-md shadow-blue-500/20"
                    : "bg-slate-900/80 text-slate-400 hover:text-slate-200 hover:bg-slate-800 border border-slate-800/80"
                }`}
              >
                <Icon className={isSelected ? "text-white" : "text-slate-400"} />
                <span>{cat.label}</span>
              </button>
            );
          })}
        </div>

        {/* Liste des questions / réponses */}
        <div className="space-y-4">
          {filteredItems.length === 0 ? (
            <div className="text-center py-12 bg-slate-900/40 rounded-2xl border border-slate-800/60 p-8">
              <FiAlertCircle className="mx-auto text-3xl text-slate-500 mb-3" />
              <p className="text-slate-300 font-medium">Aucun résultat ne correspond à votre recherche.</p>
              <button
                onClick={() => {
                  setSelectedCategory("all");
                  setSearchQuery("");
                }}
                className="mt-3 text-xs text-blue-400 hover:underline"
              >
                Réinitialiser les filtres
              </button>
            </div>
          ) : (
            filteredItems.map((item) => {
              const isOpen = !!openItems[item.id];
              return (
                <div
                  key={item.id}
                  className="bg-slate-900/70 border border-slate-800 rounded-xl overflow-hidden transition-all hover:border-slate-700/80 shadow-sm"
                >
                  <button
                    type="button"
                    onClick={() => toggleItem(item.id)}
                    className="w-full px-5 py-4 text-left flex items-start justify-between gap-4 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                  >
                    <div className="space-y-1">
                      <h2 className="text-base sm:text-lg font-bold text-white tracking-tight flex items-center gap-2">
                        <span>{item.question}</span>
                      </h2>
                      <p className="text-xs text-slate-400 font-normal">
                        {item.summary}
                      </p>
                    </div>
                    <div className="p-1 text-slate-400 hover:text-white transition-colors shrink-0 mt-1">
                      {isOpen ? (
                        <FiChevronUp className="w-5 h-5" />
                      ) : (
                        <FiChevronDown className="w-5 h-5" />
                      )}
                    </div>
                  </button>

                  {isOpen && (
                    <div className="px-5 pb-5 pt-1 text-sm border-t border-slate-800/60 mt-1">
                      {item.content}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Accès rapides utiles en bas de page */}
        <div className="bg-gradient-to-r from-blue-950/40 via-slate-900/60 to-indigo-950/40 p-6 rounded-2xl border border-blue-900/30 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>
            <h3 className="text-base font-bold text-white mb-1">Prêt à configurer vos recherches ?</h3>
            <p className="text-xs text-slate-400">
              Définissez vos critères de ciblage ou importez votre CV pour lancer votre veille personnalisée.
            </p>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <Link
              href="/profile"
              className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg text-xs font-semibold shadow-md transition-colors flex items-center gap-1.5"
            >
              <span>Mon Profil & Ciblage</span>
              <FiArrowRight />
            </Link>
            <Link
              href="/offers"
              className="bg-slate-800 hover:bg-slate-700 text-slate-200 px-4 py-2 rounded-lg text-xs font-semibold transition-colors"
            >
              Voir les offres
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
