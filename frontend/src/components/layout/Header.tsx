"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  FiBriefcase,
  FiMenu,
  FiX,
  FiUser,
  FiLogOut,
  FiPlusCircle,
  FiUserPlus,
} from "react-icons/fi";
import { useRouter } from "next/navigation";
import { logout, getToken } from "@/lib/auth";
import { authApi } from "@/lib/api";
import type { User } from "@/lib/api";
import NewApplicationModal, {
  PrefilledData,
} from "@/components/dashboard/NewApplicationModal";

// Définir le style de fond une seule fois
const headerBackground = {
  background: "#1a2a45",
  borderBottom: "1px solid rgba(255, 255, 255, 0.1)",
};

export default function Header() {
  const [isOpen, setIsOpen] = useState(false);
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [isNewApplicationModalOpen, setIsNewApplicationModalOpen] =
    useState(false);
  const [prefilledData, setPrefilledData] = useState<PrefilledData | undefined>(
    undefined,
  );
  const pathname = usePathname();
  const router = useRouter();

  // Vérifier l'état d'authentification et récupérer les infos utilisateur
  useEffect(() => {
    const checkAuth = async () => {
      setLoading(true);
      const token = getToken();
      console.log("Token in Header:", token); // Ajoutez cette ligne

      if (token) {
        try {
          const userData = await authApi.getCurrentUser();
          console.log("User data:", userData); // Ajoutez cette ligne
          setUser(userData);
          setIsLoggedIn(true);
        } catch (error) {
          console.error(
            "Erreur lors de la récupération des informations utilisateur",
            error,
          );
          setIsLoggedIn(false);
          setUser(null);
        }
      } else {
        setIsLoggedIn(false);
        setUser(null);
      }
      setLoading(false);
    };

    checkAuth();
  }, [pathname]);

  const handleLogout = async () => {
    await logout();
    setUser(null);
    setIsLoggedIn(false);
    closeMenu();
    router.push("/auth/login");
  };

  const closeMenu = () => {
    setIsOpen(false);
    setIsUserMenuOpen(false);
  };

  // Écouter l'événement pour ouvrir la modal avec des données pré-remplies
  useEffect(() => {
    const handleOpenModalWithData = (event: CustomEvent<PrefilledData>) => {
      setPrefilledData(event.detail);
      setIsNewApplicationModalOpen(true);
    };

    window.addEventListener(
      "open-application-modal",
      handleOpenModalWithData as EventListener,
    );

    return () => {
      window.removeEventListener(
        "open-application-modal",
        handleOpenModalWithData as EventListener,
      );
    };
  }, []);

  // Modifiez la fonction handleApplicationSuccess
  const handleApplicationSuccess = async () => {
    // Fermer la modal après un délai pour montrer le message de succès
    setTimeout(() => {
      setIsNewApplicationModalOpen(false);
      setPrefilledData(undefined); // Réinitialiser les données pré-remplies

      // Effectuer un rafraîchissement complet de la page
      window.location.reload();
    }, 1500);

    // Nous gardons aussi l'événement pour la compatibilité avec le code existant
    if (pathname.includes("/applications") || pathname.includes("/dashboard")) {
      window.dispatchEvent(new Event("application-created"));
    }
  };

  const handleCloseModal = () => {
    setIsNewApplicationModalOpen(false);
    setPrefilledData(undefined); // Réinitialiser les données pré-remplies
  };

  // Fonction pour déterminer si le lien est actif
  const isActive = (path: string) => {
    if (path === "/" && pathname !== "/") return false;
    return pathname?.startsWith(path);
  };

  return (
    <header className="sticky top-0 z-50 shadow-md" style={headerBackground}>
      <div className="container mx-auto px-4 py-3">
        <div className="flex items-center justify-between">
          {/* Logo et titre */}
          <Link href="/" className="flex items-center gap-2 text-white">
            <FiBriefcase className="text-2xl" />
            <span className="font-bold text-xl hidden sm:block">
              Job Tracker
            </span>
          </Link>

          {/* Navigation sur grand écran */}
          <nav className="hidden md:flex items-center space-x-8">
            {isLoggedIn ? (
              <>
                <Link
                  href="/dashboard"
                  className={`text-sm font-medium transition-colors ${
                    isActive("/dashboard")
                      ? "text-white border-b-2 border-blue-400"
                      : "text-gray-300 hover:text-white"
                  }`}
                >
                  Tableau de bord
                </Link>
                <Link
                  href="/applications"
                  className={`text-sm font-medium transition-colors ${
                    isActive("/applications")
                      ? "text-white border-b-2 border-blue-400"
                      : "text-gray-300 hover:text-white"
                  }`}
                >
                  Mes candidatures
                </Link>
                <Link
                  href="/tasks"
                  className={`text-sm font-medium transition-colors ${
                    isActive("/tasks")
                      ? "text-white border-b-2 border-blue-400"
                      : "text-gray-300 hover:text-white"
                  }`}
                >
                  Mes demarches
                </Link>
                <Link
                  href="/offers"
                  className={`text-sm font-medium transition-colors ${
                    isActive("/offers")
                      ? "text-white border-b-2 border-blue-400"
                      : "text-gray-300 hover:text-white"
                  }`}
                >
                  Offres d'emploi
                </Link>
              </>
            ) : (
              <></>
            )}
          </nav>

          {/* Actions */}
          <div className="flex items-center gap-4">
            {!loading && isLoggedIn ? (
              <>
                {/* Bouton d'ajout de candidature (visible sur desktop) */}
                <button
                  onClick={() => setIsNewApplicationModalOpen(true)}
                  className="hidden md:flex items-center gap-1 text-white bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-md text-sm font-medium transition-colors"
                >
                  <FiPlusCircle className="text-lg" />
                  <span>Nouvelle candidature</span>
                </button>

                {/* Menu utilisateur */}
                <div className="relative">
                  <button
                    onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
                    className="flex items-center gap-2 px-3 py-2 rounded-md bg-blue-900/30 hover:bg-blue-800/50 text-white transition-colors"
                  >
                    <FiUser className="text-lg" />
                    <span className="hidden sm:inline">
                      {user?.username || "Utilisateur"}
                    </span>
                  </button>

                  {/* Dropdown menu utilisateur */}
                  {isUserMenuOpen && (
                    <div className="absolute right-0 mt-2 w-48 bg-blue-night-lighter rounded-md shadow-lg z-10 py-1 border border-gray-700">
                      <div className="px-4 py-2 text-sm text-gray-300 border-b border-gray-700">
                        <div className="font-medium">{user?.username}</div>
                        <div className="text-xs text-gray-400 truncate">
                          {user?.email}
                        </div>
                      </div>
                      <Link
                        href="/profile"
                        className="block px-4 py-2 text-sm text-gray-200 hover:bg-blue-800/40"
                        onClick={closeMenu}
                      >
                        Profil
                      </Link>
                      <button
                        onClick={handleLogout}
                        className="w-full text-left px-4 py-2 text-sm text-red-400 hover:bg-blue-800/40 flex items-center gap-2"
                      >
                        <FiLogOut className="text-lg" />
                        <span>Déconnexion</span>
                      </button>
                    </div>
                  )}
                </div>
              </>
            ) : !loading ? (
              <div className="hidden md:flex items-center gap-3">
                {/* Connexion à droite */}
                <Link
                  href="/auth/login"
                  className="text-sm font-medium text-gray-300 hover:text-white transition-colors px-3 py-2"
                >
                  Connexion
                </Link>
                {/* Bouton d'inscription bien visible */}
                <Link
                  href="/auth/register"
                  className="flex items-center gap-1 text-white bg-blue-800 hover:bg-blue-700 px-4 py-2 rounded-md text-sm font-medium transition-colors"
                >
                  <FiUserPlus className="text-lg" />
                  <span>Inscription</span>
                </Link>
              </div>
            ) : (
              // État de chargement (peut être ajouté un loader ici)
              <div className="w-10 h-10 flex items-center justify-center">
                <div className="animate-pulse bg-blue-800/40 w-8 h-8 rounded-full"></div>
              </div>
            )}

            {/* Menu hamburger pour mobile */}
            <button
              className="md:hidden flex items-center text-white"
              onClick={() => setIsOpen(!isOpen)}
            >
              {isOpen ? (
                <FiX className="text-2xl" />
              ) : (
                <FiMenu className="text-2xl" />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Menu mobile */}
      {isOpen && (
        <div className="md:hidden bg-blue-night-lighter border-t border-gray-700 shadow-lg">
          <div className="px-4 py-3 space-y-3">
            {!loading && isLoggedIn ? (
              <>
                {user && (
                  <div className="py-2 mb-2 border-b border-gray-700">
                    <div className="text-white font-medium">
                      {user.username}
                    </div>
                    <div className="text-sm text-gray-400 truncate">
                      {user.email}
                    </div>
                  </div>
                )}
                <Link
                  href="/dashboard"
                  className="block py-2 text-base font-medium text-gray-200 hover:text-white"
                  onClick={closeMenu}
                >
                  Tableau de bord
                </Link>
                <Link
                  href="/applications"
                  className="block py-2 text-base font-medium text-gray-200 hover:text-white"
                  onClick={closeMenu}
                >
                  Mes candidatures
                </Link>
                <button
                  onClick={() => {
                    setIsNewApplicationModalOpen(true);
                    closeMenu();
                  }}
                  className="flex items-center gap-2 w-full py-2 text-base font-medium text-gray-200 hover:text-white"
                >
                  <FiPlusCircle />
                  Nouvelle candidature
                </button>
                <Link
                  href="/profile"
                  className="block py-2 text-base font-medium text-gray-200 hover:text-white"
                  onClick={closeMenu}
                >
                  Profil
                </Link>
                <button
                  onClick={handleLogout}
                  className="flex items-center gap-2 w-full py-2 text-base font-medium text-red-400"
                >
                  <FiLogOut />
                  Déconnexion
                </button>
              </>
            ) : !loading ? (
              <>
                {/* Mise en avant des options d'authentification */}
                <div className="flex flex-col space-y-2 pt-3 border-t border-gray-700">
                  <Link
                    href="/auth/login"
                    className="block w-full py-2 text-center text-base font-medium text-white border border-blue-700 rounded-md hover:bg-blue-800/40"
                    onClick={closeMenu}
                  >
                    Connexion
                  </Link>
                  <Link
                    href="/auth/register"
                    className="flex items-center justify-center w-full py-2 text-center text-base font-medium text-white bg-blue-600 border border-blue-600 rounded-md hover:bg-blue-700"
                    onClick={closeMenu}
                  >
                    <FiUserPlus className="mr-2" />
                    Inscription
                  </Link>
                </div>
              </>
            ) : (
              <div className="flex justify-center py-4">
                <div className="animate-pulse bg-blue-800/40 w-8 h-8 rounded-full"></div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Modal d'ajout de candidature */}
      <NewApplicationModal
        isOpen={isNewApplicationModalOpen}
        onClose={handleCloseModal}
        onSuccess={handleApplicationSuccess}
        prefilledData={prefilledData}
      />
    </header>
  );
}
