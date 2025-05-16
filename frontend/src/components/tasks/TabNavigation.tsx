import React from "react";
import { FiPlus } from "react-icons/fi";

interface TabNavigationProps {
  activeTab: "active" | "archived" | "dashboard";
  setActiveTab: (tab: "active" | "archived" | "dashboard") => void;
  setCurrentPage: (page: number) => void;
  activeCount: number;
  archivedCount: number;
  onAddTask?: () => void; // Ajout du callback
}

export default function TabNavigation({
  activeTab,
  setActiveTab,
  setCurrentPage,
  activeCount,
  archivedCount,
  onAddTask,
}: TabNavigationProps) {
  return (
    <div className="flex items-center border-b border-gray-700">
      <div className="flex flex-1">
        <button
          className={`px-6 py-3 text-sm font-medium ${
            activeTab === "active"
              ? "text-white border-b-2 border-blue-500"
              : "text-gray-400 hover:text-white"
          }`}
          onClick={() => {
            setActiveTab("active");
            setCurrentPage(1);
          }}
        >
          En cours ({activeCount})
        </button>
        <button
          className={`px-6 py-3 text-sm font-medium ${
            activeTab === "archived"
              ? "text-white border-b-2 border-blue-500"
              : "text-gray-400 hover:text-white"
          }`}
          onClick={() => {
            setActiveTab("archived");
            setCurrentPage(1);
          }}
        >
          Archivées ({archivedCount})
        </button>
        <button
          className={`px-6 py-3 text-sm font-medium ${
            activeTab === "dashboard"
              ? "text-white border-b-2 border-blue-500"
              : "text-gray-400 hover:text-white"
          }`}
          onClick={() => {
            setActiveTab("dashboard");
            setCurrentPage(1);
          }}
        >
          Tableau de bord
        </button>
      </div>
      <button
        onClick={onAddTask}
        className="ml-4 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-colors flex items-center gap-2 font-medium"
        title="Nouvelle tâche"
        type="button"
      >
        <span>Nouvelle tâche</span>
        <FiPlus className="w-4 h-4" />
      </button>
    </div>
  );
}
