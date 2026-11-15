"use client";

import { useState, useEffect } from "react";
import { authApi } from "@/lib/api";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { FiUser, FiTarget, FiBriefcase } from "react-icons/fi";
import CandidateProfileSection from "@/components/profile/CandidateProfileSection";
import TargetingPreferencesSection from "@/components/profile/TargetingPreferencesSection";
import AccountSecurityTab, { type ProfileUser } from "@/components/profile/AccountSecurityTab";

function ProfileContent() {
  const [user, setUser] = useState<ProfileUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"targeting" | "profile" | "account">("targeting");

  useEffect(() => {
    const fetchUserProfile = async () => {
      setLoading(true);
      try {
        const userData = await authApi.getCurrentUser();
        if (userData) setUser(userData);
      } catch (error) {
        console.error("Erreur lors de la récupération du profil utilisateur", error);
      } finally {
        setLoading(false);
      }
    };
    fetchUserProfile();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-blue-night">
        <div className="animate-pulse text-blue-400 text-xl">Chargement...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-blue-night p-6">
      <div className="max-w-4xl mx-auto">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2.5">
              <span>Mon Profil</span>
              {user?.username && (
                <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-blue-900/40 text-blue-300 border border-blue-700/40">
                  @{user.username}
                </span>
              )}
            </h1>
            <p className="text-sm text-gray-400 mt-1">
              Gérez votre ciblage de recherche, les sources de votre profil candidat et les
              paramètres de votre compte.
            </p>
          </div>
        </div>

        <div className="flex border-b border-gray-700/70 mb-8 overflow-x-auto gap-2">
          <button
            type="button"
            onClick={() => setActiveTab("targeting")}
            className={`flex items-center gap-2 py-3 px-5 text-sm font-semibold rounded-t-xl transition-all border-b-2 whitespace-nowrap ${
              activeTab === "targeting"
                ? "border-blue-500 text-blue-400 bg-blue-500/10"
                : "border-transparent text-gray-400 hover:text-gray-200 hover:bg-gray-800/40"
            }`}
          >
            <FiTarget className="w-4 h-4" />
            <span>Ciblage &amp; Préférences</span>
            <span className="ml-1 px-1.5 py-0.5 text-[10px] bg-blue-900/60 text-blue-300 rounded border border-blue-700/50">
              Matching IA
            </span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("profile")}
            className={`flex items-center gap-2 py-3 px-5 text-sm font-semibold rounded-t-xl transition-all border-b-2 whitespace-nowrap ${
              activeTab === "profile"
                ? "border-blue-500 text-blue-400 bg-blue-500/10"
                : "border-transparent text-gray-400 hover:text-gray-200 hover:bg-gray-800/40"
            }`}
          >
            <FiBriefcase className="w-4 h-4" />
            <span>Profil &amp; Expériences (IA)</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("account")}
            className={`flex items-center gap-2 py-3 px-5 text-sm font-semibold rounded-t-xl transition-all border-b-2 whitespace-nowrap ${
              activeTab === "account"
                ? "border-blue-500 text-blue-400 bg-blue-500/10"
                : "border-transparent text-gray-400 hover:text-gray-200 hover:bg-gray-800/40"
            }`}
          >
            <FiUser className="w-4 h-4" />
            <span>Compte &amp; Sécurité</span>
          </button>
        </div>

        {activeTab === "targeting" && (
          <div className="animate-in fade-in duration-200">
            <TargetingPreferencesSection />
          </div>
        )}

        {activeTab === "profile" && (
          <div className="animate-in fade-in duration-200">
            <CandidateProfileSection />
          </div>
        )}

        {activeTab === "account" && (
          <AccountSecurityTab user={user} onUserUpdated={setUser} />
        )}
      </div>
    </div>
  );
}

export default function ProfilePage() {
  return (
    <ProtectedRoute>
      <ProfileContent />
    </ProtectedRoute>
  );
}
