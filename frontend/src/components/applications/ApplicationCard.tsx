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
}

export default function ApplicationCard({ 
  application, 
  status, 
  onClick 
}: ApplicationCardProps) {
    // * modele pour afficher les  candidature dans la kaban, les petits carrés du kanban *//

  return (
    <div 
      className={`${getStatusBackgroundColor(status)} rounded-md p-4 cursor-pointer hover:bg-opacity-80 transition-all`}
      onClick={() => onClick(application)}
    >
      <div className="flex items-center mb-2">
        <div className="w-8 h-8 rounded-full bg-gray-600 flex items-center justify-center mr-2">
          {application.company.charAt(0)}
        </div>
        <div>
          <h3 className="font-semibold">{application.position}</h3>
          <p className="text-sm text-gray-300">{application.company}</p>
        </div>
      </div>
      <div className="mb-2">
        <div className="flex items-center justify-between mb-1">
          <span className="text-sm">{calculateProgress(application.status)} %</span>
        </div>
        <div className="w-full bg-gray-700 rounded-full h-1.5">
          <div 
            className="bg-green-500 h-1.5 rounded-full" 
            style={{ width: `${calculateProgress(application.status)}%` }}
          ></div>
        </div>
      </div>
      <div className="text-sm text-gray-400">{calculateDays(application.application_date)} jours</div>
    </div>
  );
}