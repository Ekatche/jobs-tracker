"use client";

import { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { userApi } from "@/lib/api";
import { FiEdit, FiUser, FiSave } from "react-icons/fi";
import AccountPasswordSection from "./AccountPasswordSection";

export interface ProfileUser {
  _id: string;
  username: string;
  email: string;
  full_name?: string;
  created_at: string;
  updated_at?: string;
}

const profileSchema = z.object({
  username: z
    .string()
    .min(3, "Le nom d'utilisateur doit contenir au moins 3 caractères")
    .max(50, "Le nom d'utilisateur ne peut pas dépasser 50 caractères"),
  email: z.string().email("Adresse email invalide"),
  full_name: z.string().optional(),
});

type ProfileFormData = z.infer<typeof profileSchema>;

export default function AccountSecurityTab({
  user,
  onUserUpdated,
}: {
  user: ProfileUser | null;
  onUserUpdated: (user: ProfileUser) => void;
}) {
  const [updateSuccess, setUpdateSuccess] = useState(false);
  const [updateError, setUpdateError] = useState<string | null>(null);
  const [isEditingProfile, setIsEditingProfile] = useState(false);

  const {
    register: registerProfile,
    handleSubmit: handleSubmitProfile,
    reset: resetProfile,
    formState: { errors: profileErrors, isSubmitting: profileSubmitting },
  } = useForm<ProfileFormData>({
    resolver: zodResolver(profileSchema),
    defaultValues: { username: "", email: "", full_name: "" },
  });

  useEffect(() => {
    if (user) {
      resetProfile({
        username: user.username,
        email: user.email,
        full_name: user.full_name || "",
      });
    }
  }, [user, resetProfile]);

  const onSubmitProfile = async (data: ProfileFormData) => {
    setUpdateError(null);
    setUpdateSuccess(false);
    try {
      if (!user?._id) return;
      await userApi.update(user._id, data);
      onUserUpdated({ ...user, ...data });
      setUpdateSuccess(true);
      setIsEditingProfile(false);
      setTimeout(() => setUpdateSuccess(false), 3000);
    } catch (error) {
      console.error("Erreur lors de la mise à jour du profil", error);
      setUpdateError(
        error instanceof Error
          ? error.message || "Une erreur est survenue lors de la mise à jour du profil"
          : "Une erreur est survenue lors de la mise à jour du profil"
      );
    }
  };

  return (
    <div className="animate-in fade-in duration-200 space-y-8">
      <div className="bg-blue-night-lighter rounded-lg shadow-lg p-6 mb-8">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-semibold text-white flex items-center">
            <FiUser className="mr-2" /> Informations personnelles
          </h2>
          <button
            type="button"
            onClick={() => setIsEditingProfile(!isEditingProfile)}
            className="flex items-center text-blue-400 hover:text-blue-300 transition-colors"
          >
            <FiEdit className="mr-1" />
            {isEditingProfile ? "Annuler" : "Modifier"}
          </button>
        </div>

        {updateSuccess && (
          <div className="bg-green-900/40 border border-green-600 text-green-200 p-3 rounded-md mb-4">
            Profil mis à jour avec succès
          </div>
        )}

        {updateError && (
          <div className="bg-red-900/40 border border-red-600 text-red-200 p-3 rounded-md mb-4">
            {updateError}
          </div>
        )}

        {isEditingProfile ? (
          <form onSubmit={handleSubmitProfile(onSubmitProfile)} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label htmlFor="username" className="block text-sm font-medium text-gray-300 mb-1">
                  Nom d&apos;utilisateur
                </label>
                <input
                  id="username"
                  type="text"
                  {...registerProfile("username")}
                  className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                {profileErrors.username && (
                  <p className="mt-1 text-sm text-red-400">{profileErrors.username.message}</p>
                )}
              </div>

              <div>
                <label htmlFor="email" className="block text-sm font-medium text-gray-300 mb-1">
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  {...registerProfile("email")}
                  className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                {profileErrors.email && (
                  <p className="mt-1 text-sm text-red-400">{profileErrors.email.message}</p>
                )}
              </div>

              <div className="md:col-span-2">
                <label htmlFor="full_name" className="block text-sm font-medium text-gray-300 mb-1">
                  Nom complet
                </label>
                <input
                  id="full_name"
                  type="text"
                  {...registerProfile("full_name")}
                  className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                {profileErrors.full_name && (
                  <p className="mt-1 text-sm text-red-400">{profileErrors.full_name.message}</p>
                )}
              </div>
            </div>

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={profileSubmitting}
                className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-500 transition-colors disabled:opacity-70"
              >
                <FiSave className="mr-2" />
                {profileSubmitting ? "Enregistrement..." : "Enregistrer"}
              </button>
            </div>
          </form>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <p className="text-sm font-medium text-gray-400">Nom d&apos;utilisateur</p>
              <p className="text-white">{user?.username}</p>
            </div>
            <div>
              <p className="text-sm font-medium text-gray-400">Email</p>
              <p className="text-white">{user?.email}</p>
            </div>
            <div className="md:col-span-2">
              <p className="text-sm font-medium text-gray-400">Nom complet</p>
              <p className="text-white">{user?.full_name || "Non spécifié"}</p>
            </div>
          </div>
        )}
      </div>

      <AccountPasswordSection />
    </div>
  );
}
