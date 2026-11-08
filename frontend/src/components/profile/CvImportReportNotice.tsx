"use client";

import React from "react";
import { FiAlertTriangle, FiX } from "react-icons/fi";
import { CvImportReport } from "@/types/coverLetter";

/** Vrai si l'import comporte une limite à signaler (pages omises, repli texte, erreurs). */
export function hasImportLimits(report?: CvImportReport | null): report is CvImportReport {
  return (
    !!report &&
    (report.skipped_pages.length > 0 || report.fallback_used || report.errors.length > 0)
  );
}

interface CvImportReportNoticeProps {
  report: CvImportReport;
  onDismiss: () => void;
}

export default function CvImportReportNotice({ report, onDismiss }: CvImportReportNoticeProps) {
  const processed = report.total_pages - report.skipped_pages.length;
  const pluriel = report.skipped_pages.length > 1 ? "s" : "";

  return (
    <div
      role="alert"
      className="mt-4 p-3.5 rounded-xl bg-amber-950/50 border border-amber-600/40 text-amber-100 text-xs flex items-start gap-2.5 shadow-md"
    >
      <FiAlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
      <div className="flex-1 space-y-1.5">
        <p className="font-semibold">
          CV importé partiellement : {processed} page(s) analysée(s) sur {report.total_pages}.
        </p>
        {report.skipped_pages.length > 0 && (
          <p>
            Page{pluriel} non traitée{pluriel} : {report.skipped_pages.join(", ")}. Leur contenu
            n&apos;est pas dans votre profil.
          </p>
        )}
        {report.fallback_used && (
          <p>
            L&apos;analyse visuelle n&apos;a pas pu être utilisée : le texte extrait du PDF a servi à
            la place, la mise en page peut être moins fidèle.
          </p>
        )}
        {report.errors.length > 0 && (
          <ul className="list-disc pl-4">
            {report.errors.map((message) => (
              <li key={message}>{message}</li>
            ))}
          </ul>
        )}
        <p>
          Vérifiez et corrigez vos expériences et compétences dans la section d&apos;édition du profil
          ci-dessous.
        </p>
      </div>
      <button
        type="button"
        onClick={onDismiss}
        aria-label="Fermer l'avertissement"
        className="text-amber-300 hover:text-white shrink-0"
      >
        <FiX className="w-4 h-4" />
      </button>
    </div>
  );
}
