"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { Task, ApiTask, TaskStatus } from "@/types/tasks";
import { taskApi } from "@/lib/api";

export const TASK_CATEGORIES = [
  "Toutes",
  "Général",
  "Candidature",
  "Réseau",
  "Entretien",
  "Administratif",
  "Formation",
];

export const TASK_TEMPLATES = [
  { title: "Relancer le recruteur (J+7)", category: "Candidature", priority: "haute" },
  { title: "Préparer mes histoires STAR+R", category: "Entretien", priority: "haute" },
  { title: "Envoyer un email de remerciement", category: "Entretien", priority: "normale" },
  { title: "Optimiser mon profil LinkedIn & portfolio", category: "Réseau", priority: "normale" },
];

/**
 * Manages task list fetching, optimistic status updates, filters, KPIs, and Kanban grouping.
 */
export function useTasksPage() {
  const [activeTab, setActiveTab] = useState<"active" | "archived">("active");
  const [viewMode, setViewMode] = useState<"kanban" | "list">("kanban");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [isNewTaskModalOpen, setIsNewTaskModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);

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

  const handleCardClick = (task: Task) => {
    setSelectedTask(task);
    setIsEditModalOpen(true);
  };

  const handleQuickStatusChange = async (task: Task, nextStatus: TaskStatus) => {
    try {
      setTasks((prev) =>
        prev.map((t) => (t._id === task._id ? { ...t, status: nextStatus } : t))
      );
      await taskApi.update(task._id!, { status: nextStatus });
    } catch (err) {
      console.error("Failed to update status:", err);
      fetchTasks();
    }
  };

  const handleUseTemplate = async (template: (typeof TASK_TEMPLATES)[0]) => {
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

  const activeTasks = useMemo(() => tasks.filter((t) => !t.archived), [tasks]);
  const archivedTasks = useMemo(() => tasks.filter((t) => t.archived), [tasks]);

  const displayedTasks = useMemo(() => {
    const base = activeTab === "active" ? activeTasks : archivedTasks;
    return base.filter((t) => {
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        const matchesTitle = t.title?.toLowerCase().includes(query);
        const matchesDesc = t.description?.toLowerCase().includes(query);
        const matchesComp = t.company?.toLowerCase().includes(query);
        if (!matchesTitle && !matchesDesc && !matchesComp) return false;
      }
      if (selectedCategory !== "Toutes" && (t.category || "Général") !== selectedCategory) {
        return false;
      }
      if (
        selectedPriority !== "Toutes" &&
        (t.priority || "normale") !== selectedPriority.toLowerCase()
      ) {
        return false;
      }
      return true;
    });
  }, [activeTab, activeTasks, archivedTasks, searchQuery, selectedCategory, selectedPriority]);

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
          if (dueDateOnly.getTime() < nowDateOnly.getTime()) overdueCount++;
        }
      }
    });

    return { todoCount, inProgressCount, doneCount, overdueCount, total: activeTasks.length };
  }, [activeTasks]);

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

  return {
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
  };
}
