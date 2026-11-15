"use client";

import { memo } from "react";

interface OffersPaginationProps {
  currentPage: number;
  totalOffers: number;
  itemsPerPage: number;
  onPageChange: (page: number) => void;
}

const OffersPagination = memo(function OffersPagination({
  currentPage,
  totalOffers,
  itemsPerPage,
  onPageChange,
}: OffersPaginationProps) {
  const totalPages = Math.ceil(totalOffers / itemsPerPage);
  if (totalPages <= 1) return null;

  const getPageNumbers = (): (number | string)[] => {
    const delta = 1;
    const range: number[] = [];
    for (
      let i = Math.max(2, currentPage - delta);
      i <= Math.min(totalPages - 1, currentPage + delta);
      i++
    ) {
      range.push(i);
    }

    const pages: (number | string)[] = [1];
    if (currentPage - delta > 2) pages.push("...");
    pages.push(...range);
    if (currentPage + delta < totalPages - 1) pages.push("...");
    if (totalPages > 1 && !pages.includes(totalPages)) pages.push(totalPages);
    return pages;
  };

  return (
    <div className="flex flex-wrap justify-center items-center gap-1.5 mt-8 pb-10">
      <button
        type="button"
        onClick={() => onPageChange(Math.max(1, currentPage - 1))}
        disabled={currentPage === 1}
        className="px-3.5 py-2 rounded-xl bg-slate-800/80 border border-slate-700/70 text-slate-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-700 hover:text-white transition-all text-xs font-semibold shadow-sm"
      >
        Précédent
      </button>

      {getPageNumbers().map((p, idx) =>
        typeof p === "string" ? (
          <span key={idx} className="px-2 py-1 text-slate-500 text-xs select-none">
            •••
          </span>
        ) : (
          <button
            key={idx}
            type="button"
            onClick={() => onPageChange(p)}
            className={`min-w-[34px] h-[34px] px-2 rounded-xl text-xs font-semibold transition-all border shadow-sm ${
              currentPage === p
                ? "bg-blue-600 text-white border-blue-500 shadow-blue-500/20"
                : "bg-slate-800/80 text-slate-300 border-slate-700/60 hover:bg-slate-700 hover:text-white"
            }`}
          >
            {p}
          </button>
        )
      )}

      <button
        type="button"
        onClick={() => onPageChange(Math.min(totalPages, currentPage + 1))}
        disabled={currentPage === totalPages}
        className="px-3.5 py-2 rounded-xl bg-slate-800/80 border border-slate-700/70 text-slate-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-700 hover:text-white transition-all text-xs font-semibold shadow-sm"
      >
        Suivant
      </button>
    </div>
  );
});

export default OffersPagination;
