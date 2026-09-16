import React from "react";
import { getStatusColor, STATUS_ORDER } from "@/types/application";
import { FiChevronDown } from "react-icons/fi";

interface StatusSelectProps {
  currentStatus: string;
  onChange: (newStatus: string) => void;
  className?: string;
}

export default function StatusSelect({
  currentStatus,
  onChange,
  className = "",
}: StatusSelectProps) {
  return (
    <div className={`relative inline-block w-full ${className}`}>
      <select
        value={currentStatus}
        onChange={(e) => onChange(e.target.value)}
        className={`w-full appearance-none ${getStatusColor(
          currentStatus
        )} px-3.5 py-2 pr-9 rounded-lg text-white font-medium text-sm bg-opacity-80 hover:bg-opacity-95 focus:outline-none focus:ring-2 focus:ring-blue-500/50 cursor-pointer border border-white/10 shadow-sm transition-all`}
      >
        {STATUS_ORDER.map((status) => (
          <option key={status} value={status} className="bg-slate-900 text-white py-1">
            {status}
          </option>
        ))}
      </select>
      <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2.5 text-white/70">
        <FiChevronDown className="w-4 h-4" />
      </div>
    </div>
  );
}

