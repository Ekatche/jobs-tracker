"use client";

import {
  FiZap,
  FiDownload,
  FiCopy,
  FiCheck,
  FiBookOpen,
  FiUsers,
  FiHelpCircle,
  FiShield,
  FiAlertCircle,
  FiX,
} from "react-icons/fi";

export type InterviewPrepSection = "stories" | "audience" | "questions" | "reverse";

interface InterviewPrepHeaderProps {
  targetCompany?: string;
  totalCompleted: number;
  generatingModule: string | null;
  copied: boolean;
  error: string | null;
  activeSection: InterviewPrepSection;
  storiesCount: number;
  hasAudience: boolean;
  questionsCount: number;
  reverseCount: number;
  onGenerateAll: () => void;
  onCancelGeneration: () => void;
  onCopyMarkdown: () => void;
  onDownloadMarkdown: () => void;
  onSelectSection: (section: InterviewPrepSection) => void;
}

export function InterviewCancelButton({
  show,
  onCancel,
}: {
  show: boolean;
  onCancel: () => void;
}) {
  if (!show) return null;
  return (
    <button
      type="button"
      onClick={onCancel}
      className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 shrink-0 flex items-center gap-1.5 transition-colors"
    >
      <FiX className="w-3.5 h-3.5" />
      <span>Annuler</span>
    </button>
  );
}

export default function InterviewPrepHeader({
  targetCompany,
  totalCompleted,
  generatingModule,
  copied,
  error,
  activeSection,
  storiesCount,
  hasAudience,
  questionsCount,
  reverseCount,
  onGenerateAll,
  onCancelGeneration,
  onCopyMarkdown,
  onDownloadMarkdown,
  onSelectSection,
}: InterviewPrepHeaderProps) {
  const sections: Array<{
    key: InterviewPrepSection;
    title: string;
    subtitle: string;
    badge: string;
    ready: boolean;
    Icon: typeof FiBookOpen;
    iconClass?: string;
  }> = [
    {
      key: "stories",
      title: "1. Histoires STAR+R",
      subtitle: "Preuves & métriques réelles",
      badge: String(storiesCount),
      ready: storiesCount > 0,
      Icon: FiBookOpen,
    },
    {
      key: "audience",
      title: "2. Packs d'Audience",
      subtitle: "RH, Manager, Panel Tech",
      badge: hasAudience ? "Prêt" : "0",
      ready: hasAudience,
      Icon: FiUsers,
    },
    {
      key: "questions",
      title: "3. Questions Anticipées",
      subtitle: "Comportement & Technique",
      badge: String(questionsCount),
      ready: questionsCount > 0,
      Icon: FiHelpCircle,
    },
    {
      key: "reverse",
      title: "4. Anti Red-Flags",
      subtitle: "Questions à poser",
      badge: String(reverseCount),
      ready: reverseCount > 0,
      Icon: FiShield,
      iconClass: "text-amber-400",
    },
  ];

  return (
    <>
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 sm:p-6 shadow-xl relative overflow-hidden backdrop-blur-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 flex items-center gap-1.5">
                <FiZap className="w-3.5 h-3.5 text-indigo-400" />
                Intelligence Career-Ops
              </span>
              <span className="text-xs text-slate-400">• {totalCompleted}/4 modules prêts</span>
            </div>
            <h3 className="text-xl font-bold text-white">
              Kit de Préparation d&apos;Entretien {targetCompany ? `— ${targetCompany}` : ""}
            </h3>
            <p className="text-xs text-slate-400 mt-1 max-w-2xl">
              Préparez vos entretiens avec précision : histoires STAR+R réelles, discours segmenté par
              audience, questions probables et questions inversées anti red-flags.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 shrink-0">
            <button
              type="button"
              disabled={generatingModule !== null}
              onClick={onGenerateAll}
              className="px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-500/25 flex items-center gap-2 transition-all disabled:opacity-50"
            >
              <FiZap className={`w-4 h-4 ${generatingModule === "all" ? "animate-spin" : ""}`} />
              <span>
                {generatingModule === "all" ? "Génération en cours..." : "Tout générer (1-Clic)"}
              </span>
            </button>
            <InterviewCancelButton
              show={generatingModule === "all"}
              onCancel={onCancelGeneration}
            />

            <button
              type="button"
              onClick={onCopyMarkdown}
              title="Copier en Markdown"
              className="p-2 sm:px-3 sm:py-2 rounded-xl text-xs sm:text-sm font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1.5 transition-colors"
            >
              {copied ? (
                <FiCheck className="w-4 h-4 text-emerald-400" />
              ) : (
                <FiCopy className="w-4 h-4" />
              )}
              <span className="hidden sm:inline">{copied ? "Copié !" : "Copier .md"}</span>
            </button>

            <button
              type="button"
              onClick={onDownloadMarkdown}
              title="Télécharger en fichier Markdown"
              className="p-2 sm:px-3 sm:py-2 rounded-xl text-xs sm:text-sm font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1.5 transition-colors"
            >
              <FiDownload className="w-4 h-4" />
              <span className="hidden sm:inline">Télécharger</span>
            </button>
          </div>
        </div>

        {error && (
          <div className="mt-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-300 flex items-center gap-2">
            <FiAlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {sections.map(({ key, title, subtitle, badge, ready, Icon, iconClass }) => (
          <button
            key={key}
            type="button"
            onClick={() => onSelectSection(key)}
            className={`p-3.5 rounded-xl border flex flex-col items-start gap-1 transition-all ${
              activeSection === key
                ? "bg-indigo-950/40 border-indigo-500/60 shadow-lg shadow-indigo-500/10"
                : "bg-slate-900/60 border-slate-800 text-slate-400 hover:bg-slate-800/40"
            }`}
          >
            <div className="flex items-center justify-between w-full">
              <span className="text-xs font-semibold text-white flex items-center gap-1.5">
                <Icon className={`w-4 h-4 ${iconClass || "text-indigo-400"}`} />
                {title}
              </span>
              <span
                className={`text-[11px] font-bold px-1.5 py-0.2 rounded ${
                  ready ? "bg-emerald-500/10 text-emerald-400" : "bg-slate-800 text-slate-500"
                }`}
              >
                {badge}
              </span>
            </div>
            <span className="text-[11px] text-slate-400">{subtitle}</span>
          </button>
        ))}
      </div>
    </>
  );
}
