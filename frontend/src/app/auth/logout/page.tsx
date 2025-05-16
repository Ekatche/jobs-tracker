"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { logout } from "@/lib/auth";

export default function LogoutPage() {
  const router = useRouter();

  useEffect(() => {
    const performLogout = async () => {
      try {
        await logout();
        // Redirection vers la page de connexion après déconnexion
        router.push("/auth/login");
      } catch (error) {
        console.error("Erreur lors de la déconnexion", error);
        router.push("/");
      }
    };

    performLogout();
  }, [router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="bg-white p-8 rounded-lg shadow-md w-full max-w-md text-center">
        <h2 className="text-2xl font-bold mb-4">Déconnexion en cours...</h2>
        <p className="text-gray-600">
          Vous allez être redirigé dans un instant.
        </p>
      </div>
    </div>
  );
}
