"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { authApi } from "@/lib/api";
import { FiEdit, FiSave, FiKey } from "react-icons/fi";

const passwordSchema = z
  .object({
    current_password: z.string().min(1, "Le mot de passe actuel est requis"),
    new_password: z
      .string()
      .min(8, "Le nouveau mot de passe doit contenir au moins 8 caractères"),
    confirm_password: z.string().min(1, "La confirmation du mot de passe est requise"),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: "Les mots de passe ne correspondent pas",
    path: ["confirm_password"],
  });

type PasswordFormData = z.infer<typeof passwordSchema>;

export default function AccountPasswordSection() {
  const [passwordSuccess, setPasswordSuccess] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [isChangingPassword, setIsChangingPassword] = useState(false);

  const {
    register: registerPassword,
    handleSubmit: handleSubmitPassword,
    reset: resetPassword,
    formState: { errors: passwordErrors, isSubmitting: passwordSubmitting },
  } = useForm<PasswordFormData>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { current_password: "", new_password: "", confirm_password: "" },
  });

  const onSubmitPassword = async (data: PasswordFormData) => {
    setPasswordError(null);
    setPasswordSuccess(false);
    try {
      await authApi.changePassword(data.current_password, data.new_password);
      setPasswordSuccess(true);
      resetPassword();
      setIsChangingPassword(false);
      setTimeout(() => setPasswordSuccess(false), 3000);
    } catch (error) {
      console.error("Erreur lors du changement de mot de passe", error);
      setPasswordError(
        error instanceof Error
          ? error.message || "Une erreur est survenue lors du changement de mot de passe"
          : "Une erreur est survenue lors du changement de mot de passe"
      );
    }
  };

  return (
    <div className="bg-blue-night-lighter rounded-lg shadow-lg p-6">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-xl font-semibold text-white flex items-center">
          <FiKey className="mr-2" /> Sécurité
        </h2>
        <button
          type="button"
          onClick={() => setIsChangingPassword(!isChangingPassword)}
          className="flex items-center text-blue-400 hover:text-blue-300 transition-colors"
        >
          <FiEdit className="mr-1" />
          {isChangingPassword ? "Annuler" : "Changer le mot de passe"}
        </button>
      </div>

      {passwordSuccess && (
        <div className="bg-green-900/40 border border-green-600 text-green-200 p-3 rounded-md mb-4">
          Mot de passe modifié avec succès
        </div>
      )}

      {passwordError && (
        <div className="bg-red-900/40 border border-red-600 text-red-200 p-3 rounded-md mb-4">
          {passwordError}
        </div>
      )}

      {isChangingPassword && (
        <form onSubmit={handleSubmitPassword(onSubmitPassword)} className="space-y-4">
          <div>
            <label
              htmlFor="current_password"
              className="block text-sm font-medium text-gray-300 mb-1"
            >
              Mot de passe actuel
            </label>
            <input
              id="current_password"
              type="password"
              {...registerPassword("current_password")}
              className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            {passwordErrors.current_password && (
              <p className="mt-1 text-sm text-red-400">
                {passwordErrors.current_password.message}
              </p>
            )}
          </div>

          <div>
            <label
              htmlFor="new_password"
              className="block text-sm font-medium text-gray-300 mb-1"
            >
              Nouveau mot de passe
            </label>
            <input
              id="new_password"
              type="password"
              {...registerPassword("new_password")}
              className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            {passwordErrors.new_password && (
              <p className="mt-1 text-sm text-red-400">{passwordErrors.new_password.message}</p>
            )}
          </div>

          <div>
            <label
              htmlFor="confirm_password"
              className="block text-sm font-medium text-gray-300 mb-1"
            >
              Confirmer le nouveau mot de passe
            </label>
            <input
              id="confirm_password"
              type="password"
              {...registerPassword("confirm_password")}
              className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            {passwordErrors.confirm_password && (
              <p className="mt-1 text-sm text-red-400">
                {passwordErrors.confirm_password.message}
              </p>
            )}
          </div>

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={passwordSubmitting}
              className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-500 transition-colors disabled:opacity-70"
            >
              <FiSave className="mr-2" />
              {passwordSubmitting ? "Enregistrement..." : "Changer le mot de passe"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
