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
  FiExternalLink,
  FiAward,
  FiCalendar,
  FiBook,
  FiPlus,
  FiTrash2,
  FiHeart,
} from "react-icons/fi";
import { coverLetterApi } from "@/lib/api";
import { CandidateProfile, CandidateExperience, CandidateProject, CandidateConflict } from "@/types/coverLetter";
import CvDropzone from "./CvDropzone";

function formatMonthYear(val?: string | null): string {
  if (!val) return "";
  const match = val.match(/^(\d{4})(?:-(\d{2}))?$/);
  if (!match) return val;
  const year = match[1];
  const monthNum = match[2];
  if (!monthNum) return year;
  const months = [
    "Janv.", "Févr.", "Mars", "Avril", "Mai", "Juin",
    "Juil.", "Août", "Sept.", "Oct.", "Nov.", "Déc."
  ];
  const idx = parseInt(monthNum, 10) - 1;
  return idx >= 0 && idx < 12 ? `${months[idx]} ${year}` : `${monthNum}/${year}`;
}

function formatPeriod(start?: string | null, end?: string | null): string {
  const startFmt = formatMonthYear(start);
  const endFmt = end ? formatMonthYear(end) : "Présent";
  if (!startFmt && !endFmt) return "Période non renseignée";
  if (!startFmt) return `Jusqu'à ${endFmt}`;
  return `${startFmt} — ${endFmt}`;
}

