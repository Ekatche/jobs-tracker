"use client";

import React, { useState } from "react";
import { FiChevronDown } from "react-icons/fi";

interface CollapsibleSectionProps {
  title: React.ReactNode;
  icon?: React.ReactNode;
  defaultOpen?: boolean;
  badge?: React.ReactNode;
  children: React.ReactNode;
}

/**
 * Reusable expandable card wrapper for candidate profile view sections.
 */
export function CollapsibleSection({
  title,
  icon,
  defaultOpen = false,
  badge,
  children,
}: CollapsibleSectionProps) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="bg-slate-950/40 rounded-xl border border-slate-800/80">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between gap-2 p-5 text-left"
      >
        <h3 className="text-xs uppercase tracking-wider font-semibold text-slate-400 flex items-center">
          {icon}
          {title}
        </h3>
        <div className="flex items-center gap-2 shrink-0">
          {badge}
          <FiChevronDown
            className={`w-4 h-4 text-slate-500 transition-transform ${open ? "rotate-180" : ""}`}
          />
        </div>
      </button>
      {open && <div className="px-5 pb-5 -mt-1.5">{children}</div>}
    </div>
  );
}
