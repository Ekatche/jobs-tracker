"use client";

import { FiTarget, FiFileText, FiCompass, FiCheck } from "react-icons/fi";

interface OnboardingStepperProps {
  currentStep: 1 | 2 | 3;
  onSelectStep: (step: 1 | 2 | 3) => void;
}

const STEPS: Array<{ step: 1 | 2 | 3; label: string; Icon: typeof FiTarget }> = [
  { step: 1, label: "1. Ciblage", Icon: FiTarget },
  { step: 2, label: "2. CV & Parcours", Icon: FiFileText },
  { step: 3, label: "3. Web & Lancement", Icon: FiCompass },
];

export default function OnboardingStepper({
  currentStep,
  onSelectStep,
}: OnboardingStepperProps) {
  return (
    <div className="bg-blue-night-lighter/60 border border-gray-800 rounded-xl p-4 sm:p-6 mb-8 backdrop-blur-sm shadow-xl">
      <div className="flex items-center justify-between relative">
        <div className="absolute left-0 top-1/2 -translate-y-1/2 w-full h-1 bg-gray-800 -z-0" />
        <div
          className="absolute left-0 top-1/2 -translate-y-1/2 h-1 bg-gradient-to-r from-blue-500 to-indigo-500 transition-all duration-500 -z-0"
          style={{
            width: currentStep === 1 ? "0%" : currentStep === 2 ? "50%" : "100%",
          }}
        />

        {STEPS.map(({ step, label, Icon }) => {
          const isCurrent = currentStep === step;
          const isDone = currentStep > step;
          return (
            <button
              key={step}
              onClick={() => onSelectStep(step)}
              className="flex flex-col items-center z-10 group focus:outline-none"
            >
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-sm transition-all duration-300 ${
                  isCurrent
                    ? "bg-blue-600 text-white ring-4 ring-blue-500/20 shadow-lg shadow-blue-500/30"
                    : isDone
                    ? "bg-emerald-600 text-white"
                    : "bg-gray-800 text-gray-400 border border-gray-700"
                }`}
              >
                {isDone ? <FiCheck className="text-lg" /> : <Icon className="text-lg" />}
              </div>
              <span
                className={`mt-2 text-xs font-semibold tracking-wide ${
                  isCurrent ? "text-blue-400" : "text-gray-400"
                }`}
              >
                {label}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
