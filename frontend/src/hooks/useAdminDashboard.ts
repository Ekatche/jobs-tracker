"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { adminApi, authApi, User } from "@/lib/api";
import { AdminCostSummary, AdminPeriod, AdminUserSummary } from "@/types/admin";

/**
 * Manages admin authentication verification, cost/user loading, and GDPR user actions.
 */
export function useAdminDashboard() {
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [isAuthLoading, setIsAuthLoading] = useState(true);
  const [isForbidden, setIsForbidden] = useState(false);

  const [activeTab, setActiveTab] = useState<"costs" | "users">("costs");
  const [period, setPeriod] = useState<AdminPeriod>("30d");
  const [costSummary, setCostSummary] = useState<AdminCostSummary | null>(null);
  const [usersList, setUsersList] = useState<AdminUserSummary[]>([]);
  const [isLoadingData, setIsLoadingData] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successToast, setSuccessToast] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [tierFilter, setTierFilter] = useState<string>("all");
  const [updatingUserId, setUpdatingUserId] = useState<string | null>(null);

  const [gdprDeleteUser, setGdprDeleteUser] = useState<AdminUserSummary | null>(null);
  const [gdprConfirmInput, setGdprConfirmInput] = useState("");
  const [isDeletingGdpr, setIsDeletingGdpr] = useState(false);

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
      setErrorMsg(err instanceof Error ? err.message : "Erreur de chargement des données.");
    } finally {
      setIsLoadingData(false);
    }
  }, [period, isForbidden]);

  useEffect(() => {
    if (!isAuthLoading && !isForbidden) {
      loadDashboardData();
    }
  }, [isAuthLoading, isForbidden, loadDashboardData]);

  const showToast = (msg: string) => {
    setSuccessToast(msg);
    setTimeout(() => setSuccessToast(null), 4000);
  };

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
      showToast(!currentDisabled ? "Compte désactivé avec succès." : "Compte réactivé avec succès.");
    } catch (err: unknown) {
      console.error("Erreur toggle status:", err);
      setErrorMsg(err instanceof Error ? err.message : "Erreur lors du changement de statut.");
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
      setErrorMsg(err instanceof Error ? err.message : "Erreur lors de l'effacement RGPD.");
    } finally {
      setIsDeletingGdpr(false);
    }
  };

  const filteredUsers = useMemo(() => {
    return usersList.filter((u) => {
      const q = searchQuery.toLowerCase();
      const matchSearch =
        u.pseudonym_email.toLowerCase().includes(q) ||
        u.pseudonym_name.toLowerCase().includes(q) ||
        u.id.toLowerCase().includes(q);
      const matchTier = tierFilter === "all" || u.tier === tierFilter;
      return matchSearch && matchTier;
    });
  }, [usersList, searchQuery, tierFilter]);

  return {
    currentUser,
    isAuthLoading,
    isForbidden,
    activeTab,
    setActiveTab,
    period,
    setPeriod,
    costSummary,
    usersList,
    filteredUsers,
    isLoadingData,
    errorMsg,
    successToast,
    searchQuery,
    setSearchQuery,
    tierFilter,
    setTierFilter,
    updatingUserId,
    gdprDeleteUser,
    setGdprDeleteUser,
    gdprConfirmInput,
    setGdprConfirmInput,
    isDeletingGdpr,
    loadDashboardData,
    handleUpdateTier,
    handleToggleStatus,
    handleExecuteGdprErasure,
  };
}
