"use client";

import React from "react";
import { AdminUserSummary } from "@/types/admin";
import { User } from "@/lib/api";
import { FiShield, FiSearch, FiFilter, FiTrash2 } from "react-icons/fi";

interface AdminUsersTabProps {
  currentUser: User | null;
  filteredUsers: AdminUserSummary[];
  searchQuery: string;
  tierFilter: string;
  updatingUserId: string | null;
  onSearchChange: (val: string) => void;
  onTierFilterChange: (val: string) => void;
  onUpdateTier: (userId: string, tier: "free" | "advanced" | "pro") => void;
  onToggleStatus: (userId: string, disabled: boolean) => void;
  onRequestGdprDelete: (user: AdminUserSummary) => void;
}

/**
 * Displays pseudonymized users table, tier filters, account status toggle, and GDPR erasure triggers.
 */
export function AdminUsersTab({
  currentUser,
  filteredUsers,
  searchQuery,
  tierFilter,
  updatingUserId,
  onSearchChange,
  onTierFilterChange,
  onUpdateTier,
  onToggleStatus,
  onRequestGdprDelete,
}: AdminUsersTabProps) {
  return (
    <div className="space-y-6 animate-fade-in">
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
          lettres de motivation, candidatures détaillées) n&apos;est exposé. Vous disposez du bouton droit à l&apos;oubli pour purger
          intégralement les données d&apos;un compte sur demande.
        </div>
      </div>

      {/* Filters Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 bg-slate-900/60 border border-slate-800 p-4 rounded-2xl">
        <div className="relative w-full sm:w-80">
          <FiSearch className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500 w-4 h-4" />
          <input
            type="text"
            placeholder="Rechercher par email pseudonymisé..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
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
            onChange={(e) => onTierFilterChange(e.target.value)}
            className="bg-slate-950 border border-slate-800 text-slate-200 rounded-xl px-3 py-1.5 text-xs font-semibold focus:outline-none focus:border-blue-500"
          >
            <option value="all">Tous les tiers</option>
            <option value="free">Free</option>
            <option value="advanced">Advanced</option>
            <option value="pro">Pro</option>
          </select>
        </div>
      </div>

      {/* Users Table */}
      <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl shadow-xl overflow-hidden backdrop-blur">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-800 text-xs text-slate-400 font-semibold uppercase tracking-wider bg-slate-950/40">
                <th className="py-3.5 pl-4">Utilisateur (Pseudonymisé)</th>
                <th className="py-3.5">Tier d&apos;Abonnement</th>
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

                      <td className="py-4">
                        <select
                          value={u.tier}
                          disabled={isUpdating}
                          onChange={(e) =>
                            onUpdateTier(u.id, e.target.value as "free" | "advanced" | "pro")
                          }
                          className={`text-xs font-bold rounded-lg px-2.5 py-1 border transition-all cursor-pointer ${
                            u.tier === "pro"
                              ? "bg-purple-500/10 text-purple-300 border-purple-500/30"
                              : u.tier === "advanced"
                              ? "bg-blue-500/10 text-blue-300 border-blue-500/30"
                              : "bg-slate-800 text-slate-300 border-slate-700"
                          }`}
                        >
                          <option value="free" className="bg-slate-900 text-white">Free</option>
                          <option value="advanced" className="bg-slate-900 text-white">Advanced</option>
                          <option value="pro" className="bg-slate-900 text-white">Pro</option>
                        </select>
                      </td>

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

                      <td className="py-4 text-xs text-slate-400">
                        {new Date(u.created_at).toLocaleDateString("fr-FR", {
                          day: "2-digit",
                          month: "2-digit",
                          year: "numeric",
                        })}
                      </td>

                      <td className="py-4 text-right font-mono text-xs text-slate-300">
                        {u.total_requests.toLocaleString()}
                      </td>

                      <td className="py-4 text-right font-mono text-xs font-bold text-emerald-400">
                        ${u.total_cost_usd.toFixed(4)}
                      </td>

                      <td className="py-4 pr-4">
                        <div className="flex items-center justify-center gap-2">
                          <button
                            onClick={() => onToggleStatus(u.id, u.disabled)}
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

                          <button
                            onClick={() => onRequestGdprDelete(u)}
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
  );
}
