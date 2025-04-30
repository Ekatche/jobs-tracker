import React from 'react';
import { 
  Application, 
  getStatusBackgroundColor, 
  calculateProgress, 
  calculateDays 
} from '@/types/application'

interface ApplicationCardProps {
  application: Application;
  status: string;
  onClick: (application: Application) => void;
  compact?: boolean; 
}

export default function ApplicationCard({ 
  application, 
  status, 
  onClick,
  compact = false
}: ApplicationCardProps) {
  return (
    <div 
      className={`${getStatusBackgroundColor(status)} rounded-md ${compact ? 'p-2' : 'p-4'} cursor-pointer hover:bg-opacity-80 transition-all`}
      onClick={() => onClick(application)}
    >
      <div className="flex items-center mb-1">
        {!compact && (
          <div className="w-8 h-8 rounded-full bg-gray-600 flex items-center justify-center mr-2">
            {application.company.charAt(0)}
          </div>
        )}
        <div className="overflow-hidden">
          <h3 className="font-semibold text-sm whitespace-nowrap overflow-hidden text-ellipsis">
            {application.position}
          </h3>
          <p className="text-xs text-gray-300 whitespace-nowrap overflow-hidden text-ellipsis">
            {application.company}
          </p>
        </div>
      </div>
      
      <div className={`${compact ? 'mb-1' : 'mb-2'}`}>
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs">{calculateProgress(application.status)} %</span>
        </div>
        <div className="w-full bg-gray-700 rounded-full h-1">
          <div 
            className="bg-green-500 h-1 rounded-full" 
            style={{ width: `${calculateProgress(application.status)}%` }}
          ></div>
        </div>
      </div>
      
      <div className="text-xs text-gray-400">{calculateDays(application.application_date)} j</div>
    </div>
  );
}