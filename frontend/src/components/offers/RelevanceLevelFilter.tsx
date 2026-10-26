import React, { useId } from "react";
import { RELEVANCE_LEVEL_OPTIONS } from "@/lib/relevanceLevels";

interface RelevanceLevelFilterProps {
  values: string[];
  onChange: (values: string[]) => void;
}

/**
 * Cases à cocher du filtre par niveau de pertinence, sur le même modèle
 * accessible que `CompanyFilters` (`fieldset`/`legend`, une case par niveau).
 * Plusieurs niveaux cochés se combinent en union côté API.
 */
export default function RelevanceLevelFilter({ values, onChange }: RelevanceLevelFilterProps) {
  const idBase = useId();

  return (
    <div>
      <fieldset>
        <legend className="block font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
          Pertinence
        </legend>
        <div className="w-full px-3 py-2 bg-slate-800/80 border border-slate-700/80 rounded-xl space-y-1.5">
          {RELEVANCE_LEVEL_OPTIONS.map((level) => {
            const inputId = `${idBase}-${level.value}`;
            return (
              <div key={level.value} className="flex items-center gap-2">
                <input
                  id={inputId}
                  type="checkbox"
                  checked={values.includes(level.value)}
                  onChange={(e) =>
                    onChange(
                      e.target.checked
                        ? [...values, level.value]
                        : values.filter((v) => v !== level.value)
                    )
                  }
                  className="w-4 h-4 rounded border-slate-600 bg-slate-800 text-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                />
                <label htmlFor={inputId} className="text-sm text-white cursor-pointer">
                  {level.label}
                </label>
              </div>
            );
          })}
        </div>
      </fieldset>
    </div>
  );
}
