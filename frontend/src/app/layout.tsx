"use client";

import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Header from '@/components/layout/Header';
import { NotificationProvider } from '@/contexts/NotificationContext';
import { useEffect } from 'react';
import { setupTokenRefresh } from '@/lib/api';
import { isAuthenticated } from '@/lib/auth';
import { startActivityTracking } from '@/lib/activityTracker';

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {

  useEffect(() => {
    // Vérifier si l'utilisateur est authentifié
    if (isAuthenticated()) {
      // Configurer le rafraîchissement de token
      setupTokenRefresh();
      
      // Activer le suivi d'activité
      const cleanupTracker = startActivityTracking();
      
      // Nettoyer le tracker lors du démontage
      return cleanupTracker;
    }
  }, []);

  return (
    <html lang="fr" className="h-full">
      <body className={`${geistSans.variable} ${geistMono.variable} bg-blue-night text-white h-full flex flex-col`}>
        <NotificationProvider>
          <Header />
          <main className="flex-grow overflow-auto">
            {children}
          </main>
        </NotificationProvider>
      </body>
    </html>
  );
}
