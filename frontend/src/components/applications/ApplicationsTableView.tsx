"use client";

import React from "react";
import { Application, getStatusColor, calculateDays } from "@/types/application";

interface ApplicationsTableViewProps {
  applications: Application[];
  onRowClick: (application: Application) => void;
}

/**
 * Filterable tabular view for all job applications with follow-up alert chips.
 */
export function ApplicationsTableView({
  applications,
  onRowClick,
}: ApplicationsTableViewProps) {
  return (
    <div className="flex-1 min-h-0 bg-gray-900/50 rounded-xl border border-gray-800 overflow-hidden flex flex-col">
      <div className="overflow-x-auto flex-1 custom-scrollbar">
        <table className="w-full text-left text-xs">
          <thead className="bg-gray-900/80 text-gray-400 font-semibold border-b border-gray-800 sticky top-0">
            <tr>
              <th className="py-3 px-4">Poste & Entreprise</th>
              <th className="py-3 px-4">Localisation</th>
              <th className="py-3 px-4">Date de dépôt</th>
              <th className="py-3 px-4">Statut</th>
              <th className="py-3 px-4">Alertes / Suivi</th>
              <th className="py-3 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {applications.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-12 text-center text-gray-500 italic">
                  Aucune candidature trouvée.
                </td>
              </tr>
            ) : (
              applications.map((app) => {
                const days = app.days_since_application ?? calculateDays(app.application_date);
                const isRelanceDue =
                  app.follow_up_alert === "relance_due" ||
                  (app.status === "Candidature envoyée" && days >= 7);
                const isRemerciementDue =
                  app.follow_up_alert === "remerciement_due" ||
                  (app.status === "Entretien" && days >= 1);

                return (
                  <tr
                    key={app._id}
                    onClick={() => onRowClick(app)}
                    className="hover:bg-gray-800/40 cursor-pointer transition-colors"
                  >
                    <td className="py-3 px-4">
                      <div className="font-semibold text-white">{app.position}</div>
                      <div className="text-gray-400 text-[11px]">{app.company}</div>
                    </td>
                    <td className="py-3 px-4 text-gray-300">{app.location || "—"}</td>
                    <td className="py-3 px-4 text-gray-300">
                      <div>{app.application_date.substring(0, 10)}</div>
                      <div className="text-[10px] text-gray-500">il y a {days} jours</div>
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`px-2.5 py-1 rounded-full text-[11px] font-semibold text-white ${getStatusColor(
                          app.status
                        )}`}
                      >
                        {app.status}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      {isRelanceDue && (
                        <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                          ⚠️ Relance J+7 due
                        </span>
                      )}
                      {isRemerciementDue && (
                        <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                          💌 Remerciement J+1
                        </span>
                      )}
                      {!isRelanceDue && !isRemerciementDue && (
                        <span className="text-gray-500 text-[11px]">—</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onRowClick(app);
                        }}
                        className="px-2.5 py-1 rounded bg-gray-800 hover:bg-gray-700 text-blue-400 hover:text-blue-300 text-xs font-medium border border-gray-700 transition-colors"
                      >
                        Voir détails
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
