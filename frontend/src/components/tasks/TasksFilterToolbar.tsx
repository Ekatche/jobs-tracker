"use client";

import { FiSearch, FiGrid, FiList } from "react-icons/fi";
import { TASK_CATEGORIES } from "@/hooks/useTasksPage";

interface TasksFilterToolbarProps {
  searchQuery: string;
  onSearchChange: (value: string) => void;
  selectedCategory: string;
  onCategoryChange: (value: string) => void;
  selectedPriority: string;
  onPriorityChange: (value: string) => void;
  activeTab: "active" | "archived";
  onTabChange: (tab: "active" | "archived") => void;
  activeCount: number;
  archivedCount: number;
  viewMode: "kanban" | "list";
  onViewModeChange: (mode: "kanban" | "list") => void;
}

export default function TasksFilterToolbar({
  searchQuery,
  onSearchChange,
  selectedCategory,
  onCategoryChange,
  selectedPriority,
  onPriorityChange,
  activeTab,
  onTabChange,
  activeCount,
  archivedCount,
  viewMode,
  onViewModeChange,
}: TasksFilterToolbarProps) {
  return (
    <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-4 flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 shadow-md">
      <div className="flex flex-wrap items-center gap-2.5 flex-1">
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <FiSearch className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Rechercher une démarche, note, entreprise..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded-xl py-2 pl-9 pr-3 text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>

        <select
          value={selectedCategory}
          onChange={(e) => onCategoryChange(e.target.value)}
          className="bg-slate-950 border border-slate-800 rounded-xl py-2 px-3 text-xs text-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          {TASK_CATEGORIES.map((c) => (
            <option key={c} value={c}>
              Catégorie : {c}
            </option>
          ))}
        </select>

        <select
          value={selectedPriority}
          onChange={(e) => onPriorityChange(e.target.value)}
          className="bg-slate-950 border border-slate-800 rounded-xl py-2 px-3 text-xs text-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <option value="Toutes">Priorité : Toutes</option>
          <option value="Haute">Haute priorité</option>
          <option value="Normale">Priorité normale</option>
          <option value="Basse">Basse priorité</option>
        </select>
      </div>

      <div className="flex items-center justify-between md:justify-end gap-2 border-t md:border-t-0 border-slate-800 pt-3 md:pt-0">
        <div className="flex bg-slate-950 border border-slate-800 rounded-xl p-0.5 text-xs font-semibold">
          <button
            type="button"
            onClick={() => onTabChange("active")}
            className={`px-3 py-1.5 rounded-lg transition-colors ${
              activeTab === "active"
                ? "bg-indigo-600 text-white"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Actives ({activeCount})
          </button>
          <button
            type="button"
            onClick={() => onTabChange("archived")}
            className={`px-3 py-1.5 rounded-lg transition-colors ${
              activeTab === "archived"
                ? "bg-indigo-600 text-white"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Archivées ({archivedCount})
          </button>
        </div>

        <div className="flex bg-slate-950 border border-slate-800 rounded-xl p-0.5 text-slate-400">
          <button
            type="button"
            onClick={() => onViewModeChange("kanban")}
            title="Vue Kanban"
            className={`p-1.5 rounded-lg transition-colors ${
              viewMode === "kanban" ? "bg-slate-800 text-white" : "hover:text-white"
            }`}
          >
            <FiGrid className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={() => onViewModeChange("list")}
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
  );
}
