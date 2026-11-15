"use client";

import { FiClock, FiChevronLeft, FiChevronRight } from "react-icons/fi";
import type { ApiUsageRecord } from "@/types/usage";
import { ACTION_CONFIG } from "./UsageQuotaGauges";

interface UsageAuditLogProps {
  records: ApiUsageRecord[];
  currentPage: number;
  pageSize?: number;
  onPageChange: (page: number) => void;
}

export default function UsageAuditLog({
  records,
  currentPage,
  pageSize = 10,
  onPageChange,
}: UsageAuditLogProps) {
  const totalPages = Math.max(1, Math.ceil(records.length / pageSize));
  const safeCurrentPage = Math.min(currentPage, totalPages);
  const paginatedRecords = records.slice(
    (safeCurrentPage - 1) * pageSize,
    safeCurrentPage * pageSize
  );

  return (
    <div className="space-y-4 pt-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            <FiClock className="w-5 h-5 text-indigo-400" />
            Journal Récent des Appels IA
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Historique des {records.length} dernières opérations déclenchées
          </p>
        </div>
        {records.length > 0 && (
          <span className="text-xs text-slate-400 bg-slate-900 border border-slate-800 px-3 py-1 rounded-full self-start sm:self-auto font-mono">
            {records.length} opération{records.length > 1 ? "s" : ""}
          </span>
        )}
      </div>

      <div className="bg-slate-900/70 border border-slate-800 rounded-2xl overflow-hidden shadow-xl flex flex-col">
        {records.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-500">
            Aucun appel IA enregistré récemment.
          </div>
        ) : (
          <>
            <div className="max-h-[460px] overflow-y-auto overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="sticky top-0 bg-slate-950/95 backdrop-blur z-10 text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-800">
                  <tr>
                    <th className="py-3 px-4 whitespace-nowrap">Date / Heure</th>
                    <th className="py-3 px-4">Action</th>
                    <th className="py-3 px-4 whitespace-nowrap">Tokens (In / Out)</th>
                    <th className="py-3 px-4 whitespace-nowrap">Latence</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-slate-300">
                  {paginatedRecords.map((rec, idx) => {
                    const dateStr = new Date(rec.created_at).toLocaleString("fr-FR", {
                      day: "2-digit",
                      month: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                    });
                    const config = ACTION_CONFIG[rec.action];
                    const actionLabel = config?.label || rec.action;
                    const ActionIcon = config?.icon || FiClock;

                    return (
                      <tr key={rec.id || idx} className="hover:bg-slate-800/30 transition-colors">
                        <td className="py-3 px-4 text-slate-400 whitespace-nowrap">{dateStr}</td>
                        <td className="py-3 px-4 whitespace-nowrap">
                          <div className="flex items-center gap-2">
                            <div className="p-1 rounded-md bg-slate-800 text-indigo-400 shrink-0">
                              <ActionIcon className="w-3.5 h-3.5" />
                            </div>
                            <span className="font-semibold text-white">{actionLabel}</span>
                          </div>
                        </td>
                        <td className="py-3 px-4 font-mono text-[11px] whitespace-nowrap">
                          <span className="text-slate-200">
                            {rec.input_tokens.toLocaleString()}
                          </span>
                          <span className="text-slate-500 mx-1">/</span>
                          <span className="text-slate-400">
                            {rec.output_tokens.toLocaleString()}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-slate-400 whitespace-nowrap font-mono text-[11px]">
                          {rec.latency_ms ? `${rec.latency_ms} ms` : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 px-4 py-3 bg-slate-950/70 border-t border-slate-800 text-xs text-slate-400">
              <div>
                Affichage de{" "}
                <span className="font-semibold text-slate-200">
                  {(safeCurrentPage - 1) * pageSize + 1}
                </span>{" "}
                à{" "}
                <span className="font-semibold text-slate-200">
                  {Math.min(safeCurrentPage * pageSize, records.length)}
                </span>{" "}
                sur <span className="font-semibold text-slate-200">{records.length}</span>{" "}
                opérations
              </div>

              {totalPages > 1 && (
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => onPageChange(Math.max(1, safeCurrentPage - 1))}
                    disabled={safeCurrentPage <= 1}
                    className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700/80 text-slate-300 disabled:opacity-40 disabled:cursor-not-allowed transition border border-slate-700/60"
                  >
                    <FiChevronLeft className="w-4 h-4" />
                    <span>Précédent</span>
                  </button>
                  <span className="px-2 font-medium text-slate-300">
                    Page {safeCurrentPage} sur {totalPages}
                  </span>
                  <button
                    type="button"
                    onClick={() => onPageChange(Math.min(totalPages, safeCurrentPage + 1))}
                    disabled={safeCurrentPage >= totalPages}
                    className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700/80 text-slate-300 disabled:opacity-40 disabled:cursor-not-allowed transition border border-slate-700/60"
                  >
                    <span>Suivant</span>
                    <FiChevronRight className="w-4 h-4" />
                  </button>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
