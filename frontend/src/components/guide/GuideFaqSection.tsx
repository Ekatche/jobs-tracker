"use client";

import React, { useState } from "react";
import { FiSearch, FiHelpCircle, FiChevronDown, FiChevronUp } from "react-icons/fi";

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
    summary:
      "Airflow interroge chaque jour Indeed, LinkedIn, HelloWork, les job boards spécialisés et les sites carrières via Tavily AI.",
    content: (
      <div className="space-y-2 text-slate-300 text-sm">
        <p>Les pipelines automatisés (DAGs) regroupent 4 sources complémentaires :</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1 text-xs">
          <div className="bg-slate-900/90 p-2.5 rounded-lg border border-slate-800">
            <span className="font-semibold text-blue-400 block mb-0.5">🧭 Job boards spécialisés</span>
            Welcome to the Jungle, Apec, Cadremploi et Free-Work, interrogés chaque matin en semaine.
          </div>
          <div className="bg-slate-900/90 p-2.5 rounded-lg border border-slate-800">
            <span className="font-semibold text-indigo-400 block mb-0.5">
              💼 Indeed, LinkedIn &amp; HelloWork
            </span>
            Collecte et normalisation des offres des principales plateformes pro.
          </div>
          <div className="bg-slate-900/90 p-2.5 rounded-lg border border-slate-800">
            <span className="font-semibold text-purple-400 block mb-0.5">
              ⚡ Connecteurs ATS Zero-Token &amp; Tavily
            </span>
            Extraction directe sans coût LLM sur Ashby, Workday CXS, Greenhouse, Lever et
            SmartRecruiters durci.
          </div>
          <div className="bg-slate-900/90 p-2.5 rounded-lg border border-slate-800">
            <span className="font-semibold text-emerald-400 block mb-0.5">
              🛡️ Filtre Anti-Bruit &amp; Non-Contenu
            </span>
            Élimination instantanée des doublons, murs de connexion, coquilles 404, paywalls et offres
            expirées.
          </div>
        </div>
      </div>
    ),
  },
  {
    id: "airflow-targeting",
    category: "airflow",
    question: "Comment le moteur sait-il quelles offres vous envoyer ?",
    summary:
      "La collecte lit directement vos critères définis dans l'onglet Profil (intitulés, villes, contrats).",
    content: (
      <div className="space-y-2 text-slate-300 text-sm">
        <p>
          Le système ne fait aucune recherche générique au hasard : il convertit vos critères de
          ciblage en requêtes de recherche spécialisées.
        </p>
        <ul className="list-disc pl-5 space-y-1 text-xs text-slate-400">
          <li>
            Vos <strong>intitulés ciblés</strong> (ex. <em>Data Scientist, Dev Fullstack</em>)
          </li>
          <li>
            Vos <strong>localisations et tolérance télétravail</strong> (ex.{" "}
            <em>Lyon, Télétravail partiel ou 100%</em>)
          </li>
          <li>
            Vos <strong>types de contrats</strong> retenus (CDI, CDD, Freelance, Alternance)
          </li>
        </ul>
      </div>
    ),
  },
  {
    id: "profile-vlm",
    category: "profile",
    question: "Pourquoi l'IA de vision (VLM) est-elle supérieure à un simple lecteur de PDF ?",
    summary:
      "Elle analyse visuellement votre CV pour ne pas mélanger les colonnes, dates et compétences.",
    content: (
      <div className="space-y-2 text-slate-300 text-sm">
        <p>
          Les parseurs traditionnels lisent de gauche à droite et mélangent le texte des barres
          latérales avec le texte principal.
        </p>
        <p className="text-xs text-slate-400">
          Notre <strong>modèle de vision Mistral</strong> « regarde » chaque page comme un humain :
          il identifie chaque bloc visuel, préserve la chronologie des postes et associe fidèlement
          vos compétences à leurs expériences.
        </p>
      </div>
    ),
  },
  {
    id: "profile-conflicts",
    category: "profile",
    question: "Que faire en cas de divergences ou doublons de diplômes ?",
    summary:
      "La saisie manuelle l'emporte toujours. Les diplômes similaires sont automatiquement rapprochés.",
    content: (
      <div className="space-y-2 text-slate-300 text-sm">
        <p>
          En cas de conflit entre deux sources (ex: libellé de contrat ou date différente),
          l&apos;arbitrage est automatique :{" "}
          <span className="font-mono text-xs text-emerald-400 ml-1 font-semibold">
            Manuel &gt; CV &gt; Site &gt; GitHub
          </span>
          .
        </p>
        <p className="text-xs text-slate-400">
          Les diplômes d&apos;une même école avec des variantes d&apos;intitulé sont fusionnés
          intelligemment pour retenir la version la plus complète. Vous pouvez masquer le bandeau des
          divergences d&apos;un simple clic.
        </p>
      </div>
    ),
  },
  {
    id: "matching-score",
    category: "matching",
    question: "Comment interpréter votre Matching Score sur une annonce ?",
    summary:
      "Une note sur 5 calculée par IA avec analyse des points forts et points de vigilance.",
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
          L&apos;analyse fournit aussi les compétences clés manquantes à mettre en avant ou à
          préparer pour votre entretien.
        </p>
      </div>
    ),
  },
  {
    id: "career-ops-tools",
    category: "generation",
    question:
      "Qu'apportent le Bloc H, le Score ATS du CV et les vues Calibration IA / Lacunes JD ?",
    summary:
      "Brouillons de réponses automatiques pour les offres >= 4.0, audit ATS 0-100 sans marqueurs invisibles et analytics pipeline.",
    content: (
      <div className="space-y-2 text-slate-300 text-xs leading-relaxed">
        <p>
          <strong className="text-blue-300">Bloc H (Offres &ge; 4.0) :</strong> génère
          automatiquement vos réponses brouillons aux questions types de candidature, les
          réalisations clés à valoriser et les écarts à anticiper.
        </p>
        <p>
          <strong className="text-emerald-300">Score ATS &amp; Export :</strong> dans Mes CV, chaque
          CV adapté reçoit une note 0–100 (grade A–D) sur 6 axes ainsi qu&apos;un export
          Markdown/Texte nettoyé de tout caractère Unicode invisible.
        </p>
        <p>
          <strong className="text-amber-300">Calibration IA &amp; Lacunes JD :</strong> comparez vos
          scores IA à vos entretiens réels depuis Suivi des Candidatures, et identifiez les
          compétences récurrentes manquantes depuis Offres d&apos;emploi.
        </p>
      </div>
    ),
  },
];

export default function GuideFaqSection() {
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
    <div className="bg-slate-900/40 border border-slate-800/80 rounded-2xl p-6 sm:p-8 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-blue-400 text-xs font-bold uppercase tracking-wider mb-1">
            <FiHelpCircle className="text-sm" />
            <span>Questions Précises</span>
          </div>
          <h2 className="text-xl sm:text-2xl font-bold text-white">FAQ &amp; Détails Techniques</h2>
        </div>

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
          <p className="text-center py-6 text-xs text-slate-400">
            Aucune question ne correspond à votre recherche.
          </p>
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
  );
}
