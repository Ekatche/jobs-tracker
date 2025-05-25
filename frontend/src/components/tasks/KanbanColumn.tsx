import React from "react";

import { Task, getStatusBackgroundColor } from "@/types/tasks";
import TaskCards from "./TaskCard";

interface KanbanColumnProps {
  status: string;
  tasks: Task[];
  onCardClick: (application: Task) => void;
}

export default function KanbanColumn({
  status,
  tasks,
  onCardClick,
}: KanbanColumnProps) {
  return (
    <div className="flex flex-col h-full">
      <div
        className={`${getStatusBackgroundColor(status)} rounded-md px-3 py-2 mb-2 text-white font-medium flex flex-col items-center`}
      >
        <span>{status}</span>
        <span className="text-xs bg-gray-700 px-2 py-0.5 rounded-full mt-1">
          {tasks?.length || 0}
        </span>
      </div>
      <div className="space-y-2 flex-grow overflow-y-auto max-h-[500px] pr-1 custom-scrollbar">
        {tasks
          ?.slice(0, 5)
          .map((app) => (
            <TaskCards
              key={app._id}
              task={app}
              status={status}
              onClick={onCardClick}
              compact={false}
            />
          ))}
        {(!tasks || tasks.length === 0) && (
          <div className="text-gray-400 text-center p-4">Aucune Demarches</div>
        )}
      </div>
    </div>
  );
}
