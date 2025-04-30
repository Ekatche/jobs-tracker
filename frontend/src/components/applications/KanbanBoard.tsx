import React from 'react';
import { Application, GroupedApplications, STATUS_ORDER } from '@/types/application';
import KanbanColumn from './KanbanColumn';

interface KanbanBoardProps {
  groupedApplications: GroupedApplications;
  onCardClick: (application: Application) => void;
}

export default function KanbanBoard({ 
  groupedApplications, 
  onCardClick 
}: KanbanBoardProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-6 gap-4"> 
      {STATUS_ORDER.map(status => (
        <KanbanColumn
          key={status}
          status={status}
          applications={groupedApplications[status] || []}
          onCardClick={onCardClick}
        />
      ))}
    </div>
  );
}