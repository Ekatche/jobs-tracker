"use client";

import React from 'react';

interface GradientBackgroundProps {
  children: React.ReactNode;
}

export default function GradientBackground({ children }: GradientBackgroundProps) {
  return (
    <div className="min-h-screen relative overflow-hidden">
      {/* Fond avec dégradé */}
      <div 
        className="absolute inset-0 z-0" 
        style={{ 
          background: "linear-gradient(45deg, #1e3c72 0%, #2a5298 50%, #7303c0 100%)",
        }}
      />
      
      {/* Cercles décoratifs */}
      <div className="absolute -top-24 -right-24 w-96 h-96 rounded-full bg-blue-500 opacity-20 blur-3xl"></div>
      <div className="absolute top-1/3 -left-24 w-80 h-80 rounded-full bg-indigo-600 opacity-20 blur-3xl"></div>
      <div className="absolute bottom-0 right-1/3 w-80 h-80 rounded-full bg-purple-600 opacity-10 blur-3xl"></div>
      
      {/* Contenu */}
      <div className="relative z-10">
        {children}
      </div>
    </div>
  );
}