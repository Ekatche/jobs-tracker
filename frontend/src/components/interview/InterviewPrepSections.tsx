"use client";

import React from "react";
import { InterviewPrep } from "@/types/interview";
import StorySlotsTable from "./StorySlotsTable";
import StoryBankPanel from "./StoryBankPanel";
import AudiencePacksViewer from "./AudiencePacksViewer";
import AnticipatedQuestionsViewer from "./AnticipatedQuestionsViewer";
import ReverseQuestionsViewer from "./ReverseQuestionsViewer";
import { InterviewCancelButton, type InterviewPrepSection } from "./InterviewPrepHeader";
import { FiRefreshCw, FiBookOpen, FiUsers, FiHelpCircle, FiShield } from "react-icons/fi";

interface InterviewPrepSectionsProps {
  activeSection: InterviewPrepSection;
  offerId: string;
  prep: InterviewPrep | null;
  generatingModule: string | null;
  storiesCount: number;
  hasAudience: boolean;
  questionsCount: number;
  reverseCount: number;
  bankOpen: boolean;
  onSetBankOpen: (open: boolean) => void;
  onPrepUpdated: (prep: InterviewPrep) => void;
  onGenerateModule: (moduleName: "stories" | "audience-packs" | "questions" | "reverse-questions") => void;
  onCancel: () => void;
}

export default function InterviewPrepSections({
  activeSection,
  offerId,
  prep,
  generatingModule,
  storiesCount,
  hasAudience,
  questionsCount,
  reverseCount,
  bankOpen,
  onSetBankOpen,
  onPrepUpdated,
  onGenerateModule,
  onCancel,
}: InterviewPrepSectionsProps) {
  if (activeSection === "stories") {
    const storiesBody =
      storiesCount === 0 ? (
        <EmptySectionBox
          Icon={FiBookOpen}
          title="Aucune histoire STAR+R générée"
          subtitle='Cliquez sur "Générer les histoires" pour extraire vos meilleures réalisations alignées sur cette offre.'
        />
      ) : (
        <StorySlotsTable
          prep={prep!}
          offerId={offerId}
          onPrepUpdated={onPrepUpdated}
          onOpenBank={() => onSetBankOpen(true)}
        />
      );

    return (
      <div className="space-y-4">
        <SectionActionBar
          description="Génération de 3 à 5 histoires structurées basées sur vos expériences déclarées et les exigences clés du poste."
          isGenerating={generatingModule === "stories"}
          disabled={generatingModule !== null}
          buttonLabel={storiesCount > 0 ? "Régénérer" : "Générer les histoires"}
          onGenerate={() => onGenerateModule("stories")}
          onCancel={onCancel}
        />
        {!bankOpen ? (
          storiesBody
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-4 items-start">
            <div className="min-w-0">{storiesBody}</div>
            <StoryBankPanel
              offerId={offerId}
              prep={prep}
              open={bankOpen}
              onClose={() => onSetBankOpen(false)}
              onPrepUpdated={onPrepUpdated}
            />
          </div>
        )}
      </div>
    );
  }

  if (activeSection === "audience") {
    return (
      <div className="space-y-4">
        <SectionActionBar
          description="Adaptez votre discours selon l'interlocuteur : RH (cadrage & salaire), Manager (stratégie), ou Pairs (architecture)."
          isGenerating={generatingModule === "audience-packs"}
          disabled={generatingModule !== null}
          buttonLabel={hasAudience ? "Régénérer" : "Générer les packs"}
          onGenerate={() => onGenerateModule("audience-packs")}
          onCancel={onCancel}
        />
        {!hasAudience ? (
          <EmptySectionBox
            Icon={FiUsers}
            title="Aucun pack d'audience généré"
            subtitle="Générez vos guides personnalisés pour aborder sereinement chaque tour d'entretien."
          />
        ) : (
          <AudiencePacksViewer
            recruiterPack={prep?.recruiter_pack}
            hmPack={prep?.hm_pack}
            techPack={prep?.tech_pack}
          />
        )}
      </div>
    );
  }

  if (activeSection === "questions") {
    return (
      <div className="space-y-4">
        <SectionActionBar
          description="Anticipation des questions comportementales (avec renvoi STAR+R) et techniques déduites de l'offre."
          isGenerating={generatingModule === "questions"}
          disabled={generatingModule !== null}
          buttonLabel={questionsCount > 0 ? "Régénérer" : "Générer les questions"}
          onGenerate={() => onGenerateModule("questions")}
          onCancel={onCancel}
        />
        {questionsCount === 0 ? (
          <EmptySectionBox
            Icon={FiHelpCircle}
            title="Aucune question anticipée"
            subtitle="Prévoyez les questions ciblées et préparez les points clés incontournables."
          />
        ) : (
          <AnticipatedQuestionsViewer
            offerId={offerId}
            questions={prep!.anticipated_questions}
            attempts={prep!.practice_attempts ?? []}
            onPrepUpdated={onPrepUpdated}
          />
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <SectionActionBar
        description="Questions d'audit pour évaluer la santé de l'équipe, la dette technique et l'autonomie."
        isGenerating={generatingModule === "reverse-questions"}
        disabled={generatingModule !== null}
        buttonLabel={reverseCount > 0 ? "Régénérer" : "Générer les questions"}
        onGenerate={() => onGenerateModule("reverse-questions")}
        onCancel={onCancel}
      />
      {reverseCount === 0 ? (
        <EmptySectionBox
          Icon={FiShield}
          title="Aucune question inversée générée"
          subtitle="Générez les questions tactiques pour auditer vos futurs collaborateurs."
        />
      ) : (
        <ReverseQuestionsViewer questions={prep!.reverse_questions} />
      )}
    </div>
  );
}

function SectionActionBar({
  description,
  isGenerating,
  disabled,
  buttonLabel,
  onGenerate,
  onCancel,
}: {
  description: string;
  isGenerating: boolean;
  disabled: boolean;
  buttonLabel: string;
  onGenerate: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="flex items-center justify-between bg-slate-900/40 p-3 rounded-xl border border-slate-800/80">
      <span className="text-xs text-slate-400">{description}</span>
      <div className="flex items-center gap-2 shrink-0">
        <button
          type="button"
          disabled={disabled}
          onClick={onGenerate}
          className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600/90 hover:bg-indigo-600 text-white shrink-0 flex items-center gap-1.5 transition-colors disabled:opacity-50"
        >
          <FiRefreshCw className={`w-3.5 h-3.5 ${isGenerating ? "animate-spin" : ""}`} />
          <span>{isGenerating ? "Génération..." : buttonLabel}</span>
        </button>
        <InterviewCancelButton show={isGenerating} onCancel={onCancel} />
      </div>
    </div>
  );
}

function EmptySectionBox({
  Icon,
  title,
  subtitle,
}: {
  Icon: typeof FiBookOpen;
  title: string;
  subtitle: string;
}) {
  return (
    <div className="text-center py-12 px-4 rounded-2xl bg-slate-900/40 border border-dashed border-slate-800">
      <Icon className="w-8 h-8 text-slate-600 mx-auto mb-2" />
      <h4 className="text-sm font-medium text-slate-300">{title}</h4>
      <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">{subtitle}</p>
    </div>
  );
}
