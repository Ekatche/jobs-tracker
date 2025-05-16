"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getToken } from "@/lib/auth";
import { authApi } from "@/lib/api";

export default function ApplicationsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    const checkAuth = async () => {
      const token = getToken();

      if (!token) {
        router.push("/auth/login");
        return;
      }

      try {
        // Vérifier si l'utilisateur est authentifié
        const userData = await authApi.getCurrentUser();
        if (userData) {
          setAuthenticated(true);
          setLoading(false);
        } else {
          router.push("/auth/login");
        }
      } catch (error) {
        console.error("Erreur d'authentification:", error);
        router.push("/auth/login");
      } finally {
        setLoading(false);
      }
    };

    checkAuth();
  }, [router]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-blue-night">
        <div className="animate-pulse text-blue-400 text-xl">Chargement...</div>
      </div>
    );
  }

  return authenticated ? children : null;
}
