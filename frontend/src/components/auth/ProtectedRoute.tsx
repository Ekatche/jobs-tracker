"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getToken } from "@/lib/auth";
import { authApi, refreshAccessToken } from "@/lib/api";
import { jwtDecode } from "jwt-decode";

function isTokenExpired(token: string): boolean {
  try {
    const decoded = jwtDecode<{ exp: number }>(token);
    return decoded.exp <= Date.now() / 1000;
  } catch {
    return true;
  }
}

export default function ProtectedRoute({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    const checkAuth = async () => {
      let token = getToken();

      if (!token || isTokenExpired(token)) {
        const refreshed = await refreshAccessToken();
        if (!refreshed) {
          router.push("/auth/login");
          return;
        }
        token = getToken();
      }

      try {
        // Vérifier si l'utilisateur est authentifié
        const userData = await authApi.getCurrentUser();
        if (userData) {
          setAuthenticated(true);
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

  return authenticated ? <>{children}</> : null;
}
