import React from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { Application } from '@/types/application';
import { statusColors } from './utils/constants';
import { processStatusData } from './utils/dataProcessors';

interface StatusChartProps {
  applications: Application[];
}

export default function StatusChart({ applications }: StatusChartProps) {
  const statusData = processStatusData(applications, statusColors);

  return (
    <div className="bg-blue-night-lighter rounded-lg shadow-lg p-6">
      <div className="flex items-center space-x-2 mb-6">
        <svg className="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 3.055A9.001 9.001 9.001 0 1020.945 13H11V3.055z"></path>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z"></path>
        </svg>
        <h2 className="text-xl font-semibold">Répartition par statut</h2>
      </div>
      
      <div className="h-64 mb-6">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={statusData}
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={80}
              paddingAngle={2}
              dataKey="value"
              labelLine={false}
            >
              {statusData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip 
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  const data = payload[0].payload;
                  return (
                    <div className="bg-blue-night-light p-2 rounded border border-gray-700 shadow-lg">
                      <p className="font-semibold text-white">{data.name}</p>
                      <p className="text-sm text-gray-300">
                        {data.value} candidature{data.value > 1 ? 's' : ''}
                        <span className="ml-1 text-gray-400">
                          ({((data.value / applications.length) * 100).toFixed(1)}%)
                        </span>
                      </p>
                    </div>
                  );
                }
                return null;
              }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>

      <div className="text-center mb-6">
        <div className="text-4xl font-bold">{applications.length}</div>
        <div className="text-sm text-gray-400">Candidatures actives</div>
      </div>

      {/* Légende avec pourcentages */}
      <div className="grid grid-cols-2 gap-2">
        {statusData.map((status, index) => {
          const percentage = applications.length > 0 
            ? ((status.value / applications.length) * 100).toFixed(1) 
            : '0';
          
          return (
            <div key={index} className="flex items-center space-x-2">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: status.color }}></div>
              <span className="text-sm">
                {status.name} ({status.value} - {percentage}%)
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}