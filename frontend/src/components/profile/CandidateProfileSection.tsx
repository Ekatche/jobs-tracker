"use client";

import React from "react";
import Link from "next/link";
import { FiFileText, FiSave, FiEdit2, FiCheckCircle, FiAlertCircle } from "react-icons/fi";
import { useCandidateProfile } from "@/hooks/useCandidateProfile";
import CvDropzone from "./CvDropzone";
import {
  ProfileSummaryView,
  ProfileLanguagesInterestsView,
} from "./sections/ProfileSummaryView";
import { ProfileWorkView } from "./sections/ProfileWorkView";
import { ProfileProjectsView } from "./sections/ProfileProjectsView";
import { ProfileCredentialsView } from "./sections/ProfileCredentialsView";
import { ProfileCoreEditFields } from "./sections/ProfileCoreEditFields";
import { ProfileExperiencesEditor } from "./sections/ProfileExperiencesEditor";
import { ProfileProjectsEditor } from "./sections/ProfileProjectsEditor";
import { ProfileCredentialsEditor } from "./sections/ProfileCredentialsEditor";

export default function CandidateProfileSection() {
  const cp = useCandidateProfile();

  const handleCoreFieldChange = (field: string, value: string) => {
    const setters: Record<string, (v: string) => void> = {
      headline: cp.setHeadline,
      summary: cp.setSummary,
      writingStyle: cp.setWritingStyle,
      writingSamples: cp.setWritingSamples,
      website: cp.setWebsite,
      github: cp.setGithub,
      linkedin: cp.setLinkedin,
      email: cp.setEmail,
      phone: cp.setPhone,
      mobility: cp.setMobility,
      availability: cp.setAvailability,
      skillsText: cp.setSkillsText,
      languagesText: cp.setLanguagesText,
      interestsText: cp.setInterestsText,
    };
    setters[field]?.(value);
  };

  if (cp.loading) {
    return (
      <div className="bg-blue-night-lighter rounded-lg shadow-lg p-6 mb-8 border border-gray-800 animate-pulse">
        <div className="h-6 bg-gray-700/50 rounded w-1/3 mb-4" />
        <div className="h-4 bg-gray-700/30 rounded w-2/3 mb-2" />
        <div className="h-4 bg-gray-700/30 rounded w-1/2" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <CvDropzone
        onProfileUpdated={(updated) => {
          cp.setProfile(updated);
          cp.populateForm(updated);
        }}
        hasCvSource={Boolean(cp.profile?.sources && "cv" in cp.profile.sources)}
      />

      <div className="bg-slate-900/70 backdrop-blur-md rounded-2xl shadow-xl p-6 border border-slate-800">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
          <div className="flex items-start gap-3">
            <div className="p-2.5 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-400 shrink-0">
              <FiFileText className="w-5 h-5" />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2.5">
                <h2 className="text-lg font-bold text-white">Profil Candidat Numérique (IA)</h2>
                {cp.profile ? (
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
                Synthèse consolidée issue de votre CV, portfolio et GitHub, utilisée par l&apos;IA pour personnaliser vos candidatures.{" "}
                <Link href="/guide" className="text-blue-400 hover:text-blue-300 underline font-medium">
                  Comprendre le fonctionnement
                </Link>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={() => cp.setIsEditing(!cp.isEditing)}
              className="inline-flex items-center px-4 py-2.5 rounded-xl text-xs font-semibold bg-blue-600/20 text-blue-300 border border-blue-500/30 hover:bg-blue-600/30 transition-all"
            >
              <FiEdit2 className="mr-1.5 w-3.5 h-3.5" />
              {cp.isEditing ? "Annuler l'édition" : "Modifier manuellement"}
            </button>
          </div>
        </div>

        {cp.saveSuccess && (
          <div className="bg-emerald-950/60 border border-emerald-700/60 text-emerald-200 p-3 rounded-xl mb-5 text-sm flex items-center">
            <FiCheckCircle className="mr-2 text-emerald-400 shrink-0" />
            Profil candidat enregistré avec succès ! L&apos;IA utilisera ces informations à jour.
          </div>
        )}

        {cp.saveError && (
          <div className="bg-red-950/60 border border-red-700/60 text-red-200 p-3 rounded-xl mb-5 text-sm flex items-center">
            <FiAlertCircle className="mr-2 text-red-400 shrink-0" />
            {cp.saveError}
          </div>
        )}

        {!cp.isEditing ? (
          <div className="space-y-6 text-sm">
            <ProfileSummaryView
              profile={cp.profile}
              writingStyle={cp.writingStyle}
              writingSamples={cp.writingSamples}
            />
            <ProfileWorkView
              profile={cp.profile}
              dismissedConflicts={cp.dismissedConflicts}
              onSetDismissedConflicts={cp.setDismissedConflicts}
            />
            <ProfileProjectsView profile={cp.profile} />
            <ProfileCredentialsView profile={cp.profile} />
            <ProfileLanguagesInterestsView profile={cp.profile} />
          </div>
        ) : (
          <form onSubmit={cp.handleSave} className="space-y-4 text-sm">
            <ProfileCoreEditFields
              headline={cp.headline}
              summary={cp.summary}
              writingStyle={cp.writingStyle}
              writingSamples={cp.writingSamples}
              website={cp.website}
              github={cp.github}
              linkedin={cp.linkedin}
              email={cp.email}
              phone={cp.phone}
              mobility={cp.mobility}
              availability={cp.availability}
              skillsText={cp.skillsText}
              languagesText={cp.languagesText}
              interestsText={cp.interestsText}
              busySource={cp.busySource}
              onFieldChange={handleCoreFieldChange}
              onRunImport={cp.runImport}
            />
            <ProfileExperiencesEditor
              experiences={cp.experiences}
              onAdd={cp.handleAddExperience}
              onRemove={cp.handleRemoveExperience}
              onUpdate={cp.handleUpdateExperience}
            />
            <ProfileProjectsEditor
              projects={cp.projects}
              onAdd={cp.handleAddProject}
              onRemove={cp.handleRemoveProject}
              onUpdate={cp.handleUpdateProject}
            />
            <ProfileCredentialsEditor
              education={cp.education}
              certifications={cp.certifications}
              onAddEducation={cp.handleAddEducation}
              onRemoveEducation={cp.handleRemoveEducation}
              onUpdateEducation={cp.handleUpdateEducation}
              onAddCertification={cp.handleAddCertification}
              onRemoveCertification={cp.handleRemoveCertification}
              onUpdateCertification={cp.handleUpdateCertification}
            />

            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => {
                  if (cp.profile) cp.populateForm(cp.profile);
                  cp.setIsEditing(false);
                }}
                className="px-4 py-2 rounded-md text-gray-400 hover:text-white border border-gray-700 hover:bg-gray-800 transition-colors"
              >
                Annuler
              </button>
              <button
                type="submit"
                disabled={cp.isSaving}
                className="flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-md transition-colors disabled:opacity-50"
              >
                <FiSave className="mr-2" />
                {cp.isSaving ? "Enregistrement..." : "Enregistrer le profil candidat"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
