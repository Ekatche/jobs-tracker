"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useNotification } from "@/contexts/NotificationContext";
import { applicationApi } from "@/lib/api";
import EditApplicationModal from "@/components/dashboard/EditApplicationModal";
import ApplicationsTable from "@/components/dashboard/ApplicationsTable";
import StatusChart from "@/components/dashboard/StatusChart";
import PositionChart from "@/components/dashboard/PositionChart";
import TabNavigation from "@/components/dashboard/TabNavigation";
import { Application } from "@/types/application";

export default function DashboardPage() {
  // États principaux
  const [applications, setApplications] = useState<Application[]>([]);
  const [activeApplications, setActiveApplications] = useState<Application[]>(
    [],
  );
  const [archivedApplications, setArchivedApplications] = useState<
    Application[]
  >([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // notifications et cache descriptions
  const { addNotification } = useNotification();
  const prevDescriptions = useRef<Record<string, string | undefined>>({});
  const isInitialLoad = useRef(true);

  // fetchData avec flag pour désactiver le spinner en mode “silent”
  const fetchData = useCallback(
    async (showLoading = true) => {
      if (showLoading) setLoading(true);
      try {
        const apiData = await applicationApi.getAll();
        if (!Array.isArray(apiData))
          throw new Error("Format de données invalide");
        const apps = apiData.map((item) =>
          normalizeApiData(item as Partial<Application> & { id?: string }),
        );

        // notifications quand la description apparaît
        if (!isInitialLoad.current) {
          apps.forEach((app) => {
            const oldDesc = prevDescriptions.current[app._id];
            if ((!oldDesc || oldDesc === "") && app.description) {
              addNotification(
                "info",
                `Description générée pour "${app.position}" chez "${app.company}"`,
              );
            }
          });
        }
        apps.forEach((app) => {
          prevDescriptions.current[app._id] = app.description;
        });
        isInitialLoad.current = false;

        // mise à jour des états
        setApplications(apps);
        setActiveApplications(apps.filter((a) => !a.archived));
        setArchivedApplications(apps.filter((a) => a.archived));
        setError(null);
      } catch (err: unknown) {
        console.error(err);
        setError("Impossible de charger les candidatures");
      } finally {
        if (showLoading) setLoading(false);
      }
    },
    [addNotification],
  );

  // chargement initial
  useEffect(() => {
    fetchData().finally(() => {
      isInitialLoad.current = false;
    });
  }, [fetchData]);

  // polling SILENCIEUX toutes les 10s tant qu’il manque des descriptions
  useEffect(() => {
    if (isInitialLoad.current) return;
    if (!applications.some((app) => !app.description)) return;
    const id = setInterval(() => fetchData(false), 10_000);
    return () => clearInterval(id);
  }, [applications, fetchData]);

  // État pour gérer l'onglet actif
  const [activeTab, setActiveTab] = useState<"active" | "archived">("active");

  // État pour la recherche et la pagination
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [itemsPerPage] = useState<number>(5);

  // États pour gérer la modal
  const [isEditModalOpen, setIsEditModalOpen] = useState<boolean>(false);
  const [applicationToEdit, setApplicationToEdit] =
    useState<Application | null>(null);

  // Fonction pour normaliser les données de l'API
  const normalizeApiData = (
    apiData: Partial<Application> & { id?: string },
  ): Application => ({
    _id: apiData._id || apiData.id || "",
    user_id: apiData.user_id || "",
    company: apiData.company || "",
    position: apiData.position || "",
    location: apiData.location || "",
    url: apiData.url,
    application_date: apiData.application_date || "",
    status: apiData.status || "",
    description: apiData.description,
    notes: Array.isArray(apiData.notes) ? apiData.notes : [],
    created_at: apiData.created_at || "",
    updated_at: apiData.updated_at,
    archived: apiData.archived || false,
  });

  // La fonction fetchData est déjà définie plus haut dans le code

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    const handleApplicationCreated = () => {
      fetchData();
    };

    window.addEventListener("application-created", handleApplicationCreated);
    return () => {
      window.removeEventListener(
        "application-created",
        handleApplicationCreated,
      );
    };
  }, [fetchData]);

  // Fonction pour basculer l'état archivé d'une candidature
  const handleToggleArchive = async (application: Application) => {
    try {
      await applicationApi.update(application._id, {
        ...application,
        archived: !application.archived,
      });
      await fetchData();
    } catch (error) {
      console.error("Erreur lors de l'archivage/désarchivage:", error);
    }
  };

  // Fonction pour ouvrir le modal d'édition
  const handleRowClick = (application: Application) => {
    setApplicationToEdit(application);
    setIsEditModalOpen(true);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-blue-night text-white">
        <p className="text-xl">Chargement des données...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-blue-night text-white">
        <p className="text-xl text-red-500">Erreur: {error}</p>
      </div>
    );
  }

  // Données à afficher en fonction de l'onglet actif
  const currentApplications =
    activeTab === "active" ? activeApplications : archivedApplications;

  return (
    <div className="min-h-screen bg-blue-night text-white p-6">
      <div className="max-w-7xl mx-auto">
        <div className="grid grid-cols-1 gap-6 mb-6">
          {/* Tableau des candidatures avec onglets */}
          <div className="bg-blue-night-lighter rounded-lg shadow-lg overflow-hidden">
            <div className="p-4 border-b border-gray-700 flex justify-between items-center">
              <div className="flex items-center space-x-2">
                <svg
                  className="w-6 h-6 text-gray-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
                  ></path>
                </svg>
                <h2 className="text-xl font-semibold">Mes candidatures</h2>
              </div>

              {/* Barre de recherche */}
              <div className="relative">
                <input
                  type="text"
                  placeholder="Rechercher..."
                  value={searchTerm}
                  onChange={(e) => {
                    setSearchTerm(e.target.value);
                    setCurrentPage(1);
                  }}
                  className="px-3 py-2 pl-10 bg-blue-night border border-gray-700 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-white"
                />
                <svg
                  className="w-5 h-5 text-gray-400 absolute left-3 top-1/2 transform -translate-y-1/2"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                  ></path>
                </svg>
              </div>
            </div>

            {/* Navigation par onglets */}
            <TabNavigation
              activeTab={activeTab}
              setActiveTab={setActiveTab}
              setCurrentPage={setCurrentPage}
              activeCount={activeApplications.length}
              archivedCount={archivedApplications.length}
            />

            {/* Tableau des candidatures */}
            <ApplicationsTable
              applications={currentApplications}
              searchTerm={searchTerm}
              currentPage={currentPage}
              itemsPerPage={itemsPerPage}
              setCurrentPage={setCurrentPage}
              onRowClick={handleRowClick}
              onToggleArchive={handleToggleArchive}
              activeTab={activeTab}
            />
          </div>
        </div>

        {/* Graphiques (uniquement pour les candidatures actives) */}
        {activeTab === "active" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <StatusChart applications={activeApplications} />
            <PositionChart applications={activeApplications} />
          </div>
        )}
      </div>

      {/* Modal d'édition */}
      <EditApplicationModal
        isOpen={isEditModalOpen}
        onClose={() => setIsEditModalOpen(false)}
        onSuccess={fetchData}
        application={applicationToEdit}
      />
    </div>
  );
}
