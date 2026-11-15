"use client";

import { FiCheck, FiRefreshCw, FiPlus, FiTrash2, FiSave } from "react-icons/fi";
import { TailoredCVSchema } from "@/types/resume";

interface ResumeContentEditorProps {
  editableContent: TailoredCVSchema | null;
  savingContent: boolean;
  saveSuccess: boolean;
  onChangeContent: (next: TailoredCVSchema) => void;
  onSubmit: (e: React.FormEvent) => void;
  onSkillChange: (groupCategory: string, skillsStr: string) => void;
  onBulletChange: (expIdx: number, bulletIdx: number, val: string) => void;
  onAddBullet: (expIdx: number) => void;
  onRemoveBullet: (expIdx: number, bulletIdx: number) => void;
}

export default function ResumeContentEditor({
  editableContent,
  savingContent,
  saveSuccess,
  onChangeContent,
  onSubmit,
  onSkillChange,
  onBulletChange,
  onAddBullet,
  onRemoveBullet,
}: ResumeContentEditorProps) {
  return (
    <div className="flex-1 bg-[#101827] p-6 overflow-y-auto">
      {editableContent ? (
        <form onSubmit={onSubmit} className="max-w-4xl mx-auto space-y-6 pb-8">
          <div className="flex items-center justify-between border-b border-slate-800 pb-4">
            <div>
              <h3 className="text-base font-bold text-white">Personnalisation du contenu</h3>
              <p className="text-xs text-slate-400">
                Modifiez les formulations et puces d&apos;impact générées pour les ajuster selon vos préférences.
              </p>
            </div>
            <div className="flex items-center gap-3">
              {saveSuccess && (
                <span className="flex items-center gap-1 text-xs text-emerald-400 bg-emerald-950/60 px-2.5 py-1 rounded-md border border-emerald-800/50">
                  <FiCheck /> Modifications enregistrées !
                </span>
              )}
              <button
                type="submit"
                disabled={savingContent}
                className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-xs font-bold shadow-md transition-colors"
              >
                {savingContent ? <FiRefreshCw className="animate-spin" /> : <FiSave />}
                <span>Enregistrer et voir l&apos;aperçu</span>
              </button>
            </div>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-2">
            <label className="block text-xs font-semibold text-slate-300">
              Intitulé du poste affiché en haut du CV
            </label>
            <input
              type="text"
              value={editableContent.target_role_title}
              onChange={(e) =>
                onChangeContent({ ...editableContent, target_role_title: e.target.value })
              }
              className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
              placeholder="Ex: Ingénieur IA"
              required
            />
            <p className="text-[11px] text-slate-400">
              Astuce ATS : Conservez l&apos;intitulé exact de l&apos;annonce pour maximiser le score de pertinence.
            </p>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-2">
            <label className="block text-xs font-semibold text-slate-300">
              Accroche professionnelle (Summary)
            </label>
            <textarea
              rows={3}
              value={editableContent.professional_summary}
              onChange={(e) =>
                onChangeContent({ ...editableContent, professional_summary: e.target.value })
              }
              className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-blue-500 leading-relaxed"
              placeholder="3 à 4 lignes d'impact..."
              required
            />
          </div>

          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-3">
            <h4 className="text-xs font-semibold text-slate-300">Compétences clés par catégorie</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {editableContent.prioritized_skills.map((group, idx) => (
                <div
                  key={idx}
                  className="bg-slate-950/80 p-3 rounded-lg border border-slate-800 space-y-1.5"
                >
                  <span className="text-xs font-medium text-blue-300 block">{group.category}</span>
                  <input
                    type="text"
                    value={group.skills.join(", ")}
                    onChange={(e) => onSkillChange(group.category, e.target.value)}
                    className="w-full px-2.5 py-1.5 bg-slate-900 border border-slate-700/80 rounded-md text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                    placeholder="Compétences séparées par des virgules"
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-4">
            <h4 className="text-xs font-semibold text-slate-300">
              Expériences professionnelles &amp; Puces d&apos;impact
            </h4>
            <div className="space-y-4">
              {editableContent.experiences.map((exp, expIdx) => (
                <div
                  key={expIdx}
                  className="bg-slate-950/70 border border-slate-800/90 rounded-lg p-3.5 space-y-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/80 pb-2">
                    <div className="font-semibold text-xs text-white">
                      <span>{exp.title}</span> • <span className="text-blue-400">{exp.company}</span>
                    </div>
                    <span className="text-[11px] text-slate-400">
                      {exp.start_date} – {exp.end_date || "Présent"}
                    </span>
                  </div>

                  <div className="space-y-2">
                    <label className="text-[11px] font-medium text-slate-400 block">
                      Puces de réalisations :
                    </label>
                    {exp.bullet_points.map((bullet, bIdx) => (
                      <div key={bIdx} className="flex items-start gap-2">
                        <textarea
                          rows={2}
                          value={bullet}
                          onChange={(e) => onBulletChange(expIdx, bIdx, e.target.value)}
                          className="flex-1 px-2.5 py-1 bg-slate-900 border border-slate-700/70 rounded text-xs text-slate-200 focus:outline-none focus:border-blue-500 leading-relaxed"
                        />
                        <button
                          type="button"
                          onClick={() => onRemoveBullet(expIdx, bIdx)}
                          className="p-1 text-slate-500 hover:text-red-400 transition-colors mt-1"
                          title="Supprimer cette puce"
                        >
                          <FiTrash2 className="text-xs" />
                        </button>
                      </div>
                    ))}
                    <button
                      type="button"
                      onClick={() => onAddBullet(expIdx)}
                      className="flex items-center gap-1 text-[11px] text-blue-400 hover:text-blue-300 font-medium pt-1"
                    >
                      <FiPlus className="text-xs" />
                      <span>Ajouter une puce d&apos;impact</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="flex justify-end pt-4">
            <button
              type="submit"
              disabled={savingContent}
              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white px-5 py-2 rounded-lg text-xs font-bold shadow-md transition-colors"
            >
              {savingContent ? <FiRefreshCw className="animate-spin" /> : <FiSave />}
              <span>Enregistrer et générer le PDF</span>
            </button>
          </div>
        </form>
      ) : (
        <div className="text-center py-12 text-slate-400 text-xs">
          Aucun contenu disponible pour l&apos;édition.
        </div>
      )}
    </div>
  );
}
