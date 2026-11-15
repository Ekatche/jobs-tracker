"use client";

import React from "react";
import { AdminUserSummary } from "@/types/admin";
import { FiTrash2, FiRefreshCw } from "react-icons/fi";

interface AdminGdprModalProps {
  user: AdminUserSummary | null;
  confirmInput: string;
  isDeleting: boolean;
  onConfirmInputChange: (value: string) => void;
  onCancel: () => void;
  onExecute: () => void;
}

/**
 * Confirmation modal for irreversible GDPR user data erasure.
 */
export function AdminGdprModal({
  user,
  confirmInput,
  isDeleting,
  onConfirmInputChange,
  onCancel,
  onExecute,
}: AdminGdprModalProps) {
  if (!user) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in">
      <div className="bg-slate-900 border border-rose-500/40 rounded-2xl max-w-lg w-full p-6 shadow-2xl">
        <div className="flex items-center gap-3 text-rose-400 mb-4">
          <div className="p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/20">
            <FiTrash2 className="w-6 h-6" />
          </div>
          <div>
            <h3 className="font-bold text-lg text-white">
              Droit à l&apos;Oubli RGPD — Suppression Définitive
            </h3>
            <p className="text-xs text-rose-300">
              Cette action est irréversible et purge toutes les données privées
            </p>
          </div>
        </div>

        <div className="text-xs text-slate-300 space-y-2 mb-6 bg-slate-950 p-4 rounded-xl border border-slate-800">
          <p>
            Vous êtes sur le point de purger le compte{" "}
            <span className="font-mono font-bold text-white">{user.pseudonym_email}</span>{" "}
            (ID: <span className="font-mono text-slate-400">{user.id}</span>).
          </p>
          <ul className="list-disc pl-4 space-y-1 text-slate-400">
            <li>Suppression définitive du compte et identifiants</li>
            <li>Suppression de toutes les candidatures, lettres et CV générés</li>
            <li>Suppression des préférences et critères de matching</li>
            <li>Anonymisation de l&apos;historique d&apos;usage API pour préserver les totaux financiers</li>
          </ul>
        </div>

        <div className="mb-6">
          <label className="block text-xs font-semibold text-slate-300 mb-2">
            Pour confirmer, veuillez saisir <span className="text-rose-400 font-mono">SUPPRIMER</span> :
          </label>
          <input
            type="text"
            value={confirmInput}
            onChange={(e) => onConfirmInputChange(e.target.value)}
            placeholder="SUPPRIMER"
            className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-rose-500"
          />
        </div>

        <div className="flex items-center justify-end gap-3">
          <button
            onClick={onCancel}
            disabled={isDeleting}
            className="px-4 py-2 text-xs font-semibold rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
          >
            Annuler
          </button>
          <button
            onClick={onExecute}
            disabled={confirmInput !== "SUPPRIMER" || isDeleting}
            className="px-5 py-2 text-xs font-semibold rounded-xl bg-rose-600 hover:bg-rose-500 disabled:opacity-40 disabled:cursor-not-allowed text-white transition-all shadow-lg shadow-rose-600/20 flex items-center gap-2"
          >
            {isDeleting ? (
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
  );
}
