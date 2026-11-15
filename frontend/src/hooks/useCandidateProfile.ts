"use client";

import React, { useState, useEffect, useCallback } from "react";
import { coverLetterApi } from "@/lib/api";
import {
  CandidateProfile,
  CandidateExperience,
  CandidateProject,
  CandidateEducation,
  CandidateCertification,
} from "@/types/coverLetter";
import { parseSkillsText, stringifySkillsMap } from "@/lib/profileFormatters";

export type ImportSourceName = "cv" | "github" | "website";

/**
 * Manages candidate profile hydration, external imports, nested section editing, and save mutations.
 */
export function useCandidateProfile() {
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [dismissedConflicts, setDismissedConflicts] = useState(false);
  const [busySource, setBusySource] = useState<ImportSourceName | null>(null);

  const [headline, setHeadline] = useState("");
  const [summary, setSummary] = useState("");
  const [writingStyle, setWritingStyle] = useState("");
  const [writingSamples, setWritingSamples] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [website, setWebsite] = useState("");
  const [github, setGithub] = useState("");
  const [linkedin, setLinkedin] = useState("");
  const [mobility, setMobility] = useState("");
  const [availability, setAvailability] = useState("");
  const [skillsText, setSkillsText] = useState("");
  const [languagesText, setLanguagesText] = useState("");
  const [interestsText, setInterestsText] = useState("");
  const [experiences, setExperiences] = useState<CandidateExperience[]>([]);
  const [projects, setProjects] = useState<CandidateProject[]>([]);
  const [excludedProjects, setExcludedProjects] = useState<string[]>([]);
  const [education, setEducation] = useState<CandidateEducation[]>([]);
  const [excludedEducation, setExcludedEducation] = useState<string[]>([]);
  const [certifications, setCertifications] = useState<CandidateCertification[]>([]);
  const [excludedCertifications, setExcludedCertifications] = useState<string[]>([]);

  const populateForm = useCallback((data: CandidateProfile) => {
    setHeadline(data.headline || "");
    setSummary(data.summary || "");
    setWritingStyle(data.writing_style || "");
    setWritingSamples(data.writing_samples || "");
    setEmail(data.contact?.email || "");
    setPhone(data.contact?.phone || "");
    setWebsite(data.contact?.website || "");
    setGithub(data.contact?.github || "");
    setLinkedin(data.contact?.linkedin || "");
    setMobility(data.contact?.mobility || "");
    setAvailability(data.contact?.availability || "");
    setSkillsText(stringifySkillsMap(data.skills));
    setExperiences(data.experiences || []);
    setProjects(data.projects || []);
    setExcludedProjects(data.excluded_projects || []);
    setEducation(data.education || []);
    setExcludedEducation(data.excluded_education || []);
    setCertifications(data.certifications || []);
    setExcludedCertifications(data.excluded_certifications || []);
    setLanguagesText((data.languages || []).join(", "));
    setInterestsText((data.interests || []).join(", "));
  }, []);

  const loadProfile = useCallback(async () => {
    setLoading(true);
    setSaveError(null);
    try {
      const data = await coverLetterApi.getCandidateProfile();
      if (data) {
        setProfile(data);
        populateForm(data);
      }
    } catch {
      setProfile(null);
    } finally {
      setLoading(false);
    }
  }, [populateForm]);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  const handleUpdateExperience = (idx: number, field: keyof CandidateExperience, value: string) => {
    setExperiences((prev) => {
      const copy = [...prev];
      if (field === "stack") {
        copy[idx] = { ...copy[idx], stack: value.split(",").map((s) => s.trim()).filter(Boolean) };
      } else if (field === "missions") {
        copy[idx] = { ...copy[idx], missions: value.split("\n").map((s) => s.replace(/^[•\-\*]\s*/, "")) };
      } else {
        copy[idx] = { ...copy[idx], [field]: value };
      }
      return copy;
    });
  };

  const handleAddExperience = () => {
    setExperiences((prev) => [
      { role: "", company: "", start: "", end: "", location: "", missions: [], stack: [] },
      ...prev,
    ]);
  };

  const handleRemoveExperience = (idx: number) => {
    setExperiences((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleUpdateProject = (idx: number, field: keyof CandidateProject, value: string) => {
    setProjects((prev) => {
      const copy = [...prev];
      if (field === "stack") {
        copy[idx] = { ...copy[idx], stack: value.split(",").map((s) => s.trim()).filter(Boolean) };
      } else {
        copy[idx] = { ...copy[idx], [field]: value };
        if (field === "name" && value.trim()) {
          const valLower = value.trim().toLowerCase();
          setExcludedProjects((exc) => exc.filter((n) => n.toLowerCase() !== valLower));
        }
      }
      return copy;
    });
  };

  const handleAddProject = () => {
    setProjects((prev) => [
      { name: "", description: "", stack: [], context: "", url: "", repo: "" },
      ...prev,
    ]);
  };

  const handleRemoveProject = (idx: number) => {
    const removed = projects[idx];
    if (removed?.name?.trim()) {
      const name = removed.name.trim();
      setExcludedProjects((prev) => (prev.includes(name) ? prev : [...prev, name]));
    }
    setProjects((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleUpdateEducation = (idx: number, field: keyof CandidateEducation, value: string) => {
    setEducation((prev) => {
      const copy = [...prev];
      if (field === "topics") {
        copy[idx] = { ...copy[idx], topics: value.split(",").map((s) => s.trim()).filter(Boolean) };
      } else {
        copy[idx] = { ...copy[idx], [field]: value };
        if ((field === "school" || field === "degree") && value.trim()) {
          const entry = copy[idx];
          const key = `${(entry.school || "").trim().toLowerCase()}::${(entry.degree || "").trim().toLowerCase()}`;
          setExcludedEducation((exc) => exc.filter((k) => k.toLowerCase() !== key));
        }
      }
      return copy;
    });
  };

  const handleAddEducation = () => {
    setEducation((prev) => [{ school: "", degree: "", years: "", topics: [] }, ...prev]);
  };

  const handleRemoveEducation = (idx: number) => {
    const removed = education[idx];
    if (removed?.school?.trim() || removed?.degree?.trim()) {
      const key = `${(removed.school || "").trim()}::${(removed.degree || "").trim()}`;
      setExcludedEducation((prev) => (prev.includes(key) ? prev : [...prev, key]));
    }
    setEducation((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleUpdateCertification = (
    idx: number,
    field: keyof CandidateCertification,
    value: string
  ) => {
    setCertifications((prev) => {
      const copy = [...prev];
      if (field === "topics") {
        copy[idx] = { ...copy[idx], topics: value.split(",").map((s) => s.trim()).filter(Boolean) };
      } else {
        copy[idx] = { ...copy[idx], [field]: value };
        if (field === "name" && value.trim()) {
          const valLower = value.trim().toLowerCase();
          setExcludedCertifications((exc) => exc.filter((n) => n.toLowerCase() !== valLower));
        }
      }
      return copy;
    });
  };

  const handleAddCertification = () => {
    setCertifications((prev) => [{ name: "", issuer: "", year: "", topics: [] }, ...prev]);
  };

  const handleRemoveCertification = (idx: number) => {
    const removed = certifications[idx];
    if (removed?.name?.trim()) {
      const name = removed.name.trim();
      setExcludedCertifications((prev) => (prev.includes(name) ? prev : [...prev, name]));
    }
    setCertifications((prev) => prev.filter((_, i) => i !== idx));
  };

  const runImport = async (source: ImportSourceName, call: () => Promise<CandidateProfile>) => {
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

    const parsedSkills = parseSkillsText(skillsText);
    const cleanedExperiences = experiences.map((exp) => ({
      ...exp,
      missions: (exp.missions || []).map((m) => m.trim()).filter(Boolean),
    }));

    const updatedProfile: Partial<CandidateProfile> = {
      headline,
      summary,
      writing_style: writingStyle,
      writing_samples: writingSamples,
      contact: { email, phone, website, github, linkedin, mobility, availability },
      skills: Object.keys(parsedSkills).length > 0 ? parsedSkills : profile?.skills || {},
      experiences: cleanedExperiences,
      projects,
      excluded_projects: excludedProjects,
      education,
      excluded_education: excludedEducation,
      certifications,
      excluded_certifications: excludedCertifications,
      languages: languagesText.split(",").map((s) => s.trim()).filter(Boolean),
      interests: interestsText.split(",").map((s) => s.trim()).filter(Boolean),
    };

    try {
      const saved = await coverLetterApi.updateCandidateProfile(updatedProfile);
      setProfile(saved);
      populateForm(saved);
      setIsEditing(false);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 4000);
    } catch (err: unknown) {
      setSaveError(
        err instanceof Error ? err.message : "Erreur lors de l'enregistrement du profil candidat"
      );
    } finally {
      setIsSaving(false);
    }
  };

  return {
    profile, setProfile, loading, isEditing, setIsEditing, isSaving, saveSuccess, saveError,
    dismissedConflicts, setDismissedConflicts, busySource, populateForm, runImport, handleSave,
    headline, setHeadline, summary, setSummary, writingStyle, setWritingStyle,
    writingSamples, setWritingSamples, email, setEmail, phone, setPhone,
    website, setWebsite, github, setGithub, linkedin, setLinkedin,
    mobility, setMobility, availability, setAvailability, skillsText, setSkillsText,
    languagesText, setLanguagesText, interestsText, setInterestsText,
    experiences, handleUpdateExperience, handleAddExperience, handleRemoveExperience,
    projects, handleUpdateProject, handleAddProject, handleRemoveProject,
    education, handleUpdateEducation, handleAddEducation, handleRemoveEducation,
    certifications, handleUpdateCertification, handleAddCertification, handleRemoveCertification,
  };
}
