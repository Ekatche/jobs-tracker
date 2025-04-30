import React from 'react';
import { getStatusColor, STATUS_ORDER } from '@/types/application'

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
      {STATUS_ORDER.map(status => (
        <option key={status} value={status}>
          {status}
        </option>
      ))}
    </select>
  );
}