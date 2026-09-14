"use client";

import React, { useState, useEffect } from "react";
import {
  FiFileText,
  FiBriefcase,
  FiGlobe,
  FiGithub,
  FiLinkedin,
  FiMail,
  FiPhone,
  FiSave,
  FiEdit2,
  FiCheckCircle,
  FiAlertCircle,
  FiLayers,
  FiCode,
} from "react-icons/fi";
import { coverLetterApi } from "@/lib/api";
import { CandidateProfile, CandidateExperience, CandidateProject, CandidateConflict } from "@/types/coverLetter";

export default function CandidateProfileSection() {
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Form states
  const [headline, setHeadline] = useState("");
  const [summary, setSummary] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [website, setWebsite] = useState("");
  const [github, setGithub] = useState("");
  const [linkedin, setLinkedin] = useState("");
  const [skillsText, setSkillsText] = useState("");
  const [experiences, setExperiences] = useState<CandidateExperience[]>([]);
  const [projects, setProjects] = useState<CandidateProject[]>([]);

  const loadProfile = async () => {
    setLoading(true);
    setSaveError(null);
    try {
      const data = await coverLetterApi.getCandidateProfile();
      if (data) {
        setProfile(data);
        populateForm(data);
      }
    } catch {
      // Profil non encore initialisé en base
      setProfile(null);
    } finally {
      setLoading(false);
    }
  };

  const populateForm = (data: CandidateProfile) => {
    setHeadline(data.headline || "");
    setSummary(data.summary || "");
    setEmail(data.contact?.email || "");
    setPhone(data.contact?.phone || "");
    setWebsite(data.contact?.website || "");
    setGithub(data.contact?.github || "");
    setLinkedin(data.contact?.linkedin || "");

    // Aplatir les compétences pour édition simplifiée
    if (data.skills) {
      const allSkills: string[] = [];
      Object.entries(data.skills).forEach(([category, list]) => {
        allSkills.push(`${category}: ${list.join(", ")}`);
      });
      setSkillsText(allSkills.join("\n"));
    } else {
      setSkillsText("");
    }

    setExperiences(data.experiences || []);
    setProjects(data.projects || []);
  };

  useEffect(() => {
    loadProfile();
  }, []);

  type SourceName = "cv" | "github" | "website";

  const [busySource, setBusySource] = useState<SourceName | null>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const runImport = async (source: SourceName, call: () => Promise<CandidateProfile>) => {
    setBusySource(source);
    setSaveError(null);
    try {
      const updated = await call();
      setProfile(updated);
      populateForm(updated);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 4000);
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : `Échec de l'import ${source}`);
    } finally {
      setBusySource(null);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    await runImport("cv", () => coverLetterApi.importCv(file));
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setSaveSuccess(false);
    setSaveError(null);

    // Reconstruire l'objet skills
    const parsedSkills: Record<string, string[]> = {};
    if (skillsText.trim()) {
      const lines = skillsText.split("\n");
      lines.forEach((line) => {
        const parts = line.split(":");
        if (parts.length === 2) {
          const category = parts[0].trim().toLowerCase();
          const items = parts[1]
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean);
          if (category && items.length > 0) {
            parsedSkills[category] = items;
          }
        } else if (line.trim()) {
          const defaultCat = "principales";
          const items = line
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean);
          parsedSkills[defaultCat] = [...(parsedSkills[defaultCat] || []), ...items];
        }
      });
    }

    const updatedProfile: Partial<CandidateProfile> = {
      headline,
      summary,
      contact: {
        email,
        phone,
        website,
        github,
        linkedin,
      },
      skills: Object.keys(parsedSkills).length > 0 ? parsedSkills : profile?.skills || {},
      experiences,
      projects,
      education: profile?.education || [],
      certifications: profile?.certifications || [],
      languages: profile?.languages || ["Français", "Anglais"],
    };

    try {
      const saved = await coverLetterApi.updateCandidateProfile(updatedProfile);
      setProfile(saved);
      populateForm(saved);
      setIsEditing(false);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 4000);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Erreur lors de l'enregistrement du profil candidat";
      setSaveError(message);
    } finally {
      setIsSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-blue-night-lighter rounded-lg shadow-lg p-6 mb-8 border border-gray-800 animate-pulse">
        <div className="h-6 bg-gray-700/50 rounded w-1/3 mb-4"></div>
        <div className="h-4 bg-gray-700/30 rounded w-2/3 mb-2"></div>
        <div className="h-4 bg-gray-700/30 rounded w-1/2"></div>
      </div>
    );
  }

  return (
    <div className="bg-blue-night-lighter rounded-lg shadow-lg p-6 mb-8 border border-gray-800">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-semibold text-white flex items-center">
              <FiFileText className="mr-2 text-blue-400" /> Profil Candidat & IA
            </h2>
            {profile ? (
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-900/50 text-green-300 border border-green-700/50">
                <FiCheckCircle className="mr-1" /> Prêt pour les lettres
              </span>
            ) : (
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-900/50 text-amber-300 border border-amber-700/50">
                <FiAlertCircle className="mr-1" /> Profil non initialisé
              </span>
            )}
          </div>
          <p className="text-sm text-gray-400 mt-1">
            Ces informations sont utilisées par l'agent IA pour contextualiser et rédiger vos lettres de motivation.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row gap-2">
          <input
            type="file"
            accept="application/pdf"
            className="hidden"
            ref={fileInputRef}
            onChange={handleFileUpload}
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={busySource !== null}
            className="flex items-center px-3.5 py-1.5 rounded-md text-sm font-medium bg-emerald-600/20 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-600/30 transition-colors disabled:opacity-50"
          >
            {busySource === "cv" ? (
              <span className="w-4 h-4 mr-1.5 border-2 border-emerald-300 border-t-transparent rounded-full animate-spin"></span>
            ) : (
              <FiFileText className="mr-1.5" />
            )}
            Importer mon CV
          </button>

          <button
            type="button"
            onClick={() => setIsEditing(!isEditing)}
            className="flex items-center self-start md:self-auto px-3.5 py-1.5 rounded-md text-sm font-medium bg-blue-600/20 text-blue-300 border border-blue-500/30 hover:bg-blue-600/30 transition-colors"
          >
            <FiEdit2 className="mr-1.5" />
            {isEditing ? "Annuler l'édition" : "Modifier le profil"}
          </button>
        </div>
      </div>

      {saveSuccess && (
        <div className="bg-green-900/40 border border-green-600 text-green-200 p-3 rounded-md mb-5 text-sm flex items-center">
          <FiCheckCircle className="mr-2 text-green-400 shrink-0" />
          Profil candidat enregistré avec succès ! L'IA utilisera ces informations à jour.
        </div>
      )}

      {saveError && (
        <div className="bg-red-900/40 border border-red-600 text-red-200 p-3 rounded-md mb-5 text-sm flex items-center">
          <FiAlertCircle className="mr-2 text-red-400 shrink-0" />
          {saveError}
        </div>
      )}

      {!isEditing ? (
        // Mode Affichage / Consultation
        <div className="space-y-6 text-sm">
          {/* Headline & Summary */}
          <div className="bg-blue-night/60 p-4 rounded-lg border border-gray-800/80">
            <h3 className="text-xs uppercase tracking-wider font-semibold text-gray-400 mb-1">
              Titre & Résumé
            </h3>
            <div className="text-base font-medium text-white mb-2">
              {profile?.headline || "Titre non renseigné"}
            </div>
            <p className="text-gray-300 leading-relaxed whitespace-pre-line">
              {profile?.summary || "Aucun résumé professionnel enregistré."}
            </p>
          </div>

          {/* Contact & Liens (Website, GitHub, LinkedIn, etc.) */}
          <div className="bg-blue-night/60 p-4 rounded-lg border border-gray-800/80">
            <h3 className="text-xs uppercase tracking-wider font-semibold text-gray-400 mb-3">
              Coordonnées & Liens web
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              <div className="flex items-center text-gray-300">
                <FiGlobe className="mr-2 text-blue-400 shrink-0" />
                <span className="text-gray-400 mr-2">Site Web :</span>
                {profile?.contact?.website ? (
                  <a
                    href={profile.contact.website.startsWith("http") ? profile.contact.website : `https://${profile.contact.website}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-400 hover:underline truncate"
                  >
                    {profile.contact.website}
                  </a>
                ) : (
                  <span className="text-gray-500 italic">Non renseigné</span>
                )}
              </div>

              <div className="flex items-center text-gray-300">
                <FiGithub className="mr-2 text-gray-300 shrink-0" />
                <span className="text-gray-400 mr-2">GitHub :</span>
                {profile?.contact?.github ? (
                  <a
                    href={profile.contact.github.startsWith("http") ? profile.contact.github : `https://${profile.contact.github}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-400 hover:underline truncate"
                  >
                    {profile.contact.github}
                  </a>
                ) : (
                  <span className="text-gray-500 italic">Non renseigné</span>
                )}
              </div>

              <div className="flex items-center text-gray-300">
                <FiLinkedin className="mr-2 text-blue-500 shrink-0" />
                <span className="text-gray-400 mr-2">LinkedIn :</span>
                {profile?.contact?.linkedin ? (
                  <a
                    href={profile.contact.linkedin.startsWith("http") ? profile.contact.linkedin : `https://${profile.contact.linkedin}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-400 hover:underline truncate"
                  >
                    {profile.contact.linkedin}
                  </a>
                ) : (
                  <span className="text-gray-500 italic">Non renseigné</span>
                )}
              </div>

              <div className="flex items-center text-gray-300">
                <FiMail className="mr-2 text-gray-400 shrink-0" />
                <span className="text-gray-400 mr-2">Email :</span>
                <span className="truncate">{profile?.contact?.email || "Non renseigné"}</span>
              </div>

              <div className="flex items-center text-gray-300">
                <FiPhone className="mr-2 text-gray-400 shrink-0" />
                <span className="text-gray-400 mr-2">Tél :</span>
                <span>{profile?.contact?.phone || "Non renseigné"}</span>
              </div>
            </div>
          </div>

          {/* Compétences */}
          {profile?.skills && Object.keys(profile.skills).length > 0 && (
            <div className="bg-blue-night/60 p-4 rounded-lg border border-gray-800/80">
              <h3 className="text-xs uppercase tracking-wider font-semibold text-gray-400 mb-3 flex items-center">
                <FiCode className="mr-2 text-blue-400" /> Compétences structurées
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {Object.entries(profile.skills).map(([category, items]) => (
                  <div key={category} className="bg-blue-night-lighter/50 p-2.5 rounded border border-gray-800">
                    <span className="text-xs font-semibold uppercase text-blue-400">{category}</span>
                    <div className="flex flex-wrap gap-1.5 mt-1.5">
                      {items.map((skill, i) => (
                        <span key={i} className="px-2 py-0.5 rounded text-xs bg-gray-800 text-gray-200 border border-gray-700">
                          {skill}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Expériences */}
          {profile?.experiences && profile.experiences.length > 0 && (
            <div className="bg-blue-night/60 p-4 rounded-lg border border-gray-800/80">
              <h3 className="text-xs uppercase tracking-wider font-semibold text-gray-400 mb-3 flex items-center">
                <FiBriefcase className="mr-2 text-blue-400" /> Expériences clés ({profile.experiences.length})
              </h3>
              {profile?.conflicts && profile.conflicts.length > 0 && (
                <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200 mb-3">
                  <p className="font-medium mb-1">
                    Divergences entre vos sources ({profile.conflicts.length})
                  </p>
                  <ul className="space-y-1">
                    {profile.conflicts.map((c: CandidateConflict, i) => (
                      <li key={i}>
                        {c.company} — {c.field} : « {String(c.kept)} » retenu depuis {c.kept_source},
                        « {String(c.discarded)} » écarté depuis {c.discarded_source}.
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="space-y-3">
                {profile.experiences.map((exp, idx) => (
                  <div key={idx} className="bg-blue-night-lighter/50 p-3 rounded border border-gray-800">
                    <div className="flex justify-between items-start">
                      <div>
                        <span className="font-semibold text-white">{exp.role}</span>
                        <span className="text-blue-400 mx-1.5">@</span>
                        <span className="text-gray-300 font-medium">{exp.company}</span>
                      </div>
                      <span className="text-xs text-gray-400 bg-gray-800 px-2 py-0.5 rounded">
                        {exp.start} — {exp.end || "Présent"}
                      </span>
                    </div>
                    {exp.missions && exp.missions.length > 0 && (
                      <ul className="mt-2 list-disc list-inside space-y-1 text-xs text-gray-300">
                        {exp.missions.slice(0, 3).map((m, mIdx) => (
                          <li key={mIdx} className="leading-snug">{m}</li>
                        ))}
                      </ul>
                    )}
                    {exp.stack && exp.stack.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {exp.stack.map((s, sIdx) => (
                          <span key={sIdx} className="text-[10px] bg-blue-900/30 text-blue-300 border border-blue-700/30 px-1.5 py-0.5 rounded">
                            {s}
                          </span>
                        ))}
                      </div>
                    )}
                    {exp.sources && exp.sources.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {exp.sources.map((s, sIdx) => (
                          <span key={sIdx} className="text-[10px] bg-emerald-900/30 text-emerald-300 border border-emerald-700/30 px-1.5 py-0.5 rounded">
                            {s}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Projets */}
          {profile?.projects && profile.projects.length > 0 && (
            <div className="bg-blue-night/60 p-4 rounded-lg border border-gray-800/80">
              <h3 className="text-xs uppercase tracking-wider font-semibold text-gray-400 mb-3 flex items-center">
                <FiLayers className="mr-2 text-blue-400" /> Projets personnels & réalisations
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {profile.projects.map((proj, idx) => (
                  <div key={idx} className="bg-blue-night-lighter/50 p-3 rounded border border-gray-800">
                    <div className="font-medium text-white">{proj.name}</div>
                    <p className="text-xs text-gray-400 mt-1">{proj.description}</p>
                    {proj.url && (
                      <a
                        href={proj.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-blue-400 hover:underline mt-2 inline-block"
                      >
                        Voir le projet →
                      </a>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        // Mode Édition
        <form onSubmit={handleSave} className="space-y-4 text-sm">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="candidate_headline" className="block text-xs font-semibold text-gray-300 uppercase mb-1">
                Titre professionnel (Headline)
              </label>
              <input
                id="candidate_headline"
                type="text"
                value={headline}
                onChange={(e) => setHeadline(e.target.value)}
                placeholder="ex: Ingénieur Data & IA"
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
                  onChange={(e) => setWebsite(e.target.value)}
                  placeholder="https://mon-portfolio.dev"
                  className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button
                  type="button"
                  onClick={() => runImport("website", () => coverLetterApi.importWebsite(website))}
                  disabled={busySource !== null || !website}
                  className="flex items-center shrink-0 px-3 py-1.5 rounded-md text-xs font-medium bg-purple-600/20 text-purple-300 border border-purple-500/30 hover:bg-purple-600/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {busySource === "website" ? (
                    <span className="w-3.5 h-3.5 border-2 border-purple-300 border-t-transparent rounded-full animate-spin"></span>
                  ) : (
                    "Importer"
                  )}
                </button>
              </div>
            </div>
          </div>

          <div>
            <label htmlFor="candidate_summary" className="block text-xs font-semibold text-gray-300 uppercase mb-1">
              Résumé / Bio (contexte de parcours pour l'IA)
            </label>
            <textarea
              id="candidate_summary"
              rows={4}
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              placeholder="Présentation synthétique de votre expertise, points forts et domaines de prédilection..."
              className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
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
                  onChange={(e) => setGithub(e.target.value)}
                  placeholder="https://github.com/moncompte"
                  className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button
                  type="button"
                  onClick={() => runImport("github", () => coverLetterApi.importGithub(github))}
                  disabled={busySource !== null || !github}
                  className="flex items-center shrink-0 px-3 py-1.5 rounded-md text-xs font-medium bg-purple-600/20 text-purple-300 border border-purple-500/30 hover:bg-purple-600/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {busySource === "github" ? (
                    <span className="w-3.5 h-3.5 border-2 border-purple-300 border-t-transparent rounded-full animate-spin"></span>
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
                onChange={(e) => setLinkedin(e.target.value)}
                placeholder="https://linkedin.com/in/moncompte"
                className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label htmlFor="candidate_email" className="block text-xs font-medium text-gray-300 mb-1 flex items-center">
                <FiMail className="mr-1.5" /> Email contact
              </label>
              <input
                id="candidate_email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="contact@exemple.com"
                className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label htmlFor="candidate_phone" className="block text-xs font-medium text-gray-300 mb-1 flex items-center">
                <FiPhone className="mr-1.5" /> Téléphone
              </label>
              <input
                id="candidate_phone"
                type="text"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+33 6 ..."
                className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <div>
            <label htmlFor="candidate_skills" className="block text-xs font-semibold text-gray-300 uppercase mb-1 flex items-center">
              <FiCode className="mr-1.5 text-blue-400" /> Compétences (Format "catégorie: item1, item2")
            </label>
            <textarea
              id="candidate_skills"
              rows={4}
              value={skillsText}
              onChange={(e) => setSkillsText(e.target.value)}
              placeholder="langages: Python, JavaScript, SQL&#10;cloud: Azure, AWS&#10;frameworks: FastAPI, LangChain"
              className="w-full font-mono text-xs rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={() => {
                if (profile) populateForm(profile);
                setIsEditing(false);
              }}
              className="px-4 py-2 rounded-md text-gray-400 hover:text-white border border-gray-700 hover:bg-gray-800 transition-colors"
            >
              Annuler
            </button>
            <button
              type="submit"
              disabled={isSaving}
              className="flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-md transition-colors disabled:opacity-50"
            >
              <FiSave className="mr-2" />
              {isSaving ? "Enregistrement..." : "Enregistrer le profil candidat"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
