"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import NewTaskModal from "@/components/tasks/NewTaskModal";
import EdittaskModal from "@/components/tasks/EditTaskModal";
import { Task, ApiTask, TaskStatus } from "@/types/tasks";
import KanbanBoard from "@/components/tasks/KanbanBoard";
import { taskApi } from "@/lib/api";
import {
  FiCheckCircle,
  FiClock,
  FiAlertTriangle,
  FiPlus,
  FiSearch,
  FiGrid,
  FiList,
  FiArchive,
  FiRefreshCw,
  FiCalendar,
  FiBriefcase,
  FiTag,
  FiZap,
} from "react-icons/fi";

const CATEGORIES = [
  "Toutes",
  "Général",
  "Candidature",
  "Réseau",
  "Entretien",
  "Administratif",
  "Formation",
];

const PREMADE_TEMPLATES = [
  { title: "Relancer le recruteur (J+7)", category: "Candidature", priority: "haute" },
  { title: "Préparer mes histoires STAR+R", category: "Entretien", priority: "haute" },
  { title: "Envoyer un email de remerciement", category: "Entretien", priority: "normale" },
  { title: "Optimiser mon profil LinkedIn & portfolio", category: "Réseau", priority: "normale" },
];

export default function TasksPage() {
  const [activeTab, setActiveTab] = useState<"active" | "archived">("active");
  const [viewMode, setViewMode] = useState<"kanban" | "list">("kanban");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Modals & Selected Task
  const [isNewTaskModalOpen, setIsNewTaskModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);

  // Search & Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("Toutes");
  const [selectedPriority, setSelectedPriority] = useState("Toutes");

  const fetchTasks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const apiTasks = await taskApi.getAll();
      if (!Array.isArray(apiTasks)) throw new Error("Format de données inattendu");

      const parsed: Task[] = apiTasks.map((t: ApiTask) => ({
        ...t,
        status: (t.status as string) as TaskStatus,
        archived: typeof t.archived === "boolean" ? t.archived : false,
      }));
      setTasks(parsed);
    } catch (err: unknown) {
      console.error("Error loading tasks:", err);
      setError("Impossible de charger vos démarches.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  // Handle Card Click -> Edit Modal
  const handleCardClick = (task: Task) => {
    setSelectedTask(task);
    setIsEditModalOpen(true);
  };

  // Quick cycle status (À faire -> En cours -> Terminée -> À faire)
  const handleQuickStatusChange = async (task: Task, nextStatus: TaskStatus) => {
    try {
      // Optimistic update
      setTasks((prev) =>
        prev.map((t) => (t._id === task._id ? { ...t, status: nextStatus } : t))
      );
      await taskApi.update(task._id!, { status: nextStatus });
    } catch (err) {
      console.error("Failed to update status:", err);
      fetchTasks();
    }
  };

  // Pre-fill a template into new task modal
  const handleUseTemplate = async (template: typeof PREMADE_TEMPLATES[0]) => {
    try {
      const payload: Omit<Task, "_id" | "user_id" | "created_at" | "updated_at"> = {
        title: template.title,
        category: template.category,
        priority: template.priority,
        status: TaskStatus.TODO,
      };
      await taskApi.create(payload);
      await fetchTasks();
    } catch (err) {
      console.error("Failed to add template task:", err);
    }
  };

  // Filter tasks based on activeTab, search, category, priority
  const activeTasks = useMemo(() => tasks.filter((t) => !t.archived), [tasks]);
  const archivedTasks = useMemo(() => tasks.filter((t) => t.archived), [tasks]);

  const displayedTasks = useMemo(() => {
    const base = activeTab === "active" ? activeTasks : archivedTasks;
    return base.filter((t) => {
      // Search
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        const matchesTitle = t.title?.toLowerCase().includes(query);
        const matchesDesc = t.description?.toLowerCase().includes(query);
        const matchesComp = t.company?.toLowerCase().includes(query);
        if (!matchesTitle && !matchesDesc && !matchesComp) return false;
      }
      // Category
      if (selectedCategory !== "Toutes") {
        if ((t.category || "Général") !== selectedCategory) return false;
      }
      // Priority
      if (selectedPriority !== "Toutes") {
        if ((t.priority || "normale") !== selectedPriority.toLowerCase()) return false;
      }
      return true;
    });
  }, [activeTab, activeTasks, archivedTasks, searchQuery, selectedCategory, selectedPriority]);

  // Statistics calculation
  const stats = useMemo(() => {
    const now = new Date();
    const nowDateOnly = new Date(now.getFullYear(), now.getMonth(), now.getDate());

    let todoCount = 0;
    let inProgressCount = 0;
    let doneCount = 0;
    let overdueCount = 0;

    activeTasks.forEach((t) => {
      const normStatus = (t.status || "").toLowerCase();
      if (normStatus === "terminée" || normStatus === "terminee") {
        doneCount++;
      } else {
        if (normStatus === "en cours") inProgressCount++;
        else todoCount++;

        if (t.due_date) {
          const due = new Date(t.due_date);
          const dueDateOnly = new Date(due.getFullYear(), due.getMonth(), due.getDate());
          if (dueDateOnly.getTime() < nowDateOnly.getTime()) {
            overdueCount++;
          }
        }
      }
    });

    return { todoCount, inProgressCount, doneCount, overdueCount, total: activeTasks.length };
  }, [activeTasks]);

  // Grouped tasks for Kanban
  const groupedTasks = useMemo(() => {
    const groups: Record<string, Task[]> = {
      "à faire": [],
      "en cours": [],
      "terminée": [],
    };

    displayedTasks.forEach((task) => {
      const norm = (task.status || "À faire").toLowerCase();
      if (norm === "terminée" || norm === "terminee") groups["terminée"].push(task);
      else if (norm === "en cours") groups["en cours"].push(task);
      else groups["à faire"].push(task);
    });

    return groups;
  }, [displayedTasks]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Top Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-center gap-2.5">
              <span>Mes démarches & Actions</span>
            </h1>
            <p className="text-xs sm:text-sm text-slate-400 max-w-2xl">
              Planifiez vos actions clés, relances et démarches personnelles. Ajoutez librement n'importe quelle tâche sans dépendre d'une offre.
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

        {/* Quick KPI Cards */}
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
              <span className="text-2xl font-black text-blue-400 mt-0.5 block">{stats.inProgressCount}</span>
            </div>
            <div className="p-3 rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20">
              <FiRefreshCw className="w-5 h-5" />
            </div>
          </div>

          <div className="bg-slate-900/70 border border-slate-800/80 rounded-2xl p-4 flex items-center justify-between shadow-md">
            <div>
              <span className="text-xs font-semibold text-slate-400 block">En retard</span>
              <span className={`text-2xl font-black mt-0.5 block ${stats.overdueCount > 0 ? "text-rose-400" : "text-slate-400"}`}>
                {stats.overdueCount}
              </span>
            </div>
            <div className={`p-3 rounded-xl border ${stats.overdueCount > 0 ? "bg-rose-500/10 text-rose-400 border-rose-500/30" : "bg-slate-800/60 text-slate-500 border-slate-700"}`}>
              <FiAlertTriangle className="w-5 h-5" />
            </div>
          </div>

          <div className="bg-slate-900/70 border border-slate-800/80 rounded-2xl p-4 flex items-center justify-between shadow-md">
            <div>
              <span className="text-xs font-semibold text-slate-400 block">Terminées</span>
              <span className="text-2xl font-black text-emerald-400 mt-0.5 block">{stats.doneCount}</span>
            </div>
            <div className="p-3 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <FiCheckCircle className="w-5 h-5" />
            </div>
          </div>
        </div>

        {/* Quick Action Suggestions (1-Click Templates) */}
        <div className="bg-slate-900/50 border border-slate-800/70 rounded-2xl p-4 backdrop-blur-sm">
          <div className="flex items-center gap-2 mb-2 text-xs font-bold text-slate-300">
            <FiZap className="text-amber-400" />
            <span>Démarches suggérées (Ajout rapide en 1 clic) :</span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {PREMADE_TEMPLATES.map((tmpl, idx) => (
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

        {/* Filter & View Toolbar */}
        <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-4 flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 shadow-md">
          <div className="flex flex-wrap items-center gap-2.5 flex-1">
            {/* Search Input */}
            <div className="relative flex-1 min-w-[200px] max-w-md">
              <FiSearch className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Rechercher une démarche, note, entreprise..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl py-2 pl-9 pr-3 text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            {/* Category Filter */}
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="bg-slate-950 border border-slate-800 rounded-xl py-2 px-3 text-xs text-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  Catégorie : {c}
                </option>
              ))}
            </select>

            {/* Priority Filter */}
            <select
              value={selectedPriority}
              onChange={(e) => setSelectedPriority(e.target.value)}
              className="bg-slate-950 border border-slate-800 rounded-xl py-2 px-3 text-xs text-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="Toutes">Priorité : Toutes</option>
              <option value="Haute">Haute priorité</option>
              <option value="Normale">Priorité normale</option>
              <option value="Basse">Basse priorité</option>
            </select>
          </div>

          <div className="flex items-center justify-between md:justify-end gap-2 border-t md:border-t-0 border-slate-800 pt-3 md:pt-0">
            {/* Active / Archived Tab Switcher */}
            <div className="flex bg-slate-950 border border-slate-800 rounded-xl p-0.5 text-xs font-semibold">
              <button
                type="button"
                onClick={() => setActiveTab("active")}
                className={`px-3 py-1.5 rounded-lg transition-colors ${
                  activeTab === "active" ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-white"
                }`}
              >
                Actives ({activeTasks.length})
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("archived")}
                className={`px-3 py-1.5 rounded-lg transition-colors ${
                  activeTab === "archived" ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-white"
                }`}
              >
                Archivées ({archivedTasks.length})
              </button>
            </div>

            {/* Kanban / List Switcher */}
            <div className="flex bg-slate-950 border border-slate-800 rounded-xl p-0.5 text-slate-400">
              <button
                type="button"
                onClick={() => setViewMode("kanban")}
                title="Vue Kanban"
                className={`p-1.5 rounded-lg transition-colors ${
                  viewMode === "kanban" ? "bg-slate-800 text-white" : "hover:text-white"
                }`}
              >
                <FiGrid className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={() => setViewMode("list")}
                title="Vue Liste"
                className={`p-1.5 rounded-lg transition-colors ${
                  viewMode === "list" ? "bg-slate-800 text-white" : "hover:text-white"
                }`}
              >
                <FiList className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Main Content Area */}
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
          /* List / Table View */
          <div className="bg-slate-900/70 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-950/60 text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-800">
                  <tr>
                    <th className="py-3 px-4">Statut</th>
                    <th className="py-3 px-4">Intitulé</th>
                    <th className="py-3 px-4">Catégorie</th>
                    <th className="py-3 px-4">Urgence</th>
                    <th className="py-3 px-4">Entreprise / Contexte</th>
                    <th className="py-3 px-4">Échéance</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-slate-300">
                  {displayedTasks.map((task) => {
                    const isDone = (task.status || "").toLowerCase() === "terminée";
                    return (
                      <tr
                        key={task._id}
                        onClick={() => handleCardClick(task)}
                        className="hover:bg-slate-800/40 cursor-pointer transition-colors"
                      >
                        <td className="py-3 px-4" onClick={(e) => e.stopPropagation()}>
                          <button
                            type="button"
                            onClick={() =>
                              handleQuickStatusChange(
                                task,
                                isDone ? TaskStatus.TODO : TaskStatus.DONE
                              )
                            }
                            className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold border transition-colors ${
                              isDone
                                ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
                                : (task.status || "").toLowerCase() === "en cours"
                                ? "bg-blue-500/20 text-blue-300 border-blue-500/30"
                                : "bg-slate-800 text-slate-400 border-slate-700 hover:text-white"
                            }`}
                          >
                            {task.status || "À faire"}
                          </button>
                        </td>

                        <td className="py-3 px-4 font-semibold text-white">
                          <span className={isDone ? "line-through text-slate-500" : ""}>
                            {task.title}
                          </span>
                          {task.description && (
                            <p className="text-[11px] text-slate-400 line-clamp-1 font-normal mt-0.5">
                              {task.description}
                            </p>
                          )}
                        </td>

                        <td className="py-3 px-4">
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-slate-800 text-slate-300 border border-slate-700">
                            {task.category || "Général"}
                          </span>
                        </td>

                        <td className="py-3 px-4">
                          {task.priority === "haute" ? (
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-rose-500/15 text-rose-300 border border-rose-500/30">
                              Urgente
                            </span>
                          ) : task.priority === "basse" ? (
                            <span className="text-slate-500 text-[11px]">Basse</span>
                          ) : (
                            <span className="text-blue-400 text-[11px] font-medium">Normale</span>
                          )}
                        </td>

                        <td className="py-3 px-4 text-slate-400">
                          {task.company ? (
                            <span className="inline-flex items-center gap-1 font-medium text-slate-300">
                              <FiBriefcase className="text-slate-500" />
                              <span>{task.company}</span>
                            </span>
                          ) : (
                            <span className="text-slate-600">—</span>
                          )}
                        </td>

                        <td className="py-3 px-4 text-slate-400 whitespace-nowrap">
                          {task.due_date ? (
                            <span className="inline-flex items-center gap-1">
                              <FiCalendar />
                              <span>{new Date(task.due_date).toLocaleDateString("fr-FR")}</span>
                            </span>
                          ) : (
                            <span className="text-slate-600">—</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Modals */}
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
