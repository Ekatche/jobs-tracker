import React from 'react';
import { getStatusColor } from '@/types/application'


interface StatusSelectProps {
  currentStatus: string;
  onChange: (newStatus: string) => void;
}

export default function StatusSelect({ currentStatus, onChange }: StatusSelectProps) {
  return (
    <select
      value={currentStatus}
      onChange={(e) => onChange(e.target.value)}
      className={`${getStatusColor(currentStatus)} px-3 py-1 rounded-md text-white font-medium bg-opacity-80 cursor-pointer`}
    >
      <option value="Candidature envoyée">Candidature envoyée</option>
      <option value="Entretien">Entretien</option>
      <option value="Offre reçue">Offre reçue</option>
      <option value="Refusée">Refusée</option>
    </select>
  );
}