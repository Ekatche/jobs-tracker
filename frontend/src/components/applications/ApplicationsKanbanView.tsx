"use client";

import React from "react";
import { Application, calculateDays } from "@/types/application";
import { KanbanColumnData } from "@/hooks/useApplicationsPage";
import {
  FiAlertCircle,
  FiArrowRight,
  FiMapPin,
  FiLink,
  FiClock,
  FiMail,
} from "react-icons/fi";

const QUICK_TRANSITIONS: Record<string, { nextStatus: string; label: string }> = {
  "En étude": { nextStatus: "Candidature envoyée", label: "Envoyer" },
  "Candidature envoyée": { nextStatus: "Première sélection", label: "Sélection" },
  "Première sélection": { nextStatus: "Entretien", label: "Entretien" },
  Entretien: { nextStatus: "Test technique", label: "Test tech" },
  "Test technique": { nextStatus: "Offre reçue", label: "Offre" },
  Négociation: { nextStatus: "Offre reçue", label: "Offre" },
  "Offre reçue": { nextStatus: "Offre acceptée", label: "Accepter" },
};

interface ApplicationsKanbanViewProps {
  columns: KanbanColumnData[];
  onCardClick: (application: Application) => void;
  onTransitionStatus: (e: React.MouseEvent, appId: string, newStatus: string) => void;
}

/**
 * Horizontal Kanban columns view with follow-up badges and one-click stage transitions.
 */
export function ApplicationsKanbanView({
  columns,
  onCardClick,
  onTransitionStatus,
}: ApplicationsKanbanViewProps) {
  return (
    <div className="flex-1 min-h-0 flex flex-row gap-4 overflow-x-auto overflow-y-hidden pb-2 custom-scrollbar">
      {columns.map((col) => (
        <div
          key={col.id}
          className="flex-1 min-w-[280px] max-w-[340px] flex flex-col h-full min-h-0 bg-gray-900/50 rounded-xl border border-gray-800/80 shadow-sm"
        >
          <div className="p-3 border-b border-gray-800 flex items-center justify-between flex-shrink-0 bg-gray-900/60 rounded-t-xl">
            <div className="flex items-center gap-2">
              <span className={`w-2.5 h-2.5 rounded-full ${col.dotColor}`} />
              <span className="text-xs font-bold text-gray-200">{col.title}</span>
            </div>
            <span className={`text-xs px-2 py-0.5 rounded-full font-semibold border ${col.badgeBg}`}>
              {col.apps.length}
            </span>
          </div>

          <div className="flex-1 min-h-0 overflow-y-auto p-2.5 space-y-2.5 custom-scrollbar">
            {col.apps.length === 0 ? (
              <div className="h-32 flex items-center justify-center text-xs text-gray-500 italic text-center px-4">
                Aucune candidature dans cette étape
              </div>
            ) : (
              col.apps.map((app) => {
                const days = app.days_since_application ?? calculateDays(app.application_date);
                const isRelanceDue =
                  app.follow_up_alert === "relance_due" ||
                  (app.status === "Candidature envoyée" && days >= 7);
                const isRemerciementDue =
                  app.follow_up_alert === "remerciement_due" ||
                  (app.status === "Entretien" && days >= 1);
                const quickTransition = QUICK_TRANSITIONS[app.status];

                return (
                  <div
                    key={app._id}
                    onClick={() => onCardClick(app)}
                    className="bg-blue-night-lighter/90 hover:bg-blue-night-lighter border border-gray-700/80 hover:border-blue-500/60 rounded-xl p-3 shadow-sm hover:shadow-md transition-all cursor-pointer group"
                  >
                    <div className="flex items-start justify-between gap-2 mb-1.5">
                      <h3 className="font-semibold text-xs text-white group-hover:text-blue-200 transition-colors line-clamp-2 leading-tight">
                        {app.position}
                      </h3>
                      <span className="flex-shrink-0 text-[10px] text-gray-400 bg-gray-800/80 px-1.5 py-0.5 rounded border border-gray-700 flex items-center gap-1">
                        <FiClock className="text-[9px]" />
                        {days}j
                      </span>
                    </div>

                    <div className="text-[11px] text-gray-300 font-medium truncate mb-1">
                      {app.company}
                    </div>

                    {app.location && (
                      <div className="text-[10px] text-gray-400 flex items-center gap-1 mb-2 truncate">
                        <FiMapPin className="text-[10px] shrink-0" />
                        <span>{app.location}</span>
                      </div>
                    )}

                    {isRelanceDue && (
                      <div className="mb-2 px-2 py-1 rounded text-[10px] font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/40 flex items-center gap-1.5">
                        <FiAlertCircle className="text-xs shrink-0 text-amber-400" />
                        <span>Relance J+7 due ({days}j)</span>
                      </div>
                    )}

                    {isRemerciementDue && (
                      <div className="mb-2 px-2 py-1 rounded text-[10px] font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 flex items-center gap-1.5">
                        <FiMail className="text-xs shrink-0 text-indigo-400" />
                        <span>Remerciement J+1 à faire</span>
                      </div>
                    )}

                    {app.offer_id && (
                      <div className="mb-2 flex items-center gap-1 text-[10px] text-blue-300 bg-blue-900/30 px-2 py-0.5 rounded border border-blue-500/30 w-fit">
                        <FiLink className="text-[9px] shrink-0" />
                        <span className="truncate">Offre liée</span>
                      </div>
                    )}

                    <div className="flex items-center gap-1.5 pt-2 border-t border-gray-800/80 mt-1">
                      {quickTransition && (
                        <button
                          onClick={(e) =>
                            onTransitionStatus(e, app._id, quickTransition.nextStatus)
                          }
                          className="flex-1 py-1 px-2 rounded bg-blue-600 hover:bg-blue-500 text-white text-[11px] font-medium flex items-center justify-center gap-1 transition-colors"
                          title={`Passer à l'étape : ${quickTransition.nextStatus}`}
                        >
                          <span>{quickTransition.label}</span>
                          <FiArrowRight className="text-[10px]" />
                        </button>
                      )}

                      {app.status !== "Refusée" && app.status !== "Retirée" && (
                        <button
                          onClick={(e) => onTransitionStatus(e, app._id, "Refusée")}
                          className="py-1 px-2 rounded bg-rose-950/40 hover:bg-rose-900/60 text-rose-300 text-[11px] font-medium border border-rose-800/40 transition-colors"
                          title="Déclarer la candidature refusée"
                        >
                          Refus
                        </button>
                      )}

                      {(app.status === "Refusée" || app.status === "Retirée") && (
                        <button
                          onClick={(e) =>
                            onTransitionStatus(e, app._id, "Candidature envoyée")
                          }
                          className="flex-1 py-1 px-2 rounded bg-gray-800 hover:bg-gray-700 text-blue-300 text-[11px] font-medium border border-gray-700 transition-colors"
                          title="Réactiver la candidature"
                        >
                          Réactiver
                        </button>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
