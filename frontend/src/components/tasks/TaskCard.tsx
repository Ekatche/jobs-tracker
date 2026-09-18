"use client";

import React from "react";
import { Task, TaskStatus } from "@/types/tasks";
import {
  FiCalendar,
  FiAlertTriangle,
  FiBriefcase,
  FiCheck,
  FiClock,
  FiTag,
} from "react-icons/fi";

interface TaskCardProps {
  task: Task;
  status: string;
  onClick: (task: Task) => void;
  onQuickStatusChange?: (task: Task, nextStatus: TaskStatus) => void;
}

const CATEGORY_COLORS: Record<string, string> = {
  Candidature: "bg-blue-500/15 text-blue-300 border-blue-500/30",
  Entretien: "bg-purple-500/15 text-purple-300 border-purple-500/30",
  Réseau: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  Formation: "bg-cyan-500/15 text-cyan-300 border-cyan-500/30",
  Administratif: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  Général: "bg-slate-800 text-slate-300 border-slate-700",
};

export default function TaskCard({
  task,
  status,
  onClick,
  onQuickStatusChange,
}: TaskCardProps) {
  const isDone = task.status === TaskStatus.DONE || status.toLowerCase() === "terminée";

  // Calcul du statut d'échéance
  let dueText: string | null = null;
  let isOverdue = false;
  let isDueToday = false;

  if (task.due_date) {
    const due = new Date(task.due_date);
    const now = new Date();
    // Compare dates at midnight
    const dueDateOnly = new Date(due.getFullYear(), due.getMonth(), due.getDate());
    const nowDateOnly = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const diffDays = Math.round((dueDateOnly.getTime() - nowDateOnly.getTime()) / (1000 * 60 * 60 * 24));

    if (diffDays < 0 && !isDone) {
      isOverdue = true;
      dueText = `En retard (${Math.abs(diffDays)} j)`;
    } else if (diffDays === 0) {
      isDueToday = true;
      dueText = "Aujourd'hui";
    } else {
      dueText = dueDateOnly.toLocaleDateString("fr-FR", { day: "2-digit", month: "short" });
    }
  }

  const categoryStyle = CATEGORY_COLORS[task.category || "Général"] || CATEGORY_COLORS["Général"];

  const handleNextStatus = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!onQuickStatusChange) return;

    if (task.status === TaskStatus.TODO) {
      onQuickStatusChange(task, TaskStatus.IN_PROGRESS);
    } else if (task.status === TaskStatus.IN_PROGRESS) {
      onQuickStatusChange(task, TaskStatus.DONE);
    } else {
      onQuickStatusChange(task, TaskStatus.TODO);
    }
  };

  return (
    <div
      onClick={() => onClick(task)}
      className="bg-slate-900/80 border border-slate-800/90 hover:border-slate-700 rounded-xl p-4 cursor-pointer transition-all duration-200 shadow-md hover:shadow-indigo-500/5 group flex flex-col justify-between gap-3"
    >
      <div className="space-y-2">
        {/* Badges Bar */}
        <div className="flex flex-wrap items-center justify-between gap-1.5">
          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md border uppercase tracking-wider ${categoryStyle}`}>
            {task.category || "Général"}
          </span>

          <div className="flex items-center gap-1.5">
            {task.priority === "haute" && (
              <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-rose-500/15 text-rose-300 border border-rose-500/30">
                Urgente
              </span>
            )}
            {task.priority === "basse" && (
              <span className="px-1.5 py-0.5 rounded text-[10px] font-medium text-slate-400 bg-slate-800/80 border border-slate-700">
                Secondaire
              </span>
            )}
          </div>
        </div>

        {/* Titre */}
        <h4 className={`text-sm font-semibold text-white leading-snug group-hover:text-indigo-300 transition-colors ${isDone ? "line-through text-slate-400" : ""}`}>
          {task.title}
        </h4>

        {/* Description si présente */}
        {task.description && (
          <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed">
            {task.description}
          </p>
        )}
      </div>

      {/* Footer Info & Quick Action */}
      <div className="flex items-center justify-between pt-2 border-t border-slate-800/70 text-xs">
        <div className="flex items-center gap-2 text-slate-400 truncate">
          {task.company && (
            <span className="inline-flex items-center gap-1 text-[11px] font-medium text-indigo-300 truncate max-w-[130px]">
              <FiBriefcase className="shrink-0 text-slate-500" />
              <span className="truncate">{task.company}</span>
            </span>
          )}

          {dueText && (
            <span
              className={`inline-flex items-center gap-1 text-[11px] font-medium px-1.5 py-0.5 rounded ${
                isOverdue
                  ? "bg-rose-500/15 text-rose-300 border border-rose-500/30 font-bold"
                  : isDueToday
                  ? "bg-amber-500/15 text-amber-300 border border-amber-500/30 font-semibold"
                  : "text-slate-400"
              }`}
            >
              {isOverdue ? <FiAlertTriangle className="shrink-0 text-rose-400" /> : <FiCalendar className="shrink-0" />}
              <span>{dueText}</span>
            </span>
          )}
        </div>

        {/* Quick status cycle button */}
        {onQuickStatusChange && (
          <button
            type="button"
            onClick={handleNextStatus}
            title={
              task.status === TaskStatus.TODO
                ? "Passer en cours"
                : task.status === TaskStatus.IN_PROGRESS
                ? "Marquer comme terminée"
                : "Rouvrir (à faire)"
            }
            className={`p-1.5 rounded-lg border transition-colors ${
              isDone
                ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/30 hover:bg-emerald-500/30"
                : task.status === TaskStatus.IN_PROGRESS
                ? "bg-blue-500/20 text-blue-300 border-blue-500/30 hover:bg-blue-500/30"
                : "bg-slate-800 text-slate-400 border-slate-700 hover:text-white"
            }`}
          >
            {isDone ? <FiCheck className="w-3.5 h-3.5" /> : <FiClock className="w-3.5 h-3.5" />}
          </button>
        )}
      </div>
    </div>
  );
}
