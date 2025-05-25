import { Task, getStatusColor } from "@/types/tasks";
import { useState } from "react";
import { calculateDays } from "@/types/application";
interface TaskCardProps {
  task: Task;
  status: string;
  onClick: (task: Task) => void;
  compact?: boolean;
}

// Correction du nom du composant : TaskCard (singulier) pour chaque carte, TaskCards (pluriel) pour la liste
export default function TaskCards({ task, status, onClick }: TaskCardProps) {
  const [completedTasks, setCompletedTasks] = useState<{
    [id: string]: boolean;
  }>({});

  const toggleTaskCompleted = (id: string) => {
    return { type: "TOGGLE_TASK_COMPLETED", payload: id };
  };

  const getDate = (dateString: string) => {
    const dateObject = new Date(dateString);
    return dateObject.toLocaleDateString();
  };

  const handleToggleCompleted = (id: string) => {
    setCompletedTasks((prev) => ({
      ...prev,
      [id]: true,
    }));
  };

  return (
    <div
      className={`${getStatusColor(status)} rounded-md p-4 cursor-pointer hover:bg-opacity-80 transition-all`}
      onClick={() => onClick(task)}
    >
      <div className="flex items-center mb-1">
        <div className="overflow-hidden">
          <h3 className="font-semibold text-sm whitespace-nowrap overflow-hidden text-ellipsis">
            {task.title}
          </h3>
          <p className="text-xs text-gray-300 whitespace-nowrap overflow-hidden text-ellipsis">
            {task.description}
          </p>
        </div>
      </div>

      <div className="text-xs text-gray-400">
        {task.created_at ? calculateDays(task.created_at) : 0} j
      </div>
    </div>
  );
}
