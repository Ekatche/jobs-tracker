"use client";

import { FiBriefcase, FiCalendar } from "react-icons/fi";
import { Task, TaskStatus } from "@/types/tasks";

interface TasksListViewProps {
  tasks: Task[];
  onCardClick: (task: Task) => void;
  onQuickStatusChange: (task: Task, nextStatus: TaskStatus) => void;
}

export default function TasksListView({
  tasks,
  onCardClick,
  onQuickStatusChange,
}: TasksListViewProps) {
  return (
    <div className="bg-slate-900/70 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-950/60 text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-800">
            <tr>
              <th className="py-3 px-4">Statut</th>
              <th className="py-3 px-4">Intitulé</th>
              <th className="py-3 px-4">Catégorie</th>
              <th className="py-3 px-4">Urgence</th>
              <th className="py-3 px-4">Entreprise / Contexte</th>
              <th className="py-3 px-4">Échéance</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 text-slate-300">
            {tasks.map((task) => {
              const isDone = (task.status || "").toLowerCase() === "terminée";
              return (
                <tr
                  key={task._id}
                  onClick={() => onCardClick(task)}
                  className="hover:bg-slate-800/40 cursor-pointer transition-colors"
                >
                  <td className="py-3 px-4" onClick={(e) => e.stopPropagation()}>
                    <button
                      type="button"
                      onClick={() =>
                        onQuickStatusChange(
                          task,
                          isDone ? TaskStatus.TODO : TaskStatus.DONE
                        )
                      }
                      className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold border transition-colors ${
                        isDone
                          ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
                          : (task.status || "").toLowerCase() === "en cours"
                          ? "bg-blue-500/20 text-blue-300 border-blue-500/30"
                          : "bg-slate-800 text-slate-400 border-slate-700 hover:text-white"
                      }`}
                    >
                      {task.status || "À faire"}
                    </button>
                  </td>

                  <td className="py-3 px-4 font-semibold text-white">
                    <span className={isDone ? "line-through text-slate-500" : ""}>
                      {task.title}
                    </span>
                    {task.description && (
                      <p className="text-[11px] text-slate-400 line-clamp-1 font-normal mt-0.5">
                        {task.description}
                      </p>
                    )}
                  </td>

                  <td className="py-3 px-4">
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-slate-800 text-slate-300 border border-slate-700">
                      {task.category || "Général"}
                    </span>
                  </td>

                  <td className="py-3 px-4">
                    {task.priority === "haute" ? (
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-rose-500/15 text-rose-300 border border-rose-500/30">
                        Urgente
                      </span>
                    ) : task.priority === "basse" ? (
                      <span className="text-slate-500 text-[11px]">Basse</span>
                    ) : (
                      <span className="text-blue-400 text-[11px] font-medium">Normale</span>
                    )}
                  </td>

                  <td className="py-3 px-4 text-slate-400">
                    {task.company ? (
                      <span className="inline-flex items-center gap-1 font-medium text-slate-300">
                        <FiBriefcase className="text-slate-500" />
                        <span>{task.company}</span>
                      </span>
                    ) : (
                      <span className="text-slate-600">—</span>
                    )}
                  </td>

                  <td className="py-3 px-4 text-slate-400 whitespace-nowrap">
                    {task.due_date ? (
                      <span className="inline-flex items-center gap-1">
                        <FiCalendar />
                        <span>{new Date(task.due_date).toLocaleDateString("fr-FR")}</span>
                      </span>
                    ) : (
                      <span className="text-slate-600">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
