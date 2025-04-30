import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Application } from '@/types/application';
import { processPositionData } from './utils/dataProcessors';

interface PositionChartProps {
  applications: Application[];
}

export default function PositionChart({ applications }: PositionChartProps) {
  const positionData = processPositionData(applications);

  return (
    <div className="bg-blue-night-lighter rounded-lg shadow-lg p-6">
      <div className="flex items-center space-x-2 mb-6">
        <svg className="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
        </svg>
        <h2 className="text-xl font-semibold">Types de postes</h2>
      </div>
      
      {/* Conteneur avec défilement */}
      <div className="h-80 overflow-y-auto pr-2 custom-scrollbar">
        <div style={{ height: `${Math.max(250, positionData.length * 40)}px` }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={positionData}
              layout="vertical"
              margin={{ top: 5, right: 30, left: 120, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#444" />
              <XAxis type="number" stroke="#888" />
              <YAxis 
                type="category" 
                dataKey="name" 
                stroke="#888" 
                width={120} 
                tick={{ fontSize: 12 }}
                tickFormatter={(value) => value.length > 18 ? `${value.substring(0, 18)}...` : value}
              />
              <Tooltip 
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const data = payload[0].payload;
                    return (
                      <div className="bg-blue-night-light p-2 rounded border border-gray-700 shadow-lg">
                        <p className="font-semibold text-white">{data.name}</p>
                        <p className="text-sm text-gray-300">
                          {data.value} candidature{data.value > 1 ? 's' : ''}
                        </p>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Bar dataKey="value" fill="#4A90E2" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="text-center mt-4">
        <div className="text-sm text-gray-400">Postes les plus fréquents</div>
        {positionData.length > 6 && (
          <p className="text-xs text-gray-500 mt-1">Faites défiler pour voir tous les types de postes</p>
        )}
      </div>
    </div>
  );
}