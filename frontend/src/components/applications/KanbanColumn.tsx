import React from 'react';
import { Application, getStatusColor } from '@/types/application';
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
    <div className="flex flex-col h-full">
      <div className={`${getStatusColor(status)} rounded-md px-3 py-2 mb-2 text-white font-medium flex flex-col items-center`}>
        <span>{status}</span>
        <span className="text-xs bg-gray-700 px-2 py-0.5 rounded-full mt-1">{applications?.length || 0}</span>
      </div>
      <div className="space-y-2 flex-grow overflow-y-auto max-h-[calc(100vh-220px)] pr-1 custom-scrollbar">
        {applications?.map(app => (
          <ApplicationCard 
            key={app._id} 
            application={app} 
            status={status} 
            onClick={onCardClick}
            compact={false}
          />
        ))}
        {(!applications || applications.length === 0) && (
          <div className="text-gray-400 text-center p-4">
            Aucune candidature
          </div>
        )}
      </div>
    </div>
  );
}