"use client";

import React from "react";
import { Task, TaskStatus } from "@/types/tasks";
import TaskCard from "./TaskCard";

interface KanbanColumnProps {
  status: string;
  tasks: Task[];
  onCardClick: (task: Task) => void;
  onQuickStatusChange?: (task: Task, nextStatus: TaskStatus) => void;
}

const STATUS_THEMES: Record<string, { label: string; headerBg: string; border: string; dot: string }> = {
  "à faire": {
    label: "À faire",
    headerBg: "bg-indigo-950/40 text-indigo-300 border-indigo-500/30",
    border: "border-indigo-500/20",
    dot: "bg-indigo-400",
  },
  "en cours": {
    label: "En cours",
    headerBg: "bg-blue-950/40 text-blue-300 border-blue-500/30",
    border: "border-blue-500/20",
    dot: "bg-blue-400",
  },
  "terminée": {
    label: "Terminée",
    headerBg: "bg-emerald-950/40 text-emerald-300 border-emerald-500/30",
    border: "border-emerald-500/20",
    dot: "bg-emerald-400",
  },
};

export default function KanbanColumn({
  status,
  tasks,
  onCardClick,
  onQuickStatusChange,
}: KanbanColumnProps) {
  const normKey = status.toLowerCase();
  const theme = STATUS_THEMES[normKey] || {
    label: status,
    headerBg: "bg-slate-900 text-slate-300 border-slate-700",
    border: "border-slate-800",
    dot: "bg-slate-400",
  };

  return (
    <div className="flex flex-col bg-slate-900/40 border border-slate-800/80 rounded-2xl p-3 min-h-[420px]">
      {/* Column Header */}
      <div className={`rounded-xl px-3.5 py-2.5 mb-3 border flex items-center justify-between ${theme.headerBg}`}>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${theme.dot}`} />
          <span className="text-xs font-bold uppercase tracking-wider">{theme.label}</span>
        </div>
        <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-slate-900/60 border border-slate-700/60">
          {tasks?.length || 0}
        </span>
      </div>

      {/* Cards List */}
      <div className="space-y-2.5 flex-grow overflow-y-auto max-h-[650px] pr-1 custom-scrollbar">
        {tasks && tasks.length > 0 ? (
          tasks.map((task) => (
            <TaskCard
              key={task._id}
              task={task}
              status={status}
              onClick={onCardClick}
              onQuickStatusChange={onQuickStatusChange}
            />
          ))
        ) : (
          <div className="text-slate-500 text-xs text-center py-10 border border-dashed border-slate-800/80 rounded-xl">
            Aucune démarche dans cette colonne
          </div>
        )}
      </div>
    </div>
  );
}
