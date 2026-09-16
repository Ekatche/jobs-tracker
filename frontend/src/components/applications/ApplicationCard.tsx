import React from "react";
import {
  Application,
  getStatusBackgroundColor,
  calculateProgress,
  calculateDays,
} from "@/types/application";
import { FiAlertCircle, FiMail, FiLink } from "react-icons/fi";

interface ApplicationCardProps {
  application: Application;
  status: string;
  onClick: (application: Application) => void;
  compact?: boolean;
}

export default function ApplicationCard({
  application,
  status,
  onClick,
  compact = false,
}: ApplicationCardProps) {
  const days = application.days_since_application ?? calculateDays(application.application_date);
  const isRelanceDue = application.follow_up_alert === "relance_due" || (
    (application.status === "Candidature envoyée" || status === "Candidature envoyée") && days >= 7
  );
  const isRemerciementDue = application.follow_up_alert === "remerciement_due" || (
    (application.status === "Entretien" || status === "Entretien") && days >= 1
  );

  return (
    <div
      className={`${getStatusBackgroundColor(status)} rounded-md ${compact ? "p-2" : "p-4"} cursor-pointer hover:bg-opacity-80 transition-all border border-transparent hover:border-slate-600/50 shadow-sm`}
      onClick={() => onClick(application)}
    >
      <div className="flex items-center mb-1.5">
        {!compact && (
          <div className="w-8 h-8 rounded-full bg-slate-700/80 text-white font-bold text-xs flex items-center justify-center mr-2 shrink-0">
            {application.company.charAt(0)}
          </div>
        )}
        <div className="overflow-hidden min-w-0">
          <h3 className="font-semibold text-sm whitespace-nowrap overflow-hidden text-ellipsis text-white">
            {application.position}
          </h3>
          <p className="text-xs text-gray-300 whitespace-nowrap overflow-hidden text-ellipsis">
            {application.company}
          </p>
        </div>
      </div>

      {/* Cadence follow-up alerts */}
      {isRelanceDue && (
        <div className="mb-2 px-2 py-1 rounded text-[11px] font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30 flex items-center gap-1.5">
          <FiAlertCircle className="text-xs shrink-0" />
          <span className="truncate">Relance J+7 due ({days}j)</span>
        </div>
      )}

      {isRemerciementDue && (
        <div className="mb-2 px-2 py-1 rounded text-[11px] font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 flex items-center gap-1.5">
          <FiMail className="text-xs shrink-0" />
          <span className="truncate">Remerciement J+1</span>
        </div>
      )}

      <div className={`${compact ? "mb-1" : "mb-2"}`}>
        <div className="flex items-center justify-between mb-1">
          <span className="text-[11px] text-gray-300">
            {calculateProgress(application.status)} %
          </span>
          {application.offer_id && (
            <span className="text-[10px] text-blue-300 bg-blue-500/10 px-1.5 py-0.5 rounded border border-blue-500/20 flex items-center gap-1">
              <FiLink className="text-[10px]" />
              <span>Offre liée</span>
            </span>
          )}
        </div>
        <div className="w-full bg-gray-700/80 rounded-full h-1">
          <div
            className="bg-emerald-500 h-1 rounded-full transition-all"
            style={{ width: `${calculateProgress(application.status)}%` }}
          ></div>
        </div>
      </div>

      <div className="text-xs text-gray-400 flex items-center justify-between">
        <span>{days} j</span>
        {application.location && (
          <span className="text-[11px] text-gray-400 truncate max-w-[120px]">{application.location}</span>
        )}
      </div>
    </div>
  );
}
