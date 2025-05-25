"use client";
import { useEffect, useState, useCallback } from "react";
import NewTaskModal from "@/components/tasks/NewTaskModal";
import EdittaskModal from "@/components/tasks/EditTaskModal";
import { Task, ApiTask, TaskStatus } from "@/types/tasks";
import TabNavigation from "@/components/tasks/TabNavigation";
import KanbanBoard from "@/components/tasks/KanbanBoard";
import { taskApi } from "@/lib/api";

export default function TasksPage() {
  const [activeTab, setActiveTab] = useState<
    "active" | "archived" | "dashboard"
  >("active");
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [itemsPerPage] = useState<number>(8);
  const [isEditModalOpen, setIsEditModalOpen] = useState<boolean>(false);
  const [taskToEdit, setTaskToEdit] = useState<Task | null>(null);
  const [activeTasks, setActiveTasks] = useState<Task[]>([]);
  const [archivedTasks, setArchivedTasks] = useState<Task[]>([]);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [originalTask, setOriginalTask] = useState<Task | null>(null);
  const [isNewTaskModalOpen, setIsNewTaskModalOpen] = useState(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Fonction de chargement des tâches
  const fetchTasks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const apiTasks = await taskApi.getAll();
      if (!Array.isArray(apiTasks))
        throw new Error("Format de données inattendu");
      const tasks: Task[] = apiTasks.map((apiTask: ApiTask) => ({
        ...apiTask,
        status: (apiTask.status as string).toLowerCase() as TaskStatus,

        archived:
          typeof apiTask.archived === "boolean" ? apiTask.archived : false,
      }));
      setActiveTasks(tasks.filter((task) => !task.archived));
      setArchivedTasks(tasks.filter((task) => task.archived));
    } catch (err) {
      setActiveTasks([]);
      setArchivedTasks([]);
      setError("Erreur lors du chargement des tâches");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  const handleCardClick = (task: Task): void => {
    setSelectedTask(task);
    setOriginalTask(JSON.parse(JSON.stringify(task)));
    setIsEditModalOpen(true);
  };

  const handleTaskCreated = async () => {
    await fetchTasks();
    setIsNewTaskModalOpen(false);
  };

  const handleTaskUpdated = async () => {
    await fetchTasks();
    setIsEditModalOpen(false);
  };

  const handleTaskDeleted = async (taskId: string) => {
    await taskApi.delete(taskId);
    await fetchTasks();
    setIsEditModalOpen(false);
  };

  const groupedTasks = activeTasks.reduce(
    (acc, task) => {
      if (!acc[task.status]) acc[task.status] = [];
      acc[task.status].push(task);
      return acc;
    },
    {} as Record<string, Task[]>,
  );
  const groupedArchivedTasks = archivedTasks.reduce(
    (acc, task) => {
      if (!acc[task.status]) acc[task.status] = [];
      acc[task.status].push(task);
      return acc;
    },
    {} as Record<string, Task[]>,
  );

  let content = null;
  if (loading) {
    content = (
      <div className="flex items-center justify-center min-h-[200px]">
        <span className="text-blue-400 animate-pulse">
          Chargement des tâches...
        </span>
      </div>
    );
  } else if (error) {
    content = (
      <div className="flex items-center justify-center min-h-[200px]">
        <span className="text-red-400">{error}</span>
      </div>
    );
  } else if (activeTab === "active") {
    content = (
      <div className="flex-grow overflow-x-auto overflow-y-hidden custom-scrollbar">
        <KanbanBoard
          groupedTasks={groupedTasks}
          onCardClick={handleCardClick}
        />
      </div>
    );
  } else if (activeTab === "archived") {
    content = (
      <div className="flex-grow overflow-x-auto overflow-y-hidden custom-scrollbar">
        <KanbanBoard
          groupedTasks={groupedArchivedTasks}
          onCardClick={handleCardClick}
        />
      </div>
    );
  } else if (activeTab === "dashboard") {
    content = (
      <div>
        <h2 className="text-xl font-semibold mb-2">Dashboard</h2>
        <div className="flex gap-8">
          <div className="bg-blue-900 rounded-lg p-4 flex-1">
            <div className="text-2xl font-bold">{activeTasks.length}</div>
            <div className="text-sm text-gray-400">Tâches actives</div>
          </div>
          <div className="bg-blue-900 rounded-lg p-4 flex-1">
            <div className="text-2xl font-bold">{archivedTasks.length}</div>
            <div className="text-sm text-gray-400">Tâches archivées</div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-blue-night text-white p-6">
      <div className="max-w-7xl mx-auto">
        <div className="grid grid-cols-1 gap-6 mb-6">
          {/* Header */}
          <div className="flex items-center space-x-2">
            <svg
              className="w-6 h-6 text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
              ></path>
            </svg>
            <h2 className="text-xl font-semibold">Mes Demarches</h2>
          </div>

          {/* Bloc principal avec fond et arrondi */}
          <div className="bg-blue-night-lighter rounded-lg shadow-lg overflow-hidden">
            {/* Onglets */}
            <div className="p-4 border-b border-gray-700 flex items-center">
              <div className="flex-1">
                <TabNavigation
                  activeTab={activeTab}
                  setActiveTab={setActiveTab}
                  setCurrentPage={setCurrentPage}
                  activeCount={activeTasks.length}
                  archivedCount={archivedTasks.length}
                  onAddTask={() => setIsNewTaskModalOpen(true)}
                />
              </div>
            </div>
            <NewTaskModal
              isOpen={isNewTaskModalOpen}
              onClose={() => setIsNewTaskModalOpen(false)}
              onSuccess={handleTaskCreated}
            />
            <EdittaskModal
              isOpen={isEditModalOpen}
              onClose={() => setIsEditModalOpen(false)}
              onSuccess={handleTaskUpdated}
              onDelete={handleTaskDeleted}
              task={selectedTask}
            />
            {/* Contenu */}
            <div className="p-6">{content}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
