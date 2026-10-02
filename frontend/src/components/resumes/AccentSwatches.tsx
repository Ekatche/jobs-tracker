"use client";

import { CV_ACCENTS, type CvAccentKey } from "@/lib/cvTemplates";

interface AccentSwatchesProps {
  value: CvAccentKey;
  onChange: (accent: CvAccentKey) => void;
  disabled?: boolean;
}

export default function AccentSwatches({ value, onChange, disabled = false }: AccentSwatchesProps) {
  return (
    <div className="flex items-center gap-1.5" role="group" aria-label="Couleur d'accent">
      {CV_ACCENTS.map((accent) => {
        const selected = accent.key === value;
        return (
          <button
            key={accent.key}
            type="button"
            onClick={() => onChange(accent.key)}
            disabled={disabled}
            aria-label={accent.label}
            aria-pressed={selected}
            title={accent.label}
            style={{ backgroundColor: accent.primary }}
            className={`w-5 h-5 rounded-full border transition-all disabled:opacity-50 ${
              selected
                ? "border-white ring-2 ring-white ring-offset-2 ring-offset-[#152238]"
                : "border-white/20 hover:scale-110"
            }`}
          />
        );
      })}
    </div>
  );
}
