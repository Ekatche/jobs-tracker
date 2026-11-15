"use client";

import NewTaskModal from "@/components/tasks/NewTaskModal";
import EdittaskModal from "@/components/tasks/EditTaskModal";
import KanbanBoard from "@/components/tasks/KanbanBoard";
import TasksListView from "@/components/tasks/TasksListView";
import TasksFilterToolbar from "@/components/tasks/TasksFilterToolbar";
import { useTasksPage, TASK_TEMPLATES } from "@/hooks/useTasksPage";
import {
  FiCheckCircle,
  FiClock,
  FiAlertTriangle,
  FiPlus,
  FiRefreshCw,
  FiZap,
} from "react-icons/fi";

export default function TasksPage() {
  const {
    activeTab,
    setActiveTab,
    viewMode,
    setViewMode,
    tasks,
    loading,
    error,
    isNewTaskModalOpen,
    setIsNewTaskModalOpen,
    isEditModalOpen,
    setIsEditModalOpen,
    selectedTask,
    searchQuery,
    setSearchQuery,
    selectedCategory,
    setSelectedCategory,
    selectedPriority,
    setSelectedPriority,
    activeTasks,
    archivedTasks,
    displayedTasks,
    stats,
    groupedTasks,
    fetchTasks,
    handleCardClick,
    handleQuickStatusChange,
    handleUseTemplate,
  } = useTasksPage();

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-center gap-2.5">
              <span>Mes démarches &amp; Actions</span>
            </h1>
            <p className="text-xs sm:text-sm text-slate-400 max-w-2xl">
              Planifiez vos actions clés, relances et démarches personnelles. Ajoutez librement
              n&apos;importe quelle tâche sans dépendre d&apos;une offre.
            </p>
          </div>

          <div className="flex items-center gap-2.5 shrink-0">
            <button
              type="button"
              onClick={fetchTasks}
              title="Rafraîchir"
              className="p-2.5 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-400 hover:text-white transition-colors"
            >
              <FiRefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            </button>

            <button
              type="button"
              onClick={() => setIsNewTaskModalOpen(true)}
              className="px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs sm:text-sm font-bold flex items-center gap-2 transition-all shadow-lg shadow-indigo-500/25"
            >
              <FiPlus className="w-4 h-4" />
              <span>Nouvelle démarche</span>
            </button>
          </div>
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
          <div className="bg-slate-900/70 border border-slate-800/80 rounded-2xl p-4 flex items-center justify-between shadow-md">
            <div>
              <span className="text-xs font-semibold text-slate-400 block">À faire</span>
              <span className="text-2xl font-black text-white mt-0.5 block">{stats.todoCount}</span>
            </div>
            <div className="p-3 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <FiClock className="w-5 h-5" />
            </div>
          </div>

          <div className="bg-slate-900/70 border border-slate-800/80 rounded-2xl p-4 flex items-center justify-between shadow-md">
            <div>
              <span className="text-xs font-semibold text-slate-400 block">En cours</span>
              <span className="text-2xl font-black text-blue-400 mt-0.5 block">
                {stats.inProgressCount}
              </span>
            </div>
            <div className="p-3 rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20">
              <FiRefreshCw className="w-5 h-5" />
            </div>
          </div>

          <div className="bg-slate-900/70 border border-slate-800/80 rounded-2xl p-4 flex items-center justify-between shadow-md">
            <div>
              <span className="text-xs font-semibold text-slate-400 block">En retard</span>
              <span
                className={`text-2xl font-black mt-0.5 block ${
                  stats.overdueCount > 0 ? "text-rose-400" : "text-slate-400"
                }`}
              >
                {stats.overdueCount}
              </span>
            </div>
            <div
              className={`p-3 rounded-xl border ${
                stats.overdueCount > 0
                  ? "bg-rose-500/10 text-rose-400 border-rose-500/30"
                  : "bg-slate-800/60 text-slate-500 border-slate-700"
              }`}
            >
              <FiAlertTriangle className="w-5 h-5" />
            </div>
          </div>

          <div className="bg-slate-900/70 border border-slate-800/80 rounded-2xl p-4 flex items-center justify-between shadow-md">
            <div>
              <span className="text-xs font-semibold text-slate-400 block">Terminées</span>
              <span className="text-2xl font-black text-emerald-400 mt-0.5 block">
                {stats.doneCount}
              </span>
            </div>
            <div className="p-3 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <FiCheckCircle className="w-5 h-5" />
            </div>
          </div>
        </div>

        <div className="bg-slate-900/50 border border-slate-800/70 rounded-2xl p-4 backdrop-blur-sm">
          <div className="flex items-center gap-2 mb-2 text-xs font-bold text-slate-300">
            <FiZap className="text-amber-400" />
            <span>Démarches suggérées (Ajout rapide en 1 clic) :</span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {TASK_TEMPLATES.map((tmpl, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => handleUseTemplate(tmpl)}
                className="px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 hover:border-indigo-500/50 text-slate-300 hover:text-white text-xs font-medium flex items-center gap-1.5 transition-all shadow-sm"
              >
                <FiPlus className="text-indigo-400" />
                <span>{tmpl.title}</span>
              </button>
            ))}
          </div>
        </div>

        <TasksFilterToolbar
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          selectedCategory={selectedCategory}
          onCategoryChange={setSelectedCategory}
          selectedPriority={selectedPriority}
          onPriorityChange={setSelectedPriority}
          activeTab={activeTab}
          onTabChange={setActiveTab}
          activeCount={activeTasks.length}
          archivedCount={archivedTasks.length}
          viewMode={viewMode}
          onViewModeChange={setViewMode}
        />

        {loading && tasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-16 text-slate-400 space-y-3">
            <FiRefreshCw className="w-8 h-8 animate-spin text-indigo-400" />
            <p className="text-sm">Chargement de vos démarches...</p>
          </div>
        ) : error ? (
          <div className="p-6 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-center text-sm">
            {error}
          </div>
        ) : displayedTasks.length === 0 ? (
          <div className="text-center py-16 px-4 rounded-2xl bg-slate-900/40 border border-dashed border-slate-800">
            <FiCheckCircle className="w-10 h-10 text-slate-600 mx-auto mb-3" />
            <h3 className="text-base font-bold text-slate-300">Aucune démarche trouvée</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
              {searchQuery || selectedCategory !== "Toutes" || selectedPriority !== "Toutes"
                ? "Aucune démarche ne correspond à vos filtres actuels."
                : "Vous n'avez pas encore de démarche active. Cliquez ci-dessous pour en créer une."}
            </p>
            <button
              type="button"
              onClick={() => setIsNewTaskModalOpen(true)}
              className="mt-4 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl transition-colors inline-flex items-center gap-2"
            >
              <FiPlus />
              <span>Créer ma première démarche</span>
            </button>
          </div>
        ) : viewMode === "kanban" ? (
          <KanbanBoard
            groupedTasks={groupedTasks}
            onCardClick={handleCardClick}
            onQuickStatusChange={handleQuickStatusChange}
          />
        ) : (
          <TasksListView
            tasks={displayedTasks}
            onCardClick={handleCardClick}
            onQuickStatusChange={handleQuickStatusChange}
          />
        )}

        <NewTaskModal
          isOpen={isNewTaskModalOpen}
          onClose={() => setIsNewTaskModalOpen(false)}
          onSuccess={fetchTasks}
        />

        <EdittaskModal
          isOpen={isEditModalOpen}
          onClose={() => setIsEditModalOpen(false)}
          onSuccess={fetchTasks}
          onDelete={fetchTasks}
          task={selectedTask}
        />
      </div>
    </div>
  );
}
