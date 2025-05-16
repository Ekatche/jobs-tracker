import { statusColors } from "./constants";

export function getStatusColor(status: string): string {
  const baseColor = statusColors[status] || "#CCCCCC";
  return baseColor.replace("#", "bg-[#") + "]";
}

export function getLocationColor(location: string): string {
  if (!location || location.trim() === "") return "bg-gray-500";

  const lowerLocation = location.toLowerCase();

  if (
    lowerLocation.includes("remote") ||
    lowerLocation.includes("télétravail")
  ) {
    return "bg-green-600";
  } else if (
    lowerLocation.includes("france") ||
    lowerLocation.includes("paris")
  ) {
    return "bg-blue-600";
  } else if (
    lowerLocation.includes("lyon") ||
    lowerLocation.includes("marseille") ||
    lowerLocation.includes("bordeaux") ||
    lowerLocation.includes("lille") ||
    lowerLocation.includes("toulouse") ||
    lowerLocation.includes("nantes") ||
    lowerLocation.includes("strasbourg")
  ) {
    return "bg-indigo-600";
  } else if (lowerLocation.includes("étranger")) {
    return "bg-violet-600";
  } else {
    return "bg-purple-600";
  }
}
