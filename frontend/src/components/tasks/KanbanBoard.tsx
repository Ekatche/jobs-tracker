"use client";

import React from "react";
import { Task, GroupedTasks, STATUS_ORDER, TaskStatus } from "@/types/tasks";
import KanbanColumn from "./KanbanColumn";

interface KanbanBoardProps {
  groupedTasks: GroupedTasks;
  onCardClick: (task: Task) => void;
  onQuickStatusChange?: (task: Task, nextStatus: TaskStatus) => void;
}

export default function KanbanBoard({
  groupedTasks,
  onCardClick,
  onQuickStatusChange,
}: KanbanBoardProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {STATUS_ORDER.map((status) => (
        <KanbanColumn
          key={status}
          status={status}
          tasks={groupedTasks[status] || []}
          onCardClick={onCardClick}
          onQuickStatusChange={onQuickStatusChange}
        />
      ))}
    </div>
  );
}
