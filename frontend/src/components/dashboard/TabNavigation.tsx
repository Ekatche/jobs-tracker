import React from "react";

interface TabNavigationProps {
  activeTab: "active" | "archived";
  setActiveTab: (tab: "active" | "archived") => void;
  setCurrentPage: (page: number) => void;
  activeCount: number;
  archivedCount: number;
}

export default function TabNavigation({
  activeTab,
  setActiveTab,
  setCurrentPage,
  activeCount,
  archivedCount,
}: TabNavigationProps) {
  return (
    <div className="flex border-b border-gray-700">
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
    </div>
  );
}
