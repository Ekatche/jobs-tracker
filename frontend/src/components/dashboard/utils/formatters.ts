export function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return new Intl.DateTimeFormat('fr-FR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  }).format(date);
}

export function getDaysSinceApplication(dateString: string): string {
  const applicationDate = new Date(dateString);
  const now = new Date();
  const diffTime = Math.abs(now.getTime() - applicationDate.getTime());
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  
  return diffDays === 1 ? "1 jour" : `${diffDays} jours`;
}