export default function CandidateProfileSection() {
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Inline writing style editor (always visible, independent of full edit mode)
  const [isEditingStyle, setIsEditingStyle] = useState(false);
  const [writingStyleDraft, setWritingStyleDraft] = useState("");
  const [isSavingStyle, setIsSavingStyle] = useState(false);
  const [saveStyleSuccess, setSaveStyleSuccess] = useState(false);

  // Form states
  const [headline, setHeadline] = useState("");
  const [summary, setSummary] = useState("");
  const [writingStyle, setWritingStyle] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [website, setWebsite] = useState("");
  const [github, setGithub] = useState("");
  const [linkedin, setLinkedin] = useState("");
  const [skillsText, setSkillsText] = useState("");
  const [languagesText, setLanguagesText] = useState("");
  const [interestsText, setInterestsText] = useState("");
  const [experiences, setExperiences] = useState<CandidateExperience[]>([]);
  const [projects, setProjects] = useState<CandidateProject[]>([]);
  const [excludedProjects, setExcludedProjects] = useState<string[]>([]);

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
    setWritingStyle(data.writing_style || "");
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
    setExcludedProjects(data.excluded_projects || []);
    setLanguagesText((data.languages || []).join(", "));
    setInterestsText((data.interests || []).join(", "));
  };

  const handleUpdateExperience = (
    index: number,
    field: keyof CandidateExperience,
    value: string
  ) => {
    setExperiences((prev) => {
      const copy = [...prev];
      if (field === "stack") {
        copy[index] = {
          ...copy[index],
          stack: value.split(",").map((s) => s.trim()).filter(Boolean),
        };
      } else if (field === "missions") {
        copy[index] = {
          ...copy[index],
          missions: value
            .split("\n")
            .map((s) => s.replace(/^[•\-\*]\s*/, "").trim())
            .filter(Boolean),
        };
      } else {
        copy[index] = { ...copy[index], [field]: value };
      }
      return copy;
    });
  };

  const handleAddExperience = () => {
    setExperiences((prev) => [
      {
        role: "",
        company: "",
        start: "",
        end: "",
        location: "",
        missions: [],
        stack: [],
      },
      ...prev,
    ]);
  };

  const handleRemoveExperience = (index: number) => {
    setExperiences((prev) => prev.filter((_, i) => i !== index));
  };

  const handleUpdateProject = (
    index: number,
    field: keyof CandidateProject,
    value: string
  ) => {
    setProjects((prev) => {
      const copy = [...prev];
      if (field === "stack") {
        copy[index] = {
          ...copy[index],
          stack: value.split(",").map((s) => s.trim()).filter(Boolean),
        };
      } else {
        copy[index] = { ...copy[index], [field]: value };
        if (field === "name" && value.trim()) {
          const valLower = value.trim().toLowerCase();
          setExcludedProjects((prevExc) =>
            prevExc.filter((n) => n.toLowerCase() !== valLower)
          );
        }
      }
      return copy;
    });
  };

  const handleAddProject = () => {
    setProjects((prev) => [
      {
        name: "",
        description: "",
        stack: [],
        context: "perso",
        url: "",
        repo: "",
      },
      ...prev,
    ]);
  };

  const handleRemoveProject = (index: number) => {
    const projToRemove = projects[index];
    if (projToRemove?.name?.trim()) {
      const name = projToRemove.name.trim();
      setExcludedProjects((prev) => (prev.includes(name) ? prev : [...prev, name]));
    }
    setProjects((prev) => prev.filter((_, i) => i !== index));
  };

  useEffect(() => {
    loadProfile();
  }, []);

  type SourceName = "cv" | "github" | "website";

  const [busySource, setBusySource] = useState<SourceName | null>(null);

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
      writing_style: writingStyle,
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
      excluded_projects: excludedProjects,
      education: profile?.education || [],
      certifications: profile?.certifications || [],
      languages: languagesText
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
      interests: interestsText
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
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
    <div className="space-y-6">
      {/* 1. Zone d'importation de CV par glisser-déposer ou sélection */}
      <CvDropzone
        onProfileUpdated={(updated) => {
          setProfile(updated);
          populateForm(updated);
        }}
        hasCvSource={Boolean(profile?.sources && "cv" in profile.sources)}
      />

      {/* 2. Profil Numérique Consolidé (IA) */}
      <div className="bg-slate-900/70 backdrop-blur-md rounded-2xl shadow-xl p-6 border border-slate-800">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
          <div className="flex items-start gap-3">
            <div className="p-2.5 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-400 shrink-0">
              <FiFileText className="w-5 h-5" />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2.5">
                <h2 className="text-lg font-bold text-white">
                  Profil Candidat Numérique (IA)
                </h2>
                {profile ? (
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-950/80 text-emerald-300 border border-emerald-700/50">
                    <FiCheckCircle className="mr-1 text-emerald-400" /> Prêt pour les lettres & matching
                  </span>
                ) : (
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-950/80 text-amber-300 border border-amber-700/50">
                    <FiAlertCircle className="mr-1 text-amber-400" /> Profil non initialisé
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Synthèse consolidée issue de votre CV, portfolio et GitHub, utilisée par l'IA pour personnaliser vos candidatures.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={() => setIsEditing(!isEditing)}
              className="inline-flex items-center px-4 py-2.5 rounded-xl text-xs font-semibold bg-blue-600/20 text-blue-300 border border-blue-500/30 hover:bg-blue-600/30 transition-all"
            >
              <FiEdit2 className="mr-1.5 w-3.5 h-3.5" />
              {isEditing ? "Annuler l'édition" : "Modifier manuellement"}
            </button>
          </div>
        </div>

      {saveSuccess && (
        <div className="bg-emerald-950/60 border border-emerald-700/60 text-emerald-200 p-3 rounded-xl mb-5 text-sm flex items-center">
          <FiCheckCircle className="mr-2 text-emerald-400 shrink-0" />
          Profil candidat enregistré avec succès ! L'IA utilisera ces informations à jour.
        </div>
      )}

      {saveError && (
        <div className="bg-red-950/60 border border-red-700/60 text-red-200 p-3 rounded-xl mb-5 text-sm flex items-center">
          <FiAlertCircle className="mr-2 text-red-400 shrink-0" />
          {saveError}
        </div>
      )}

      {!isEditing ? (
        // Mode Affichage / Consultation
        <div className="space-y-6 text-sm">
          {/* Titre & Résumé */}
          <div className="bg-slate-950/40 p-5 rounded-xl border border-slate-800/80">
            <div className="flex items-center justify-between mb-2.5">
              <h3 className="text-xs uppercase tracking-wider font-semibold text-slate-400 flex items-center gap-1.5">
                <FiAward className="text-blue-400" /> Titre professionnel & Résumé
              </h3>
              {profile?.headline && (
                <span className="text-[11px] font-semibold px-2 py-0.5 rounded-md bg-blue-500/10 text-blue-400 border border-blue-500/20">
                  Titre actif
                </span>
              )}
            </div>
            <div className="text-lg font-bold text-white mb-2 tracking-tight">
              {profile?.headline || "Titre professionnel non renseigné"}
            </div>
            <p className="text-slate-300 leading-relaxed whitespace-pre-line text-xs sm:text-sm">
              {profile?.summary || "Aucun résumé professionnel enregistré."}
            </p>
            {/* Voice DNA — always visible inline editor */}
            <div className="mt-3 pt-3 border-t border-slate-800/80">
              <div className="flex items-center justify-between mb-1.5">
                <div className="text-[11px] font-semibold text-purple-400 uppercase tracking-wider flex items-center gap-1.5">
                  <span>✍️</span> Style d&apos;écriture (Voice DNA)
                </div>
                {!isEditingStyle && (
                  <button
                    type="button"
                    onClick={() => {
                      setWritingStyleDraft(profile?.writing_style || writingStyle);
                      setIsEditingStyle(true);
                    }}
                    className="text-[10px] px-2 py-0.5 rounded-md bg-purple-500/10 text-purple-400 border border-purple-500/20 hover:bg-purple-500/20 transition-colors"
                  >
                    ✏️ Modifier
                  </button>
                )}
              </div>
              {isEditingStyle ? (
                <div className="space-y-2">
                  <textarea
                    id="inline_writing_style"
                    rows={3}
                    value={writingStyleDraft}
                    onChange={(e) => setWritingStyleDraft(e.target.value)}
                    placeholder="ex: Style direct et sobre, phrases courtes et percutantes, orienté résultats chiffrés, voix active, zéro flatterie générique..."
                    className="w-full rounded-md bg-slate-900 border border-purple-500/30 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-purple-500/50 text-xs leading-relaxed resize-none"
                    autoFocus
                  />
                  <div className="flex items-center gap-2 justify-end">
                    {saveStyleSuccess && (
                      <span className="text-[10px] text-emerald-400">✓ Sauvegardé</span>
                    )}
                    <button
                      type="button"
                      onClick={() => {
                        setIsEditingStyle(false);
                        setSaveStyleSuccess(false);
                      }}
                      className="text-[10px] px-2.5 py-1 rounded-md text-gray-400 hover:text-gray-200 transition-colors"
                    >
                      Annuler
                    </button>
                    <button
                      type="button"
                      disabled={isSavingStyle}
                      onClick={async () => {
                        setIsSavingStyle(true);
                        try {
                          await coverLetterApi.updateCandidateProfile({ writing_style: writingStyleDraft });
                          setWritingStyle(writingStyleDraft);
                          setProfile((prev) => prev ? { ...prev, writing_style: writingStyleDraft } : prev);
                          setSaveStyleSuccess(true);
                          setTimeout(() => {
                            setIsEditingStyle(false);
                            setSaveStyleSuccess(false);
                          }, 1500);
                        } catch {
                          // keep editor open on error
                        } finally {
                          setIsSavingStyle(false);
                        }
                      }}
                      className="text-[10px] px-3 py-1 rounded-md bg-purple-600/80 text-white hover:bg-purple-500 transition-colors disabled:opacity-60 flex items-center gap-1"
                    >
                      {isSavingStyle ? (
                        <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      ) : "Sauvegarder"}
                    </button>
                  </div>
                </div>
              ) : (
                <p className="text-slate-300 italic text-xs leading-relaxed whitespace-pre-line min-h-[1.5rem]">
                  {profile?.writing_style || writingStyle
                    ? <>&ldquo;{profile?.writing_style || writingStyle}&rdquo;</>
                    : <span className="text-slate-500 not-italic">Non défini — cliquez ✏️ Modifier pour décrire votre style d&apos;écriture.</span>
                  }
                </p>
              )}
            </div>
          </div>

          {/* Coordonnées & Liens web */}
          <div className="bg-slate-950/40 p-5 rounded-xl border border-slate-800/80">
            <h3 className="text-xs uppercase tracking-wider font-semibold text-slate-400 mb-3.5">
              Coordonnées & Liens web
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
              <div className="bg-slate-900/80 p-3 rounded-xl border border-slate-800/90 flex items-center">
                <FiGlobe className="mr-2.5 text-blue-400 shrink-0 w-4 h-4" />
                <div className="min-w-0">
                  <div className="text-[10px] text-slate-400 uppercase font-semibold">Site Web</div>
                  {profile?.contact?.website ? (
                    <a
                      href={profile.contact.website.startsWith("http") ? profile.contact.website : `https://${profile.contact.website}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-blue-400 hover:underline truncate block"
                    >
                      {profile.contact.website.replace(/^https?:\/\//, "")}
                    </a>
                  ) : (
                    <span className="text-xs text-slate-500 italic">Non renseigné</span>
                  )}
                </div>
              </div>

              <div className="bg-slate-900/80 p-3 rounded-xl border border-slate-800/90 flex items-center">
                <FiGithub className="mr-2.5 text-slate-300 shrink-0 w-4 h-4" />
                <div className="min-w-0">
                  <div className="text-[10px] text-slate-400 uppercase font-semibold">GitHub</div>
                  {profile?.contact?.github ? (
                    <a
                      href={profile.contact.github.startsWith("http") ? profile.contact.github : `https://${profile.contact.github}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-blue-400 hover:underline truncate block"
                    >
                      {profile.contact.github.replace(/^https?:\/\//, "")}
                    </a>
                  ) : (
                    <span className="text-xs text-slate-500 italic">Non renseigné</span>
                  )}
                </div>
              </div>

              <div className="bg-slate-900/80 p-3 rounded-xl border border-slate-800/90 flex items-center">
                <FiLinkedin className="mr-2.5 text-blue-500 shrink-0 w-4 h-4" />
                <div className="min-w-0">
                  <div className="text-[10px] text-slate-400 uppercase font-semibold">LinkedIn</div>
                  {profile?.contact?.linkedin ? (
                    <a
                      href={profile.contact.linkedin.startsWith("http") ? profile.contact.linkedin : `https://${profile.contact.linkedin}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-blue-400 hover:underline truncate block"
                    >
                      {profile.contact.linkedin.replace(/^https?:\/\//, "")}
                    </a>
                  ) : (
                    <span className="text-xs text-slate-500 italic">Non renseigné</span>
                  )}
                </div>
              </div>

              <div className="bg-slate-900/80 p-3 rounded-xl border border-slate-800/90 flex items-center">
                <FiMail className="mr-2.5 text-emerald-400 shrink-0 w-4 h-4" />
                <div className="min-w-0">
                  <div className="text-[10px] text-slate-400 uppercase font-semibold">Email</div>
                  <span className="text-xs text-slate-200 truncate block">
                    {profile?.contact?.email || "Non renseigné"}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Compétences structurées */}
          {profile?.skills && Object.keys(profile.skills).length > 0 && (
            <div className="bg-slate-950/40 p-5 rounded-xl border border-slate-800/80">
              <h3 className="text-xs uppercase tracking-wider font-semibold text-slate-400 mb-3.5 flex items-center">
                <FiCode className="mr-2 text-blue-400" /> Compétences structurées
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                {Object.entries(profile.skills).map(([category, items]) => (
                  <div key={category} className="bg-slate-900/80 p-3.5 rounded-xl border border-slate-800/90">
                    <span className="text-xs font-bold uppercase tracking-wider text-blue-400">
                      {category.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                    </span>
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {items.map((skill, i) => (
                        <span key={i} className="px-2.5 py-0.5 rounded-lg text-xs bg-slate-800 text-slate-200 border border-slate-700/70 font-medium">
                          {skill}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Expériences clés */}
          {profile?.experiences && profile.experiences.length > 0 && (
            <div className="bg-slate-950/40 p-5 rounded-xl border border-slate-800/80">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-xs uppercase tracking-wider font-semibold text-slate-400 flex items-center">
                  <FiBriefcase className="mr-2 text-blue-400" /> Expériences clés ({profile.experiences.length})
                </h3>
              </div>
              {profile?.conflicts && profile.conflicts.length > 0 && (
                <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3.5 text-xs text-amber-200 mb-4">
                  <p className="font-semibold mb-1">
                    Divergences détectées entre vos sources ({profile.conflicts.length})
                  </p>
                  <ul className="space-y-1">
                    {profile.conflicts.map((c: CandidateConflict, i) => (
                      <li key={i}>
                        <span className="font-medium text-amber-300">{c.company}</span> — {c.field} : « {String(c.kept)} » retenu depuis {c.kept_source},
                        « {String(c.discarded)} » écarté depuis {c.discarded_source}.
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="max-h-[560px] overflow-y-auto pr-1.5 custom-scrollbar space-y-3.5">
                {profile.experiences.map((exp, idx) => (
                  <div key={idx} className="bg-slate-900/80 p-4 rounded-xl border border-slate-800/90 hover:border-slate-700/80 transition-all">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div>
                        <span className="font-bold text-white text-sm sm:text-base">{exp.role}</span>
                        <span className="text-blue-400 mx-1.5 font-semibold">@</span>
                        <span className="text-slate-200 font-semibold">{exp.company}</span>
                        {exp.location && (
                          <span className="text-xs text-slate-400 ml-2">({exp.location})</span>
                        )}
                      </div>
                      <span className="inline-flex items-center text-xs font-semibold text-slate-300 bg-slate-800/90 border border-slate-700/60 px-2.5 py-1 rounded-lg shrink-0 w-fit">
                        <FiCalendar className="mr-1.5 text-blue-400" />
                        {formatPeriod(exp.start, exp.end)}
                      </span>
                    </div>

                    {exp.missions && exp.missions.length > 0 && (
                      <ul className="mt-3 space-y-1.5 text-xs text-slate-300">
                        {exp.missions.map((m, mIdx) => (
                          <li key={mIdx} className="flex items-start gap-2">
                            <span className="text-blue-400 mt-1 leading-none">•</span>
                            <span className="leading-relaxed">{m}</span>
                          </li>
                        ))}
                      </ul>
                    )}

                    <div className="flex flex-wrap items-center gap-1.5 mt-3 pt-3 border-t border-slate-800/60">
                      {exp.stack && exp.stack.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {exp.stack.map((s, sIdx) => (
                            <span key={sIdx} className="text-[10px] bg-blue-950/60 text-blue-300 border border-blue-800/40 px-2 py-0.5 rounded-md font-medium">
                              {s}
                            </span>
                          ))}
                        </div>
                      )}
                      {exp.sources && exp.sources.length > 0 && (
                        <div className="flex flex-wrap gap-1 ml-auto">
                          {exp.sources.map((s, sIdx) => (
                            <span key={sIdx} className="text-[10px] bg-emerald-950/60 text-emerald-300 border border-emerald-800/40 px-2 py-0.5 rounded-md font-medium">
                              {s}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Projets */}
          {profile?.projects && profile.projects.length > 0 && (
            <div className="bg-slate-950/40 p-5 rounded-xl border border-slate-800/80">
              <div className="flex items-center justify-between mb-3.5">
                <h3 className="text-xs uppercase tracking-wider font-semibold text-slate-400 flex items-center">
                  <FiLayers className="mr-2 text-blue-400" /> Projets personnels & réalisations ({profile.projects.length})
                </h3>
                {profile.projects.length > 4 && (
                  <span className="text-[10px] text-slate-500 italic">Défilement actif</span>
                )}
              </div>
              <div className="max-h-[520px] overflow-y-auto pr-1.5 custom-scrollbar">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                  {profile.projects.map((proj, idx) => (
                    <div key={idx} className="bg-slate-900/80 p-4 rounded-xl border border-slate-800/90 flex flex-col justify-between hover:border-slate-700/80 transition-all">
                      <div>
                        <div className="flex items-center justify-between gap-2 mb-1.5">
                          <div className="font-bold text-white text-sm flex items-center gap-2">
                            <span>{proj.name}</span>
                            {proj.context && (
                              <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                                {proj.context}
                              </span>
                            )}
                          </div>
                          {proj.sources && proj.sources.length > 0 && (
                            <div className="flex gap-1">
                              {proj.sources.map((s, sIdx) => (
                                <span key={sIdx} className="text-[9px] bg-emerald-950/60 text-emerald-300 border border-emerald-800/40 px-1.5 py-0.5 rounded">
                                  {s}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                        <p className="text-xs text-slate-300 leading-relaxed mt-1">
                          {proj.description}
                        </p>
                        {proj.highlights && proj.highlights.length > 0 && (
                          <ul className="mt-2 space-y-1 text-xs text-slate-400">
                            {proj.highlights.map((h, hIdx) => (
                              <li key={hIdx} className="flex items-start gap-1.5">
                                <span className="text-blue-400 mt-0.5">•</span>
                                <span>{h}</span>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>

                      <div className="mt-4 pt-3 border-t border-slate-800/60 space-y-3">
                        {proj.stack && proj.stack.length > 0 && (
                          <div className="flex flex-wrap gap-1">
                            {proj.stack.map((s, sIdx) => (
                              <span key={sIdx} className="text-[10px] bg-blue-950/60 text-blue-300 border border-blue-800/40 px-2 py-0.5 rounded-md font-medium">
                                {s}
                              </span>
                            ))}
                          </div>
                        )}
                        <div className="flex flex-wrap items-center gap-2">
                          {proj.url && (
                            <a
                              href={proj.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center text-xs font-semibold text-blue-400 hover:text-blue-300 hover:underline gap-1"
                            >
                              <span>Consulter</span>
                              <FiExternalLink className="w-3.5 h-3.5" />
                            </a>
                          )}
                          {proj.repo && (
                            <a
                              href={proj.repo}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center text-xs font-semibold text-slate-300 hover:text-white hover:underline gap-1 ml-auto"
                            >
                              <FiGithub className="w-3.5 h-3.5" />
                              <span>Code</span>
                            </a>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Formations & Diplômes */}
          {profile?.education && profile.education.length > 0 && (
            <div className="bg-slate-950/40 p-5 rounded-xl border border-slate-800/80">
              <h3 className="text-xs uppercase tracking-wider font-semibold text-slate-400 mb-3.5 flex items-center">
                <FiBook className="mr-2 text-blue-400" /> Formations & Diplômes ({profile.education.length})
              </h3>
              <div className="max-h-[460px] overflow-y-auto pr-1.5 custom-scrollbar">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                  {profile.education.map((edu, idx) => (
                    <div
                      key={idx}
                      className="bg-slate-900/80 p-4 rounded-xl border border-slate-800/90 hover:border-slate-700/80 transition-all flex flex-col justify-between"
                    >
                      <div>
                        <div className="flex items-start justify-between gap-2">
                          <h4 className="font-bold text-white text-sm sm:text-base leading-snug">
                            {edu.degree}
                          </h4>
                          {edu.years && (
                            <span className="inline-flex items-center text-[11px] font-semibold text-slate-300 bg-slate-800/90 border border-slate-700/60 px-2.5 py-0.5 rounded-lg shrink-0 w-fit">
                              <FiCalendar className="mr-1 text-blue-400" />
                              {edu.years}
                            </span>
                          )}
                        </div>
                        <p className="text-blue-400 text-xs font-semibold mt-1">
                          {edu.school}
                        </p>
                      </div>

                      {edu.topics && edu.topics.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-3 pt-3 border-t border-slate-800/60">
                          {edu.topics.map((t, tIdx) => (
                            <span
                              key={tIdx}
                              className="text-[10px] bg-slate-800/70 text-slate-300 border border-slate-700/40 px-2 py-0.5 rounded-md font-medium"
                            >
                              {t}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Certifications */}
          {profile?.certifications && profile.certifications.length > 0 && (
            <div className="bg-slate-950/40 p-5 rounded-xl border border-slate-800/80">
              <h3 className="text-xs uppercase tracking-wider font-semibold text-slate-400 mb-3.5 flex items-center">
                <FiAward className="mr-2 text-emerald-400" /> Certifications ({profile.certifications.length})
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                {profile.certifications.map((cert, idx) => (
                  <div
                    key={idx}
                    className="bg-slate-900/80 p-3.5 rounded-xl border border-slate-800/90 hover:border-slate-700/80 transition-all"
                  >
                    <h4 className="font-bold text-white text-xs sm:text-sm">{cert.name}</h4>
                    <p className="text-emerald-400 text-xs mt-1">{cert.issuer}</p>
                    {cert.year && (
                      <span className="text-[10px] text-slate-400 mt-2 block">{cert.year}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Langues & Centres d'intérêt */}
          {((profile?.languages && profile.languages.length > 0) || (profile?.interests && profile.interests.length > 0)) && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {profile?.languages && profile.languages.length > 0 && (
                <div className="bg-slate-950/40 p-5 rounded-xl border border-slate-800/80">
                  <h3 className="text-xs uppercase tracking-wider font-semibold text-slate-400 mb-3 flex items-center">
                    <FiGlobe className="mr-2 text-cyan-400" /> Langues ({profile.languages.length})
                  </h3>
                  <div className="flex flex-wrap gap-1.5">
                    {profile.languages.map((lang, idx) => (
                      <span key={idx} className="px-3 py-1 rounded-lg text-xs bg-slate-900 text-cyan-300 border border-cyan-800/40 font-medium">
                        {lang}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {profile?.interests && profile.interests.length > 0 && (
                <div className="bg-slate-950/40 p-5 rounded-xl border border-slate-800/80">
                  <h3 className="text-xs uppercase tracking-wider font-semibold text-slate-400 mb-3 flex items-center">
                    <FiHeart className="mr-2 text-rose-400" /> Centres d&apos;intérêt ({profile.interests.length})
                  </h3>
                  <div className="flex flex-wrap gap-1.5">
                    {profile.interests.map((item, idx) => (
                      <span key={idx} className="px-3 py-1 rounded-lg text-xs bg-slate-900 text-rose-300 border border-rose-800/40 font-medium">
                        {item}
                      </span>
                    ))}
                  </div>
                </div>
              )}
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

          <div>
            <label htmlFor="candidate_writing_style" className="block text-xs font-semibold text-gray-300 uppercase mb-1 flex items-center justify-between">
              <span>Style d&apos;écriture personnel (Voice DNA)</span>
              <span className="text-[10px] normal-case text-gray-400 font-normal">guide le ton et le style des lettres de motivation générées</span>
            </label>
            <textarea
              id="candidate_writing_style"
              rows={3}
              value={writingStyle}
              onChange={(e) => setWritingStyle(e.target.value)}
              placeholder="ex: Style direct et sobre, phrases courtes et percutantes, orienté résultats chiffrés, voix active, zéro flatterie générique..."
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
              <FiCode className="mr-1.5 text-blue-400" /> Compétences (Format libre "catégorie: item1, item2")
            </label>
            <textarea
              id="candidate_skills"
              rows={4}
              value={skillsText}
              onChange={(e) => setSkillsText(e.target.value)}
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
                onChange={(e) => setLanguagesText(e.target.value)}
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
                onChange={(e) => setInterestsText(e.target.value)}
                placeholder="ex: Course à pied, Échecs, Bénévolat associatif, Photographie"
                className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 text-xs sm:text-sm"
              />
            </div>
          </div>

          {/* Édition des Expériences */}
          <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800">
            <div className="flex items-center justify-between mb-3">
              <label className="text-xs font-semibold text-gray-300 uppercase flex items-center">
                <FiBriefcase className="mr-2 text-blue-400" /> Expériences professionnelles ({experiences.length})
              </label>
              <button
                type="button"
                onClick={handleAddExperience}
                className="inline-flex items-center gap-1 text-xs font-medium bg-blue-600/20 text-blue-300 hover:bg-blue-600/30 border border-blue-500/30 px-2.5 py-1 rounded-lg transition-colors cursor-pointer"
              >
                <FiPlus className="w-3.5 h-3.5" />
                <span>Ajouter une expérience</span>
              </button>
            </div>

            <div className="space-y-3 max-h-[380px] overflow-y-auto pr-1.5 custom-scrollbar">
              {experiences.map((exp, idx) => (
                <div key={idx} className="bg-slate-900/90 p-3 rounded-lg border border-slate-800 space-y-2 relative">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wide">
                      Expérience #{idx + 1}
                    </span>
                    <button
                      type="button"
                      onClick={() => handleRemoveExperience(idx)}
                      className="text-red-400 hover:text-red-300 p-1 rounded hover:bg-red-950/40 transition-colors cursor-pointer"
                      title="Supprimer cette expérience"
                    >
                      <FiTrash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <div>
                      <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Poste / Rôle</label>
                      <input
                        type="text"
                        value={exp.role || ""}
                        onChange={(e) => handleUpdateExperience(idx, "role", e.target.value)}
                        placeholder="ex: Chef de Projet, Animatrice 2D, Data Engineer"
                        className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white"
                      />
                    </div>
                    <div>
                      <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Entreprise</label>
                      <input
                        type="text"
                        value={exp.company || ""}
                        onChange={(e) => handleUpdateExperience(idx, "company", e.target.value)}
                        placeholder="ex: Agence Nile"
                        className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                    <div>
                      <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Début (ex: 2023-02)</label>
                      <input
                        type="text"
                        value={exp.start || ""}
                        onChange={(e) => handleUpdateExperience(idx, "start", e.target.value)}
                        placeholder="2023-02"
                        className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white"
                      />
                    </div>
                    <div>
                      <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Fin (vide = en cours)</label>
                      <input
                        type="text"
                        value={exp.end || ""}
                        onChange={(e) => handleUpdateExperience(idx, "end", e.target.value)}
                        placeholder="2024-06"
                        className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white"
                      />
                    </div>
                    <div>
                      <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Localisation</label>
                      <input
                        type="text"
                        value={exp.location || ""}
                        onChange={(e) => handleUpdateExperience(idx, "location", e.target.value)}
                        placeholder="ex: Lyon, France"
                        className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Outils & compétences (séparés par virgule)</label>
                    <input
                      type="text"
                      value={(exp.stack || []).join(", ")}
                      onChange={(e) => handleUpdateExperience(idx, "stack", e.target.value)}
                      placeholder="Python, Illustrator, Gestion de projet, Anglais courant"
                      className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-slate-400 font-medium block mb-0.5">
                      Missions & Réalisations (1 bullet point par ligne)
                    </label>
                    <textarea
                      rows={3}
                      value={(exp.missions || []).join("\n")}
                      onChange={(e) => handleUpdateExperience(idx, "missions", e.target.value)}
                      placeholder={"Pilotage d'un projet transverse avec réduction des délais de 30%\nCoordination d'une équipe de 5 personnes\nMise en place d'un nouveau processus qualité"}
                      className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white focus:outline-none focus:ring-1 focus:ring-blue-500 custom-scrollbar resize-y"
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Édition des Projets */}
          <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800">
            <div className="flex items-center justify-between mb-3">
              <label className="text-xs font-semibold text-gray-300 uppercase flex items-center">
                <FiLayers className="mr-2 text-blue-400" /> Projets & Réalisations ({projects.length})
              </label>
              <button
                type="button"
                onClick={handleAddProject}
                className="inline-flex items-center gap-1 text-xs font-medium bg-blue-600/20 text-blue-300 hover:bg-blue-600/30 border border-blue-500/30 px-2.5 py-1 rounded-lg transition-colors cursor-pointer"
              >
                <FiPlus className="w-3.5 h-3.5" />
                <span>Ajouter un projet</span>
              </button>
            </div>

            <div className="space-y-3 max-h-[380px] overflow-y-auto pr-1.5 custom-scrollbar">
              {projects.map((proj, idx) => (
                <div key={idx} className="bg-slate-900/90 p-3 rounded-lg border border-slate-800 space-y-2 relative">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wide">
                      Projet #{idx + 1}
                    </span>
                    <button
                      type="button"
                      onClick={() => handleRemoveProject(idx)}
                      className="text-red-400 hover:text-red-300 p-1 rounded hover:bg-red-950/40 transition-colors cursor-pointer"
                      title="Supprimer ce projet"
                    >
                      <FiTrash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <div>
                      <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Nom du projet</label>
                      <input
                        type="text"
                        value={proj.name || ""}
                        onChange={(e) => handleUpdateProject(idx, "name", e.target.value)}
                        placeholder="ex: WideDocs"
                        className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white"
                      />
                    </div>
                    <div>
                      <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Contexte</label>
                      <input
                        type="text"
                        value={proj.context || "perso"}
                        onChange={(e) => handleUpdateProject(idx, "context", e.target.value)}
                        placeholder="perso, client, recherche"
                        className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Description</label>
                    <textarea
                      rows={2}
                      value={proj.description || ""}
                      onChange={(e) => handleUpdateProject(idx, "description", e.target.value)}
                      placeholder="Description concise du projet et des défis relevés..."
                      className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white"
                    />
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <div>
                      <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Lien public (Démo / Site)</label>
                      <input
                        type="text"
                        value={proj.url || ""}
                        onChange={(e) => handleUpdateProject(idx, "url", e.target.value)}
                        placeholder="https://..."
                        className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white"
                      />
                    </div>
                    <div>
                      <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Dépôt GitHub (Code source)</label>
                      <input
                        type="text"
                        value={proj.repo || ""}
                        onChange={(e) => handleUpdateProject(idx, "repo", e.target.value)}
                        placeholder="https://github.com/..."
                        className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Outils & compétences (séparés par virgule)</label>
                    <input
                      type="text"
                      value={(proj.stack || []).join(", ")}
                      onChange={(e) => handleUpdateProject(idx, "stack", e.target.value)}
                      placeholder="React, FastAPI, PostgreSQL / ou : Storyboard, Animation 2D, After Effects"
                      className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white"
                    />
                  </div>
                </div>
              ))}
            </div>
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
    </div>
  );
}
