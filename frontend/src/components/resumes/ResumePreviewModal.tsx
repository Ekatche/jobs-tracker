"use client";

import { FiRefreshCw } from "react-icons/fi";
import { TailoredResume, TailoredCVSchema } from "@/types/resume";
import type { ResumeAppearance } from "@/lib/cvTemplates";
import ResumeAtsTab from "@/components/resumes/ResumeAtsTab";
import ResumePreviewToolbar from "@/components/resumes/ResumePreviewToolbar";
import ResumeContentEditor from "@/components/resumes/ResumeContentEditor";
import { useResumePreview, type ResumeModalTab } from "@/hooks/useResumePreview";

interface ResumePreviewModalProps {
  resume: TailoredResume | null;
  isOpen: boolean;
  onClose: () => void;
  onUpdateAppearance?: (resumeId: string, appearance: ResumeAppearance) => Promise<void>;
  onUpdateContent?: (resumeId: string, content: TailoredCVSchema) => Promise<void>;
  onRegenerate?: (resume: TailoredResume) => Promise<void>;
  initialTab?: ResumeModalTab;
}

export default function ResumePreviewModal({
  resume,
  isOpen,
  onClose,
  onUpdateAppearance,
  onUpdateContent,
  onRegenerate,
  initialTab = "preview",
}: ResumePreviewModalProps) {
  const {
    resumeId,
    activeTab,
    setActiveTab,
    atsRefreshKey,
    selectedTemplate,
    selectedAccent,
    withPhoto,
    pdfUrl,
    loadingPdf,
    downloading,
    savingContent,
    regenerating,
    saveSuccess,
    error,
    editableContent,
    setEditableContent,
    handleDownload,
    handleTemplateChange,
    handleAccentChange,
    handlePhotoToggle,
    handleRegenerateClick,
    handleSaveContent,
    handleBulletChange,
    handleAddBullet,
    handleRemoveBullet,
    handleSkillChange,
  } = useResumePreview({
    resume,
    isOpen,
    initialTab,
    onUpdateAppearance,
    onUpdateContent,
    onRegenerate,
  });

  if (!isOpen || !resume) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="bg-[#131d31] border border-slate-700/60 rounded-xl shadow-2xl flex flex-col w-full max-w-5xl h-[92vh] overflow-hidden text-slate-100 animate-in fade-in zoom-in-95 duration-200">
        <ResumePreviewToolbar
          resume={resume}
          activeTab={activeTab}
          selectedTemplate={selectedTemplate}
          selectedAccent={selectedAccent}
          withPhoto={withPhoto}
          loadingPdf={loadingPdf}
          downloading={downloading}
          regenerating={regenerating}
          hasRegenerate={Boolean(onRegenerate)}
          onTabChange={setActiveTab}
          onTemplateChange={handleTemplateChange}
          onAccentChange={handleAccentChange}
          onPhotoToggle={handlePhotoToggle}
          onRegenerate={handleRegenerateClick}
          onDownload={handleDownload}
          onClose={onClose}
        />

        {activeTab === "preview" && (
          <div className="flex-1 bg-slate-950/60 p-4 overflow-hidden relative flex items-center justify-center">
            {loadingPdf && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-[#131d31]/80 z-10 gap-3">
                <FiRefreshCw className="animate-spin text-3xl text-blue-400" />
                <p className="text-sm text-slate-300">Rendu du CV vectoriel en cours...</p>
              </div>
            )}

            {error && (
              <div className="text-center p-6 bg-red-950/40 border border-red-800/50 rounded-lg text-red-200 text-sm max-w-md">
                <p className="font-semibold mb-1">Échec de l&apos;aperçu</p>
                <p className="text-xs text-red-300/80">{error}</p>
              </div>
            )}

            {!error && pdfUrl && (
              <iframe
                src={`${pdfUrl}#toolbar=0&navpanes=0`}
                className="w-full h-full rounded-lg shadow-2xl border border-slate-800 bg-white"
                title="Aperçu du CV"
              />
            )}
          </div>
        )}

        {activeTab === "edit" && (
          <ResumeContentEditor
            editableContent={editableContent}
            savingContent={savingContent}
            saveSuccess={saveSuccess}
            onChangeContent={setEditableContent}
            onSubmit={handleSaveContent}
            onSkillChange={handleSkillChange}
            onBulletChange={handleBulletChange}
            onAddBullet={handleAddBullet}
            onRemoveBullet={handleRemoveBullet}
          />
        )}

        {activeTab === "ats" && (
          <ResumeAtsTab
            resumeId={resumeId}
            offerId={resume.offer_id}
            refreshKey={atsRefreshKey}
          />
        )}
      </div>
    </div>
  );
}
