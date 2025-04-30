import React from 'react';
import { Application, getStatusColor } from '@/types/application'
;
import ApplicationCard from './ApplicationCard';

interface KanbanColumnProps {
  status: string;
  applications: Application[];
  onCardClick: (application: Application) => void;
}

export default function KanbanColumn({ 
  status, 
  applications, 
  onCardClick 
}: KanbanColumnProps) {
  return (
    <div className="flex flex-col">
      <div className={`${getStatusColor(status)} rounded-md px-3 py-2 mb-4 text-white font-medium`}>
        {status}
      </div>
      <div className="space-y-4 max-h-[calc(100vh-180px)] overflow-y-auto pr-1">
        {applications?.map(app => (
          <ApplicationCard 
            key={app._id} 
            application={app} 
            status={status} 
            onClick={onCardClick}
          />
        ))}
        {!applications || applications.length === 0 && (
          <div className="text-gray-400 text-center p-4">
            Aucune candidature
          </div>
        )}
      </div>
    </div>
  );
}