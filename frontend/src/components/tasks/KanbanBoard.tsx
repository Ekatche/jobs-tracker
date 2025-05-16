import React from "react";
import { Task, GroupedTasks, STATUS_ORDER } from "@/types/tasks";
import KanbanColumn from "./KanbanColumn";

interface KanbanBoardProps {
  groupedTasks: GroupedTasks;
  onCardClick: (task: Task) => void;
}
export default function KanbanBoard({
  groupedTasks,
  onCardClick,
}: KanbanBoardProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {STATUS_ORDER.map((status) => (
        <KanbanColumn
          key={status}
          status={status}
          tasks={groupedTasks[status] || []}
          onCardClick={onCardClick}
        />
      ))}
    </div>
  );
}
