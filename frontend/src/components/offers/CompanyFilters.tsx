import React, { useId } from "react";
import { SECTOR_OPTIONS, COMPANY_SIZE_OPTIONS } from "@/lib/companyTaxonomy";

interface CompanyFiltersProps {
  sectorValues: string[];
  onSectorChange: (values: string[]) => void;
  companySizeValues: string[];
  onCompanySizeChange: (values: string[]) => void;
}

/**
 * Cases à cocher groupées pour les filtres Secteur et Taille d'entreprise.
 *
 * Remplace les anciens `<select multiple>` (inaccessibles au clavier et peu
 * lisibles) par des `fieldset`/`legend` avec une case par option, chacune
 * reliée à son label via `htmlFor`/`id`. Le state (tableaux de valeurs) et sa
 * mise à jour restent gérés par le parent : ce composant ne fait que projeter
 * les valeurs cochées vers les mêmes callbacks de setter.
 */
export default function CompanyFilters({
  sectorValues,
  onSectorChange,
  companySizeValues,
  onCompanySizeChange,
}: CompanyFiltersProps) {
  const sectorIdBase = useId();
  const companySizeIdBase = useId();

  const toggleValue = (values: string[], value: string, checked: boolean): string[] =>
    checked ? [...values, value] : values.filter((v) => v !== value);

  return (
    <>
      <div>
        <fieldset>
          <legend className="block font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
            Secteur
          </legend>
          <div className="w-full max-h-40 overflow-y-auto px-3 py-2 bg-slate-800/80 border border-slate-700/80 rounded-xl space-y-1.5">
            {SECTOR_OPTIONS.map((sector) => {
              const inputId = `${sectorIdBase}-${sector.value}`;
              return (
                <div key={sector.value} className="flex items-center gap-2">
                  <input
                    id={inputId}
                    type="checkbox"
                    checked={sectorValues.includes(sector.value)}
                    onChange={(e) =>
                      onSectorChange(toggleValue(sectorValues, sector.value, e.target.checked))
                    }
                    className="w-4 h-4 rounded border-slate-600 bg-slate-800 text-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                  />
                  <label htmlFor={inputId} className="text-sm text-white cursor-pointer">
                    {sector.label}
                  </label>
                </div>
              );
            })}
          </div>
        </fieldset>
      </div>

      <div>
        <fieldset>
          <legend className="block font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
            Taille d&apos;entreprise
          </legend>
          <div className="w-full max-h-40 overflow-y-auto px-3 py-2 bg-slate-800/80 border border-slate-700/80 rounded-xl space-y-1.5">
            {COMPANY_SIZE_OPTIONS.map((size) => {
              const inputId = `${companySizeIdBase}-${size.value}`;
              return (
                <div key={size.value} className="flex items-center gap-2">
                  <input
                    id={inputId}
                    type="checkbox"
                    checked={companySizeValues.includes(size.value)}
                    onChange={(e) =>
                      onCompanySizeChange(
                        toggleValue(companySizeValues, size.value, e.target.checked)
                      )
                    }
                    className="w-4 h-4 rounded border-slate-600 bg-slate-800 text-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                  />
                  <label htmlFor={inputId} className="text-sm text-white cursor-pointer">
                    {size.label}
                  </label>
                </div>
              );
            })}
          </div>
        </fieldset>
      </div>
    </>
  );
}
