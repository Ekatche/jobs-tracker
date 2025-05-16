import React from "react";
import { Application } from "@/types/application";
import { formatDate, getDaysSinceApplication } from "./utils/formatters";
import { getStatusColor, getLocationColor } from "./utils/helpers";
import Pagination from "./Pagination";

interface ApplicationsTableProps {
  applications: Application[];
  searchTerm: string;
  currentPage: number;
  itemsPerPage: number;
  setCurrentPage: (page: number) => void;
  onRowClick: (application: Application) => void;
  onToggleArchive: (application: Application) => void;
  activeTab: "active" | "archived";
}

export default function ApplicationsTable({
  applications,
  searchTerm,
  currentPage,
  itemsPerPage,
  setCurrentPage,
  onRowClick,
  onToggleArchive,
  activeTab,
}: ApplicationsTableProps) {
  // Filtrer les applications selon le terme de recherche
  const filteredApplications = searchTerm
    ? applications.filter((app) => {
        const searchLower = searchTerm.toLowerCase();
        return (
          app.company.toLowerCase().includes(searchLower) ||
          app.position.toLowerCase().includes(searchLower) ||
          app.status.toLowerCase().includes(searchLower) ||
          (app.location && app.location.toLowerCase().includes(searchLower))
        );
      })
    : applications;

  // Pagination
  const totalPages = Math.ceil(filteredApplications.length / itemsPerPage);
  const indexOfLastItem = currentPage * itemsPerPage;
  const indexOfFirstItem = indexOfLastItem - itemsPerPage;
  const currentItems = filteredApplications.slice(
    indexOfFirstItem,
    indexOfLastItem,
  );

  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="text-left bg-blue-night-lighter">
              <th className="p-4 font-medium text-gray-400">Entreprise</th>
              <th className="p-4 font-medium text-gray-400">Poste</th>
              <th className="p-4 font-medium text-gray-400">Statut</th>
              <th className="p-4 font-medium text-gray-400">Localisation</th>
              <th className="p-4 font-medium text-gray-400">URL</th>
              <th className="p-4 font-medium text-gray-400">
                Date de candidature
              </th>
              <th className="p-4 font-medium text-gray-400">Actions</th>
            </tr>
          </thead>
          <tbody>
            {currentItems.map((app) => (
              <tr
                key={app._id}
                className="border-t border-gray-700 hover:bg-blue-night-light cursor-pointer"
              >
                <td className="p-4" onClick={() => onRowClick(app)}>
                  <div className="flex items-center">
                    <div className="w-8 h-8 flex items-center justify-center rounded-full bg-blue-900/40 text-white font-medium mr-2">
                      {app.company.charAt(0)}
                    </div>
                    {app.company}
                  </div>
                </td>
                <td className="p-4" onClick={() => onRowClick(app)}>
                  {app.position}
                </td>
                <td className="p-4" onClick={() => onRowClick(app)}>
                  <div className="flex items-center">
                    <div
                      className={`w-3 h-3 rounded-full mr-2 ${getStatusColor(app.status)}`}
                    ></div>
                    {app.status}
                  </div>
                </td>
                <td className="p-4" onClick={() => onRowClick(app)}>
                  {app.location && app.location.trim() !== "" ? (
                    <span
                      className={`px-3 py-1 text-sm rounded-full text-white ${getLocationColor(app.location)}`}
                    >
                      {app.location}
                    </span>
                  ) : (
                    <span className="text-gray-500">Non spécifiée</span>
                  )}
                </td>
                <td className="p-4" onClick={() => onRowClick(app)}>
                  {app.url && (
                    <a
                      href={app.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-400 hover:underline"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <svg
                        className="w-5 h-5 inline-block"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                        xmlns="http://www.w3.org/2000/svg"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth="2"
                          d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
                        ></path>
                      </svg>
                    </a>
                  )}
                </td>
                <td className="p-4" onClick={() => onRowClick(app)}>
                  <div>
                    {formatDate(app.application_date)}
                    <div className="text-xs text-gray-400">
                      {getDaysSinceApplication(app.application_date)}
                    </div>
                  </div>
                </td>
                <td className="p-4">
                  <button
                    onClick={() => onToggleArchive(app)}
                    className={`px-3 py-1 rounded-md text-xs ${
                      app.archived
                        ? "bg-blue-600 hover:bg-blue-700 text-white"
                        : "bg-gray-600 hover:bg-gray-700 text-white"
                    }`}
                  >
                    {app.archived ? "Désarchiver" : "Archiver"}
                  </button>
                </td>
              </tr>
            ))}
            {currentItems.length === 0 && (
              <tr className="border-t border-gray-700">
                <td colSpan={7} className="p-4 text-center text-gray-400">
                  {activeTab === "active"
                    ? "Aucune candidature active trouvée"
                    : "Aucune candidature archivée trouvée"}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="p-4 border-t border-gray-700 flex justify-between items-center">
        <span className="text-sm text-gray-400">
          Affichage de{" "}
          {filteredApplications.length > 0
            ? Math.min(
                (currentPage - 1) * itemsPerPage + 1,
                filteredApplications.length,
              )
            : 0}{" "}
          à {Math.min(currentPage * itemsPerPage, filteredApplications.length)}{" "}
          sur {filteredApplications.length} candidatures
          {applications.length !== filteredApplications.length && (
            <span className="ml-1">
              (filtrées sur {applications.length} au total)
            </span>
          )}
        </span>
        <Pagination
          currentPage={currentPage}
          totalPages={totalPages}
          onPageChange={setCurrentPage}
        />
      </div>
    </>
  );
}
