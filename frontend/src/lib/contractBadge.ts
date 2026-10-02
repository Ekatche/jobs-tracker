export interface ContractBadgeStyle {
  className: string;
  label: string;
}

export function getContractBadgeStyles(contract: string | null | undefined): ContractBadgeStyle | null {
  if (!contract || contract === "Non spécifié") {
    return null;
  }

  const c = contract.toLowerCase();

  if (c.includes("stage") || c.includes("intern")) {
    return {
      className: "bg-amber-500/15 text-amber-300 border-amber-500/35 font-semibold",
      label: "🎓 Stage",
    };
  }

  if (c.includes("alternance") || c.includes("apprentissage") || c.includes("apprenti")) {
    return {
      className: "bg-orange-500/15 text-orange-300 border-orange-500/35 font-semibold",
      label: "📚 Alternance",
    };
  }

  if (c.includes("cdi")) {
    return {
      className: "bg-emerald-500/15 text-emerald-300 border-emerald-500/35 font-semibold",
      label: "CDI",
    };
  }

  if (c.includes("cdd")) {
    return {
      className: "bg-sky-500/15 text-sky-300 border-sky-500/35 font-semibold",
      label: "CDD",
    };
  }

  if (c.includes("freelance") || c.includes("prestation") || c.includes("indépendant")) {
    return {
      className: "bg-purple-500/15 text-purple-300 border-purple-500/35 font-semibold",
      label: "Freelance",
    };
  }

  return {
    className: "bg-slate-800 text-slate-300 border-slate-700/60 font-medium",
    label: contract,
  };
}
