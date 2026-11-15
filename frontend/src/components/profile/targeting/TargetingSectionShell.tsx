"use client";

import React from "react";
import { FiChevronDown } from "react-icons/fi";

interface TargetingSectionShellProps {
  icon: React.ReactNode;
  iconBoxClassName: string;
  title: string;
  subtitle: string;
  isOpen: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}

/**
 * Collapsible card container used across targeting preference sections.
 */
export function TargetingSectionShell({
  icon,
  iconBoxClassName,
  title,
  subtitle,
  isOpen,
  onToggle,
  children,
}: TargetingSectionShellProps) {
  return (
    <div className="bg-slate-900/70 border border-slate-800 backdrop-blur-md rounded-2xl p-6 shadow-xl space-y-6">
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-center justify-between gap-3 border-b border-slate-800/80 pb-4 text-left cursor-pointer"
      >
        <div className="flex items-center gap-3">
          <div className={`p-2.5 border rounded-xl ${iconBoxClassName}`}>
            {icon}
          </div>
          <div>
            <h3 className="text-base font-bold text-white">{title}</h3>
            <p className="text-xs text-slate-400">{subtitle}</p>
          </div>
        </div>
        <FiChevronDown
          className={`w-4 h-4 text-slate-500 shrink-0 transition-transform ${
            isOpen ? "rotate-180" : ""
          }`}
        />
      </button>

      {isOpen && children}
    </div>
  );
}
