"use client";

import React from "react";
import Link from "next/link";
import {
  FiShield,
  FiUsers,
  FiActivity,
  FiRefreshCw,
  FiLock,
  FiCheckCircle,
  FiAlertTriangle,
  FiArrowLeft,
} from "react-icons/fi";
import { useAdminDashboard } from "@/hooks/useAdminDashboard";
import { AdminCostsTab } from "@/components/admin/AdminCostsTab";
import { AdminUsersTab } from "@/components/admin/AdminUsersTab";
import { AdminGdprModal } from "@/components/admin/AdminGdprModal";

const PERIOD_OPTIONS = [
  { id: "24h", label: "24h" },
  { id: "7d", label: "7j" },
  { id: "30d", label: "30j" },
  { id: "all", label: "Tout" },
] as const;

export default function AdminDashboardPage() {
  const ad = useAdminDashboard();

  if (ad.isAuthLoading) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center text-white">
        <FiRefreshCw className="w-8 h-8 text-blue-500 animate-spin mb-4" />
        <p className="text-slate-400 font-medium">Vérification des droits d&apos;administration...</p>
      </div>
    );
  }

  if (ad.isForbidden || !ad.currentUser) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-slate-900 border border-rose-500/30 rounded-2xl p-8 text-center shadow-2xl backdrop-blur">
          <div className="w-16 h-16 bg-rose-500/10 text-rose-400 rounded-full flex items-center justify-center mx-auto mb-5 border border-rose-500/20">
            <FiLock className="w-8 h-8" />
          </div>
          <h2 className="text-2xl font-bold text-white mb-2">Accès Non Autorisé</h2>
          <p className="text-slate-400 text-sm mb-6 leading-relaxed">
            Cet espace est strictement réservé aux comptes disposant du rôle administrateur.
          </p>
          <Link
            href="/applications"
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-sm font-semibold transition-all shadow-lg shadow-blue-500/20"
          >
            <FiArrowLeft className="w-4 h-4" />
            Retour à l&apos;application
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 pb-20">
      {ad.successToast && (
        <div className="fixed bottom-6 right-6 z-50 bg-emerald-500/90 text-white px-5 py-3 rounded-xl shadow-xl flex items-center gap-2.5 backdrop-blur border border-emerald-400/40 animate-slide-up">
          <FiCheckCircle className="w-5 h-5 shrink-0" />
          <span className="text-sm font-medium">{ad.successToast}</span>
        </div>
      )}

      {/* Admin Header */}
      <div className="border-b border-slate-800 bg-slate-900/60 backdrop-blur sticky top-0 z-40">
        <div className="container mx-auto px-4 py-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-gradient-to-tr from-amber-500 to-indigo-600 flex items-center justify-center text-white shadow-lg shadow-amber-500/10">
              <FiShield className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold text-white tracking-tight">Espace Administration</h1>
                <span className="px-2 py-0.5 text-[11px] font-bold rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 uppercase tracking-wider">
                  Admin Master
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Suivi analytique des coûts LLM, volume d&apos;appels et gestion conforme RGPD
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-1 flex items-center shadow-inner">
              {PERIOD_OPTIONS.map((p) => (
                <button
                  key={p.id}
                  onClick={() => ad.setPeriod(p.id)}
                  className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                    ad.period === p.id ? "bg-blue-600 text-white shadow-sm" : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>

            <button
              onClick={() => ad.loadDashboardData()}
              disabled={ad.isLoadingData}
              className="p-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 hover:text-white transition-all shadow-sm"
              title="Rafraîchir les données"
            >
              <FiRefreshCw className={`w-4 h-4 ${ad.isLoadingData ? "animate-spin text-blue-400" : ""}`} />
            </button>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="container mx-auto px-4 flex gap-6 pt-1">
          <button
            onClick={() => ad.setActiveTab("costs")}
            className={`pb-3 text-sm font-semibold border-b-2 flex items-center gap-2 transition-colors ${
              ad.activeTab === "costs" ? "border-blue-500 text-blue-400" : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <FiActivity className="w-4 h-4" />
            Coûts & Usage API
          </button>
          <button
            onClick={() => ad.setActiveTab("users")}
            className={`pb-3 text-sm font-semibold border-b-2 flex items-center gap-2 transition-colors ${
              ad.activeTab === "users" ? "border-blue-500 text-blue-400" : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <FiUsers className="w-4 h-4" />
            Gestion Utilisateurs & RGPD
            <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] bg-slate-800 text-slate-300">
              {ad.usersList.length}
            </span>
          </button>
        </div>
      </div>

      <div className="container mx-auto px-4 pt-8">
        {ad.errorMsg && (
          <div className="mb-6 bg-rose-500/10 border border-rose-500/30 rounded-2xl p-4 text-rose-300 flex items-center gap-3">
            <FiAlertTriangle className="w-5 h-5 shrink-0" />
            <span className="text-sm">{ad.errorMsg}</span>
          </div>
        )}

        {ad.activeTab === "costs" && (
          <AdminCostsTab costSummary={ad.costSummary} period={ad.period} />
        )}

        {ad.activeTab === "users" && (
          <AdminUsersTab
            currentUser={ad.currentUser}
            filteredUsers={ad.filteredUsers}
            searchQuery={ad.searchQuery}
            tierFilter={ad.tierFilter}
            updatingUserId={ad.updatingUserId}
            onSearchChange={ad.setSearchQuery}
            onTierFilterChange={ad.setTierFilter}
            onUpdateTier={ad.handleUpdateTier}
            onToggleStatus={ad.handleToggleStatus}
            onRequestGdprDelete={(u) => {
              ad.setGdprDeleteUser(u);
              ad.setGdprConfirmInput("");
            }}
          />
        )}
      </div>

      <AdminGdprModal
        user={ad.gdprDeleteUser}
        confirmInput={ad.gdprConfirmInput}
        isDeleting={ad.isDeletingGdpr}
        onConfirmInputChange={ad.setGdprConfirmInput}
        onCancel={() => {
          ad.setGdprDeleteUser(null);
          ad.setGdprConfirmInput("");
        }}
        onExecute={ad.handleExecuteGdprErasure}
      />
    </div>
  );
}
