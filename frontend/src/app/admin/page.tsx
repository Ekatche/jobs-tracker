"use client";

import React, { useEffect, useState, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  FiShield,
  FiDollarSign,
  FiCpu,
  FiUsers,
  FiActivity,
  FiRefreshCw,
  FiLock,
  FiCheckCircle,
  FiAlertTriangle,
  FiTrash2,
  FiSearch,
  FiFilter,
  FiInfo,
  FiZap,
  FiFileText,
  FiMail,
  FiAward,
  FiLayers,
  FiChevronRight,
  FiArrowLeft,
  FiCheck,
} from "react-icons/fi";
import { adminApi, authApi, User } from "@/lib/api";
import {
  AdminCostSummary,
  AdminPeriod,
  AdminUserSummary,
  ModelCostItem,
  ActionCostItem,
} from "@/types/admin";

const ACTION_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  interview_prep: FiAward,
  cv_tailoring: FiFileText,
  cover_letter: FiMail,
  evaluation: FiZap,
  cv_parsing: FiLayers,
  offer_summary: FiCpu,
};

export default function AdminDashboardPage() {
  const router = useRouter();

  // Auth & Permissions
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [isAuthLoading, setIsAuthLoading] = useState(true);
  const [isForbidden, setIsForbidden] = useState(false);

  // Dashboard Data
  const [activeTab, setActiveTab] = useState<"costs" | "users">("costs");
  const [period, setPeriod] = useState<AdminPeriod>("30d");
  const [costSummary, setCostSummary] = useState<AdminCostSummary | null>(null);
  const [usersList, setUsersList] = useState<AdminUserSummary[]>([]);
  const [isLoadingData, setIsLoadingData] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successToast, setSuccessToast] = useState<string | null>(null);

  // Users Filters & Actions
  const [searchQuery, setSearchQuery] = useState("");
  const [tierFilter, setTierFilter] = useState<string>("all");
  const [updatingUserId, setUpdatingUserId] = useState<string | null>(null);

  // Modal Droit à l'oubli RGPD
  const [gdprDeleteUser, setGdprDeleteUser] = useState<AdminUserSummary | null>(null);
  const [gdprConfirmInput, setGdprConfirmInput] = useState("");
  const [isDeletingGdpr, setIsDeletingGdpr] = useState(false);

  // 1. Vérification des droits administrateur
  useEffect(() => {
    const verifyAdmin = async () => {
      try {
        setIsAuthLoading(true);
        const user = await authApi.getCurrentUser();
        setCurrentUser(user);
        if (user.role !== "admin") {
          setIsForbidden(true);
        }
      } catch (err) {
        console.error("Erreur vérification auth admin:", err);
        setIsForbidden(true);
      } finally {
        setIsAuthLoading(false);
      }
    };

    verifyAdmin();
  }, []);

  // 2. Chargement des données du tableau de bord
  const loadDashboardData = useCallback(async () => {
    if (isForbidden) return;
    try {
      setIsLoadingData(true);
      setErrorMsg(null);
      const [costs, users] = await Promise.all([
        adminApi.getCosts(period),
        adminApi.getUsers(),
      ]);
      setCostSummary(costs);
      setUsersList(users);
    } catch (err: unknown) {
      console.error("Erreur chargement dashboard admin:", err);
      const msg = err instanceof Error ? err.message : "Erreur de chargement des données.";
      setErrorMsg(msg);
    } finally {
      setIsLoadingData(false);
    }
  }, [period, isForbidden]);

  useEffect(() => {
    if (!isAuthLoading && !isForbidden) {
      loadDashboardData();
    }
  }, [isAuthLoading, isForbidden, loadDashboardData]);

  // Notifications temporaires
  const showToast = (msg: string) => {
    setSuccessToast(msg);
    setTimeout(() => setSuccessToast(null), 4000);
  };

  // 3. Gestion des actions utilisateurs
  const handleUpdateTier = async (userId: string, newTier: "free" | "advanced" | "pro") => {
    try {
      setUpdatingUserId(userId);
      const updated = await adminApi.updateTier(userId, newTier);
      setUsersList((prev) => prev.map((u) => (u.id === userId ? updated : u)));
      showToast(`Tier mis à jour en "${newTier.toUpperCase()}" avec succès.`);
    } catch (err) {
      console.error("Erreur mise à jour tier:", err);
      setErrorMsg("Impossible de mettre à jour le tier.");
    } finally {
      setUpdatingUserId(null);
    }
  };

  const handleToggleStatus = async (userId: string, currentDisabled: boolean) => {
    try {
      setUpdatingUserId(userId);
      const updated = await adminApi.toggleStatus(userId, !currentDisabled);
      setUsersList((prev) => prev.map((u) => (u.id === userId ? updated : u)));
      showToast(
        !currentDisabled
          ? "Compte désactivé avec succès."
          : "Compte réactivé avec succès."
      );
    } catch (err: unknown) {
      console.error("Erreur toggle status:", err);
      const msg = err instanceof Error ? err.message : "Erreur lors du changement de statut.";
      setErrorMsg(msg);
    } finally {
      setUpdatingUserId(null);
    }
  };

  const handleExecuteGdprErasure = async () => {
    if (!gdprDeleteUser || gdprConfirmInput !== "SUPPRIMER") return;
    try {
      setIsDeletingGdpr(true);
      await adminApi.deleteUserGdpr(gdprDeleteUser.id);
      setUsersList((prev) => prev.filter((u) => u.id !== gdprDeleteUser.id));
      setGdprDeleteUser(null);
      setGdprConfirmInput("");
      showToast("Compte utilisateur effacé et anonymisé conformément au RGPD.");
    } catch (err: unknown) {
      console.error("Erreur suppression RGPD:", err);
      const msg = err instanceof Error ? err.message : "Erreur lors de l'effacement RGPD.";
      setErrorMsg(msg);
    } finally {
      setIsDeletingGdpr(false);
    }
  };

  // Filtrage des utilisateurs
  const filteredUsers = useMemo(() => {
    return usersList.filter((u) => {
      const matchSearch =
        u.pseudonym_email.toLowerCase().includes(searchQuery.toLowerCase()) ||
        u.pseudonym_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        u.id.toLowerCase().includes(searchQuery.toLowerCase());
      const matchTier = tierFilter === "all" || u.tier === tierFilter;
      return matchSearch && matchTier;
    });
  }, [usersList, searchQuery, tierFilter]);

  // Si en cours de vérification auth
  if (isAuthLoading) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center text-white">
        <FiRefreshCw className="w-8 h-8 text-blue-500 animate-spin mb-4" />
        <p className="text-slate-400 font-medium">Vérification des droits d'administration...</p>
      </div>
    );
  }

  // Si accès interdit
  if (isForbidden || !currentUser) {
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
            Retour à l'application
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 pb-20">
      {/* Toast Notification */}
      {successToast && (
        <div className="fixed bottom-6 right-6 z-50 bg-emerald-500/90 text-white px-5 py-3 rounded-xl shadow-xl flex items-center gap-2.5 backdrop-blur border border-emerald-400/40 animate-slide-up">
          <FiCheckCircle className="w-5 h-5 shrink-0" />
          <span className="text-sm font-medium">{successToast}</span>
        </div>
      )}

      {/* Header Admin */}
      <div className="border-b border-slate-800 bg-slate-900/60 backdrop-blur sticky top-0 z-40">
        <div className="container mx-auto px-4 py-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-gradient-to-tr from-amber-500 to-indigo-600 flex items-center justify-center text-white shadow-lg shadow-amber-500/10">
              <FiShield className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold text-white tracking-tight">
                  Espace Administration
                </h1>
                <span className="px-2 py-0.5 text-[11px] font-bold rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 uppercase tracking-wider">
                  Admin Master
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Suivi analytique des coûts LLM, volume d'appels et gestion conforme RGPD
              </p>
            </div>
          </div>

          {/* Sélecteur de Période & Rafraîchissement */}
          <div className="flex items-center gap-2.5">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-1 flex items-center shadow-inner">
              {(
                [
                  { id: "24h", label: "24h" },
                  { id: "7d", label: "7j" },
                  { id: "30d", label: "30j" },
                  { id: "all", label: "Tout" },
                ] as const
              ).map((p) => (
                <button
                  key={p.id}
                  onClick={() => setPeriod(p.id)}
                  className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                    period === p.id
                      ? "bg-blue-600 text-white shadow-sm"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>

            <button
              onClick={() => loadDashboardData()}
              disabled={isLoadingData}
              className="p-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 hover:text-white transition-all shadow-sm"
              title="Rafraîchir les données"
            >
              <FiRefreshCw className={`w-4 h-4 ${isLoadingData ? "animate-spin text-blue-400" : ""}`} />
            </button>
          </div>
        </div>

        {/* Onglets */}
        <div className="container mx-auto px-4 flex gap-6 pt-1">
          <button
            onClick={() => setActiveTab("costs")}
            className={`pb-3 text-sm font-semibold border-b-2 flex items-center gap-2 transition-colors ${
              activeTab === "costs"
                ? "border-blue-500 text-blue-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <FiActivity className="w-4 h-4" />
            Coûts & Usage API
          </button>
          <button
            onClick={() => setActiveTab("users")}
            className={`pb-3 text-sm font-semibold border-b-2 flex items-center gap-2 transition-colors ${
              activeTab === "users"
                ? "border-blue-500 text-blue-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <FiUsers className="w-4 h-4" />
            Gestion Utilisateurs & RGPD
            <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] bg-slate-800 text-slate-300">
              {usersList.length}
            </span>
          </button>
        </div>
      </div>

      <div className="container mx-auto px-4 pt-8">
        {/* Message d'erreur s'il y a lieu */}
        {errorMsg && (
          <div className="mb-6 bg-rose-500/10 border border-rose-500/30 rounded-2xl p-4 text-rose-300 flex items-center gap-3">
            <FiAlertTriangle className="w-5 h-5 shrink-0" />
            <span className="text-sm">{errorMsg}</span>
          </div>
        )}

        {/* ============================================================== */}
        {/* ONGLET 1 : COÛTS & USAGE API                                  */}
        {/* ============================================================== */}
        {activeTab === "costs" && (
          <div className="space-y-8 animate-fade-in">
            {/* Grille des 4 KPIs */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
              {/* KPI 1 : Dépense totale */}
              <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-5 shadow-lg backdrop-blur">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    Dépense Totale
                  </span>
                  <div className="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center border border-emerald-500/20">
                    <FiDollarSign className="w-4 h-4" />
                  </div>
                </div>
                <div className="text-2xl font-black text-white tracking-tight">
                  ${costSummary ? costSummary.total_cost_usd.toFixed(4) : "0.0000"}
                </div>
                <div className="text-[11px] text-slate-400 mt-1 flex items-center gap-1">
                  <span>Période active :</span>
                  <span className="font-semibold text-emerald-400 uppercase">{period}</span>
                </div>
              </div>

              {/* KPI 2 : Tokens */}
              <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-5 shadow-lg backdrop-blur">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    Tokens Consommés
                  </span>
                  <div className="w-8 h-8 rounded-lg bg-blue-500/10 text-blue-400 flex items-center justify-center border border-blue-500/20">
                    <FiCpu className="w-4 h-4" />
                  </div>
                </div>
                <div className="text-2xl font-black text-white tracking-tight">
                  {costSummary ? costSummary.total_tokens.toLocaleString() : "0"}
                </div>
                <div className="text-[11px] text-slate-400 mt-1">
                  Entrée + sortie cumulées
                </div>
              </div>

              {/* KPI 3 : Requêtes API */}
              <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-5 shadow-lg backdrop-blur">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    Appels LLM
                  </span>
                  <div className="w-8 h-8 rounded-lg bg-indigo-500/10 text-indigo-400 flex items-center justify-center border border-indigo-500/20">
                    <FiActivity className="w-4 h-4" />
                  </div>
                </div>
                <div className="text-2xl font-black text-white tracking-tight">
                  {costSummary ? costSummary.total_requests.toLocaleString() : "0"}
                </div>
                <div className="text-[11px] text-slate-400 mt-1">
                  Générations et inférences
                </div>
              </div>

              {/* KPI 4 : Coût moyen / User */}
              <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-5 shadow-lg backdrop-blur">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    Coût Moyen / Utilisateur
                  </span>
                  <div className="w-8 h-8 rounded-lg bg-amber-500/10 text-amber-400 flex items-center justify-center border border-amber-500/20">
                    <FiUsers className="w-4 h-4" />
                  </div>
                </div>
                <div className="text-2xl font-black text-white tracking-tight">
                  ${costSummary ? costSummary.avg_cost_per_user.toFixed(4) : "0.0000"}
                </div>
                <div className="text-[11px] text-slate-400 mt-1">
                  Sur {costSummary?.active_users_count || 0} utilisateur(s) actif(s)
                </div>
              </div>
            </div>

            {/* Répartition par Modèle IA */}
            <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-6 shadow-xl backdrop-blur">
              <div className="flex items-center justify-between mb-5">
                <div>
                  <h3 className="text-base font-bold text-white flex items-center gap-2">
                    <FiCpu className="text-blue-400" />
                    Répartition des Dépenses par Modèle IA
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Coûts unitaires et volume de tokens par modèle (OpenAI, Gemini, Mistral)
                  </p>
                </div>
              </div>

              {costSummary?.model_breakdown && costSummary.model_breakdown.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b border-slate-800 text-xs text-slate-400 font-semibold uppercase tracking-wider">
                        <th className="pb-3 pl-2">Modèle</th>
                        <th className="pb-3 text-right">Appels</th>
                        <th className="pb-3 text-right">Tokens In / Out</th>
                        <th className="pb-3 text-right">Total Tokens</th>
                        <th className="pb-3 text-right">Coût ($ USD)</th>
                        <th className="pb-3 pr-2 text-right">% du Budget</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {costSummary.model_breakdown.map((m) => {
                        const pct =
                          costSummary.total_cost_usd > 0
                            ? Math.min(100, (m.cost_usd / costSummary.total_cost_usd) * 100)
                            : 0;
                        return (
                          <tr key={m.model} className="hover:bg-slate-800/30 transition-colors">
                            <td className="py-3 pl-2 font-semibold text-white">
                              <span className="font-mono text-xs text-blue-300 bg-blue-950/60 px-2 py-1 rounded-lg border border-blue-800/40">
                                {m.model}
                              </span>
                            </td>
                            <td className="py-3 text-right text-slate-300 font-mono text-xs">
                              {m.requests_count.toLocaleString()}
                            </td>
                            <td className="py-3 text-right text-slate-400 font-mono text-xs">
                              {m.input_tokens.toLocaleString()} / {m.output_tokens.toLocaleString()}
                            </td>
                            <td className="py-3 text-right text-slate-200 font-mono text-xs font-semibold">
                              {m.total_tokens.toLocaleString()}
                            </td>
                            <td className="py-3 text-right text-emerald-400 font-mono text-xs font-bold">
                              ${m.cost_usd.toFixed(4)}
                            </td>
                            <td className="py-3 pr-2 text-right">
                              <div className="flex items-center justify-end gap-2">
                                <div className="w-20 bg-slate-800 rounded-full h-1.5 overflow-hidden">
                                  <div
                                    className="bg-emerald-500 h-1.5 rounded-full"
                                    style={{ width: `${pct}%` }}
                                  />
                                </div>
                                <span className="text-xs text-slate-400 font-mono w-10 text-right">
                                  {pct.toFixed(1)}%
                                </span>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-center py-12 text-slate-500 text-sm">
                  Aucun appel API enregistré pour cette période.
                </div>
              )}
            </div>

            {/* Répartition par Fonctionnalité */}
            <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-6 shadow-xl backdrop-blur">
              <div className="flex items-center justify-between mb-5">
                <div>
                  <h3 className="text-base font-bold text-white flex items-center gap-2">
                    <FiZap className="text-amber-400" />
                    Consommation par Fonctionnalité Métier
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Coûts imputables aux différents générateurs (STAR+R, CV ATS, Lettres, Évaluations)
                  </p>
                </div>
              </div>

              {costSummary?.action_breakdown && costSummary.action_breakdown.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {costSummary.action_breakdown.map((a) => {
                    const Icon = ACTION_ICONS[a.action] || FiZap;
                    const pct =
                      costSummary.total_cost_usd > 0
                        ? Math.min(100, (a.cost_usd / costSummary.total_cost_usd) * 100)
                        : 0;
                    return (
                      <div
                        key={a.action}
                        className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 flex flex-col justify-between"
                      >
                        <div className="flex items-start justify-between gap-3 mb-3">
                          <div className="flex items-center gap-2.5">
                            <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20">
                              <Icon className="w-4 h-4" />
                            </div>
                            <span className="font-semibold text-sm text-slate-200 leading-snug">
                              {a.label}
                            </span>
                          </div>
                          <span className="text-xs font-mono font-bold text-emerald-400 shrink-0">
                            ${a.cost_usd.toFixed(4)}
                          </span>
                        </div>

                        <div>
                          <div className="flex justify-between text-[11px] text-slate-400 mb-1">
                            <span>{a.requests_count} appels</span>
                            <span>{a.total_tokens.toLocaleString()} tokens</span>
                          </div>
                          <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                            <div
                              className="bg-blue-500 h-1.5 rounded-full"
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="text-center py-12 text-slate-500 text-sm">
                  Aucun appel API enregistré pour cette période.
                </div>
              )}
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* ONGLET 2 : GESTION DES UTILISATEURS & RGPD                     */}
        {/* ============================================================== */}
        {activeTab === "users" && (
          <div className="space-y-6 animate-fade-in">
            {/* Bannière de Conformité RGPD */}
            <div className="bg-blue-950/40 border border-blue-800/40 rounded-2xl p-4 flex items-start gap-3.5 shadow-sm">
              <div className="p-2 rounded-lg bg-blue-500/20 text-blue-400 shrink-0 border border-blue-500/30">
                <FiShield className="w-5 h-5" />
              </div>
              <div className="text-xs text-blue-200/90 leading-relaxed">
                <p className="font-bold text-white text-sm mb-0.5">
                  Conformité RGPD & Minimisation des Données
                </p>
                Conformément aux principes de confidentialité par conception (Privacy by Design), les identités ci-dessous sont
                strictement pseudonymisées (<code className="text-blue-300">a***e@domaine.com</code>). Aucun contenu privé (textes des CV,
                lettres de motivation, candidatures détaillées) n'est exposé. Vous disposez du bouton droit à l'oubli pour purger
                intégralement les données d'un compte sur demande.
              </div>
            </div>

            {/* Barre de Recherche et Filtres */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4 bg-slate-900/60 border border-slate-800 p-4 rounded-2xl">
              <div className="relative w-full sm:w-80">
                <FiSearch className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500 w-4 h-4" />
                <input
                  type="text"
                  placeholder="Rechercher par email pseudonymisé..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-3.5 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
                />
              </div>

              <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
                <span className="text-xs text-slate-400 flex items-center gap-1 font-medium">
                  <FiFilter className="w-3.5 h-3.5" />
                  Filtrer par Tier:
                </span>
                <select
                  value={tierFilter}
                  onChange={(e) => setTierFilter(e.target.value)}
                  className="bg-slate-950 border border-slate-800 text-slate-200 rounded-xl px-3 py-1.5 text-xs font-semibold focus:outline-none focus:border-blue-500"
                >
                  <option value="all">Tous les tiers</option>
                  <option value="free">Free</option>
                  <option value="advanced">Advanced</option>
                  <option value="pro">Pro</option>
                </select>
              </div>
            </div>

            {/* Tableau des Utilisateurs */}
            <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl shadow-xl overflow-hidden backdrop-blur">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-slate-800 text-xs text-slate-400 font-semibold uppercase tracking-wider bg-slate-950/40">
                      <th className="py-3.5 pl-4">Utilisateur (Pseudonymisé)</th>
                      <th className="py-3.5">Tier d'Abonnement</th>
                      <th className="py-3.5">Rôle</th>
                      <th className="py-3.5">Statut</th>
                      <th className="py-3.5">Inscription</th>
                      <th className="py-3.5 text-right">Appels LLM</th>
                      <th className="py-3.5 text-right">Coût Généré</th>
                      <th className="py-3.5 pr-4 text-center">Actions RGPD</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {filteredUsers.length > 0 ? (
                      filteredUsers.map((u) => {
                        const isSelf = u.id === currentUser?.id;
                        const isUpdating = updatingUserId === u.id;
                        return (
                          <tr key={u.id} className="hover:bg-slate-800/30 transition-colors">
                            {/* Identité pseudonymisée */}
                            <td className="py-4 pl-4">
                              <div className="flex items-center gap-3">
                                <div className="w-9 h-9 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center font-bold text-white text-xs shrink-0">
                                  {u.pseudonym_name.charAt(0)}
                                </div>
                                <div className="min-w-0">
                                  <div className="font-semibold text-white text-xs truncate">
                                    {u.pseudonym_name}
                                  </div>
                                  <div className="font-mono text-[11px] text-slate-400 truncate">
                                    {u.pseudonym_email}
                                  </div>
                                </div>
                              </div>
                            </td>

                            {/* Tier avec sélecteur direct */}
                            <td className="py-4">
                              <select
                                value={u.tier}
                                disabled={isUpdating}
                                onChange={(e) =>
                                  handleUpdateTier(u.id, e.target.value as "free" | "advanced" | "pro")
                                }
                                className={`text-xs font-bold rounded-lg px-2.5 py-1 border transition-all cursor-pointer ${
                                  u.tier === "pro"
                                    ? "bg-purple-500/10 text-purple-300 border-purple-500/30"
                                    : u.tier === "advanced"
                                    ? "bg-blue-500/10 text-blue-300 border-blue-500/30"
                                    : "bg-slate-800 text-slate-300 border-slate-700"
                                }`}
                              >
                                <option value="free" className="bg-slate-900 text-white">
                                  Free
                                </option>
                                <option value="advanced" className="bg-slate-900 text-white">
                                  Advanced
                                </option>
                                <option value="pro" className="bg-slate-900 text-white">
                                  Pro
                                </option>
                              </select>
                            </td>

                            {/* Rôle */}
                            <td className="py-4">
                              <span
                                className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                                  u.role === "admin"
                                    ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                                    : "bg-slate-800 text-slate-400"
                                }`}
                              >
                                {u.role}
                              </span>
                            </td>

                            {/* Statut actif / inactif */}
                            <td className="py-4">
                              <span
                                className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                                  u.disabled
                                    ? "bg-rose-500/10 text-rose-400 border border-rose-500/30"
                                    : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                                }`}
                              >
                                <span
                                  className={`w-1.5 h-1.5 rounded-full ${
                                    u.disabled ? "bg-rose-400" : "bg-emerald-400"
                                  }`}
                                />
                                {u.disabled ? "Désactivé" : "Actif"}
                              </span>
                            </td>

                            {/* Date création */}
                            <td className="py-4 text-xs text-slate-400">
                              {new Date(u.created_at).toLocaleDateString("fr-FR", {
                                day: "2-digit",
                                month: "2-digit",
                                year: "numeric",
                              })}
                            </td>

                            {/* Appels LLM */}
                            <td className="py-4 text-right font-mono text-xs text-slate-300">
                              {u.total_requests.toLocaleString()}
                            </td>

                            {/* Coût USD */}
                            <td className="py-4 text-right font-mono text-xs font-bold text-emerald-400">
                              ${u.total_cost_usd.toFixed(4)}
                            </td>

                            {/* Actions directes */}
                            <td className="py-4 pr-4">
                              <div className="flex items-center justify-center gap-2">
                                {/* Bascule Statut */}
                                <button
                                  onClick={() => handleToggleStatus(u.id, u.disabled)}
                                  disabled={isSelf || isUpdating}
                                  className={`px-2.5 py-1 rounded-lg text-xs font-semibold border transition-all ${
                                    isSelf
                                      ? "opacity-30 cursor-not-allowed border-slate-800 text-slate-600"
                                      : u.disabled
                                      ? "bg-emerald-600/20 text-emerald-300 border-emerald-500/40 hover:bg-emerald-600/30"
                                      : "bg-slate-800 hover:bg-rose-600/20 text-slate-400 hover:text-rose-300 border-slate-700"
                                  }`}
                                  title={
                                    isSelf
                                      ? "Impossible de désactiver votre propre compte"
                                      : u.disabled
                                      ? "Réactiver ce compte"
                                      : "Désactiver ce compte"
                                  }
                                >
                                  {u.disabled ? "Réactiver" : "Désactiver"}
                                </button>

                                {/* Droit à l'oubli RGPD */}
                                <button
                                  onClick={() => {
                                    setGdprDeleteUser(u);
                                    setGdprConfirmInput("");
                                  }}
                                  disabled={isSelf || isUpdating}
                                  className={`p-1.5 rounded-lg border transition-all ${
                                    isSelf
                                      ? "opacity-30 cursor-not-allowed border-slate-800 text-slate-600"
                                      : "bg-slate-800 hover:bg-rose-600 text-slate-400 hover:text-white border-slate-700"
                                  }`}
                                  title={
                                    isSelf
                                      ? "Impossible de supprimer votre propre compte"
                                      : "Droit à l'oubli RGPD (Effacement définitif)"
                                  }
                                >
                                  <FiTrash2 className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })
                    ) : (
                      <tr>
                        <td colSpan={8} className="py-12 text-center text-slate-500 text-sm">
                          Aucun utilisateur correspondant aux critères.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Modal Confirmation Droit à l'oubli RGPD */}
      {gdprDeleteUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in">
          <div className="bg-slate-900 border border-rose-500/40 rounded-2xl max-w-lg w-full p-6 shadow-2xl">
            <div className="flex items-center gap-3 text-rose-400 mb-4">
              <div className="p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/20">
                <FiTrash2 className="w-6 h-6" />
              </div>
              <div>
                <h3 className="font-bold text-lg text-white">
                  Droit à l'Oubli RGPD — Suppression Définitive
                </h3>
                <p className="text-xs text-rose-300">
                  Cette action est irréversible et purge toutes les données privées
                </p>
              </div>
            </div>

            <div className="text-xs text-slate-300 space-y-2 mb-6 bg-slate-950 p-4 rounded-xl border border-slate-800">
              <p>
                Vous êtes sur le point de purger le compte{" "}
                <span className="font-mono font-bold text-white">
                  {gdprDeleteUser.pseudonym_email}
                </span>{" "}
                (ID: <span className="font-mono text-slate-400">{gdprDeleteUser.id}</span>).
              </p>
              <ul className="list-disc pl-4 space-y-1 text-slate-400">
                <li>Suppression définitive du compte et identifiants</li>
                <li>Suppression de toutes les candidatures, lettres et CV générés</li>
                <li>Suppression des préférences et critères de matching</li>
                <li>
                  Anonymisation de l'historique d'usage API pour préserver les totaux financiers
                </li>
              </ul>
            </div>

            <div className="mb-6">
              <label className="block text-xs font-semibold text-slate-300 mb-2">
                Pour confirmer, veuillez saisir <span className="text-rose-400 font-mono">SUPPRIMER</span> :
              </label>
              <input
                type="text"
                value={gdprConfirmInput}
                onChange={(e) => setGdprConfirmInput(e.target.value)}
                placeholder="SUPPRIMER"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-rose-500"
              />
            </div>

            <div className="flex items-center justify-end gap-3">
              <button
                onClick={() => {
                  setGdprDeleteUser(null);
                  setGdprConfirmInput("");
                }}
                disabled={isDeletingGdpr}
                className="px-4 py-2 text-xs font-semibold rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
              >
                Annuler
              </button>
              <button
                onClick={handleExecuteGdprErasure}
                disabled={gdprConfirmInput !== "SUPPRIMER" || isDeletingGdpr}
                className="px-5 py-2 text-xs font-semibold rounded-xl bg-rose-600 hover:bg-rose-500 disabled:opacity-40 disabled:cursor-not-allowed text-white transition-all shadow-lg shadow-rose-600/20 flex items-center gap-2"
              >
                {isDeletingGdpr ? (
                  <>
                    <FiRefreshCw className="w-3.5 h-3.5 animate-spin" />
                    Purge en cours...
                  </>
                ) : (
                  <>
                    <FiTrash2 className="w-3.5 h-3.5" />
                    Purger définitivement
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
