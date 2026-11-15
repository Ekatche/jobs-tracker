"use client";

import ApplicationDetails from "@/components/applications/ApplicationDetails";
import NewApplicationModal from "@/components/dashboard/NewApplicationModal";
import CalibrationModal from "@/components/applications/CalibrationModal";
import { ApplicationsHeaderBar } from "@/components/applications/ApplicationsHeaderBar";
import { ApplicationsKanbanView } from "@/components/applications/ApplicationsKanbanView";
import { ApplicationsTableView } from "@/components/applications/ApplicationsTableView";
import { useApplicationsPage } from "@/hooks/useApplicationsPage";
import { FiAlertCircle, FiRefreshCw } from "react-icons/fi";

export default function ApplicationsPage() {
  const ap = useApplicationsPage();

  return (
    <div className="h-[calc(100dvh-64px)] flex flex-col overflow-hidden bg-blue-night text-white">
      <ApplicationsHeaderBar
        applications={ap.applications}
        summary={ap.summary}
        scoredOffersCount={ap.scoredOffersCount}
        searchTerm={ap.searchTerm}
        filterAlertOnly={ap.filterAlertOnly}
        viewMode={ap.viewMode}
        refreshing={ap.refreshing}
        onSearchChange={ap.setSearchTerm}
        onToggleAlertFilter={() => ap.setFilterAlertOnly(!ap.filterAlertOnly)}
        onOpenCalibration={() => ap.setIsCalibrationOpen(true)}
        onViewModeChange={ap.setViewMode}
        onRefresh={() => ap.fetchData(false)}
        onOpenNewModal={() => {
          ap.setPrefilledData(undefined);
          ap.setIsNewAppModalOpen(true);
        }}
      />

      <div className="flex-1 min-h-0 flex flex-col p-4 overflow-hidden">
        {ap.loading ? (
          <div className="flex-1 flex items-center justify-center py-24 text-gray-400 gap-3">
            <FiRefreshCw className="w-6 h-6 animate-spin text-blue-400" />
            <span className="text-sm font-medium">Chargement des candidatures...</span>
          </div>
        ) : ap.error ? (
          <div className="flex-1 flex items-center justify-center py-24 text-rose-400 gap-2">
            <FiAlertCircle className="w-5 h-5" />
            <span className="text-sm">{ap.error}</span>
          </div>
        ) : ap.viewMode === "kanban" ? (
          <ApplicationsKanbanView
            columns={ap.columns}
            onCardClick={ap.handleCardClick}
            onTransitionStatus={ap.handleTransitionStatus}
          />
        ) : (
          <ApplicationsTableView
            applications={ap.filteredApplications}
            onRowClick={ap.handleCardClick}
          />
        )}
      </div>

      <ApplicationDetails
        application={ap.selectedApplication}
        originalApplication={ap.originalApplication}
        onClose={ap.handleBackClick}
        onChange={ap.handleFieldChange}
        onSave={ap.handleSaveChanges}
        onCancel={ap.handleCancelChanges}
        onDelete={ap.handleDeleteApplication}
        onArchive={ap.handleToggleArchive}
        onAddNote={ap.handleAddNote}
        onEditNote={ap.handleEditNote}
        onDeleteNote={ap.handleDeleteNote}
        hasUnsavedChanges={ap.hasUnsavedChanges}
        isAddingNote={ap.isAddingNote}
        isDeletingNote={ap.isDeletingNote}
        deletingNoteIndex={ap.deletingNoteIndex}
      />

      <NewApplicationModal
        isOpen={ap.isNewAppModalOpen}
        onClose={() => {
          ap.setIsNewAppModalOpen(false);
          ap.setPrefilledData(undefined);
        }}
        onSuccess={() => {
          ap.setIsNewAppModalOpen(false);
          ap.setPrefilledData(undefined);
          ap.fetchData(false);
          ap.addNotification("success", "Candidature ajoutée avec succès");
        }}
        prefilledData={ap.prefilledData}
      />

      <CalibrationModal
        isOpen={ap.isCalibrationOpen}
        onClose={() => ap.setIsCalibrationOpen(false)}
      />
    </div>
  );
}
