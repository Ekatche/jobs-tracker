"use client";

import React from "react";
import { coverLetterApi } from "@/lib/api";
import { CandidateProfile } from "@/types/coverLetter";
import { ImportSourceName } from "@/hooks/useCandidateProfile";
import {
  FiGlobe,
  FiGithub,
  FiLinkedin,
  FiMail,
  FiPhone,
  FiTruck,
  FiCalendar,
  FiCode,
  FiHeart,
} from "react-icons/fi";

interface ProfileCoreEditFieldsProps {
  headline: string;
  summary: string;
  writingStyle: string;
  writingSamples: string;
  website: string;
  github: string;
  linkedin: string;
  email: string;
  phone: string;
  mobility: string;
  availability: string;
  skillsText: string;
  languagesText: string;
  interestsText: string;
  busySource: ImportSourceName | null;
  onFieldChange: (field: string, value: string) => void;
  onRunImport: (source: ImportSourceName, call: () => Promise<CandidateProfile>) => void;
}

/**
 * Core identity, Voice DNA, contact links, skills, languages, and interests form inputs.
 */
export function ProfileCoreEditFields({
  headline,
  summary,
  writingStyle,
  writingSamples,
  website,
  github,
  linkedin,
  email,
  phone,
  mobility,
  availability,
  skillsText,
  languagesText,
  interestsText,
  busySource,
  onFieldChange,
  onRunImport,
}: ProfileCoreEditFieldsProps) {
  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label htmlFor="candidate_headline" className="block text-xs font-semibold text-gray-300 uppercase mb-1">
            Titre professionnel (Headline)
          </label>
          <input
            id="candidate_headline"
            type="text"
            value={headline}
            onChange={(e) => onFieldChange("headline", e.target.value)}
            placeholder="ex: Développeur Fullstack, Chef de Projet, Designer UI/UX, Consultant..."
            className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label htmlFor="candidate_website" className="block text-xs font-semibold text-gray-300 uppercase mb-1 flex items-center">
            <FiGlobe className="mr-1.5 text-blue-400" /> Site Web / Portfolio
          </label>
          <div className="flex gap-2">
            <input
              id="candidate_website"
              type="text"
              value={website}
              onChange={(e) => onFieldChange("website", e.target.value)}
              placeholder="https://mon-portfolio.dev"
              className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              type="button"
              onClick={() => onRunImport("website", () => coverLetterApi.importWebsite(website))}
              disabled={busySource !== null || !website}
              className="flex items-center shrink-0 px-3 py-1.5 rounded-md text-xs font-medium bg-purple-600/20 text-purple-300 border border-purple-500/30 hover:bg-purple-600/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {busySource === "website" ? (
                <span className="w-3.5 h-3.5 border-2 border-purple-300 border-t-transparent rounded-full animate-spin" />
              ) : (
                "Importer"
              )}
            </button>
          </div>
        </div>
      </div>

      <div>
        <label htmlFor="candidate_summary" className="block text-xs font-semibold text-gray-300 uppercase mb-1">
          Résumé / Bio (contexte de parcours pour l&apos;IA)
        </label>
        <textarea
          id="candidate_summary"
          rows={4}
          value={summary}
          onChange={(e) => onFieldChange("summary", e.target.value)}
          placeholder="Présentation synthétique de votre expertise, points forts et domaines de prédilection..."
          className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <div>
        <label htmlFor="candidate_writing_style" className="block text-xs font-semibold text-gray-300 uppercase mb-1 flex items-center justify-between">
          <span>Style d&apos;écriture personnel (Voice DNA)</span>
          <span className="text-[10px] normal-case text-gray-400 font-normal">
            guide le ton et le style des lettres de motivation générées
          </span>
        </label>
        <textarea
          id="candidate_writing_style"
          rows={3}
          value={writingStyle}
          onChange={(e) => onFieldChange("writingStyle", e.target.value)}
          placeholder="ex: Style direct et sobre, phrases courtes et percutantes, orienté résultats chiffrés, voix active, zéro flatterie générique..."
          className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 text-xs sm:text-sm"
        />
      </div>

      <div>
        <label htmlFor="candidate_writing_samples" className="block text-xs font-semibold text-gray-300 uppercase mb-1 flex items-center justify-between">
          <span>Lettres d&apos;exemple</span>
          <span className="text-[10px] normal-case text-gray-400 font-normal">
            2 ou 3 lettres écrites par vous : seul le style est imité, jamais le contenu
          </span>
        </label>
        <textarea
          id="candidate_writing_samples"
          rows={8}
          value={writingSamples}
          onChange={(e) => onFieldChange("writingSamples", e.target.value)}
          placeholder="Collez ici vos lettres de motivation, séparées par une ligne vide..."
          className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 text-xs sm:text-sm"
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        <div>
          <label htmlFor="candidate_github" className="block text-xs font-medium text-gray-300 mb-1 flex items-center">
            <FiGithub className="mr-1.5" /> GitHub
          </label>
          <div className="flex gap-2">
            <input
              id="candidate_github"
              type="text"
              value={github}
              onChange={(e) => onFieldChange("github", e.target.value)}
              placeholder="https://github.com/moncompte"
              className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              type="button"
              onClick={() => onRunImport("github", () => coverLetterApi.importGithub(github))}
              disabled={busySource !== null || !github}
              className="flex items-center shrink-0 px-3 py-1.5 rounded-md text-xs font-medium bg-purple-600/20 text-purple-300 border border-purple-500/30 hover:bg-purple-600/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {busySource === "github" ? (
                <span className="w-3.5 h-3.5 border-2 border-purple-300 border-t-transparent rounded-full animate-spin" />
              ) : (
                "Importer"
              )}
            </button>
          </div>
        </div>

        <div>
          <label htmlFor="candidate_linkedin" className="block text-xs font-medium text-gray-300 mb-1 flex items-center justify-between">
            <span className="flex items-center">
              <FiLinkedin className="mr-1.5 text-blue-400" /> LinkedIn
            </span>
            <span className="text-[10px] normal-case text-gray-500 italic">affiché sur votre profil, non importé</span>
          </label>
          <input
            id="candidate_linkedin"
            type="text"
            value={linkedin}
            onChange={(e) => onFieldChange("linkedin", e.target.value)}
            placeholder="https://linkedin.com/in/moncompte"
            className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {[
          { id: "candidate_email", field: "email", label: "Email contact", type: "email", val: email, ph: "contact@exemple.com", icon: <FiMail className="mr-1.5" /> },
          { id: "candidate_phone", field: "phone", label: "Téléphone", type: "text", val: phone, ph: "+33 6 ...", icon: <FiPhone className="mr-1.5" /> },
          { id: "candidate_mobility", field: "mobility", label: "Mobilité", type: "text", val: mobility, ph: "Permis B, véhiculé", icon: <FiTruck className="mr-1.5" /> },
          { id: "candidate_availability", field: "availability", label: "Disponibilités", type: "text", val: availability, ph: "Disponible immédiatement · 2x8, nuit, week-end", icon: <FiCalendar className="mr-1.5" /> },
        ].map((item) => (
          <div key={item.id}>
            <label htmlFor={item.id} className="block text-xs font-medium text-gray-300 mb-1 flex items-center">
              {item.icon} {item.label}
            </label>
            <input
              id={item.id}
              type={item.type}
              value={item.val}
              onChange={(e) => onFieldChange(item.field, e.target.value)}
              placeholder={item.ph}
              className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        ))}
      </div>

      <div>
        <label htmlFor="candidate_skills" className="block text-xs font-semibold text-gray-300 uppercase mb-1 flex items-center">
          <FiCode className="mr-1.5 text-blue-400" /> Compétences (Format libre &ldquo;catégorie: item1, item2&rdquo;)
        </label>
        <textarea
          id="candidate_skills"
          rows={4}
          value={skillsText}
          onChange={(e) => onFieldChange("skillsText", e.target.value)}
          placeholder="compétences clés: Gestion de projet, Communication, Négociation&#10;outils: Excel, Figma, Notion, Git&#10;méthodologies: Agile, Scrum, Lean"
          className="w-full font-mono text-xs rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label htmlFor="candidate_languages" className="block text-xs font-semibold text-gray-300 uppercase mb-1 flex items-center">
            <FiGlobe className="mr-1.5 text-cyan-400" /> Langues maîtrisées (séparées par virgule)
          </label>
          <input
            id="candidate_languages"
            type="text"
            value={languagesText}
            onChange={(e) => onFieldChange("languagesText", e.target.value)}
            placeholder="ex: Français (natif), Anglais (courant C1), Espagnol"
            className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 text-xs sm:text-sm"
          />
        </div>

        <div>
          <label htmlFor="candidate_interests" className="block text-xs font-semibold text-gray-300 uppercase mb-1 flex items-center">
            <FiHeart className="mr-1.5 text-rose-400" /> Centres d&apos;intérêt & Engagements (séparés par virgule)
          </label>
          <input
            id="candidate_interests"
            type="text"
            value={interestsText}
            onChange={(e) => onFieldChange("interestsText", e.target.value)}
            placeholder="ex: Course à pied, Échecs, Bénévolat associatif, Photographie"
            className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 text-xs sm:text-sm"
          />
        </div>
      </div>
    </>
  );
}
