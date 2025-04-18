'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { authApi, userApi } from '@/lib/api';
import { getToken } from '@/lib/auth';
import { FiEdit, FiUser, FiMail, FiSave, FiKey } from 'react-icons/fi';

// Ajoutez ceci après les imports et avant les schémas de validation
interface User {
  _id: string;
  username: string;
  email: string;
  full_name?: string;
  created_at: string;
  updated_at?: string;
}

// Schéma de validation pour la mise à jour du profil
const profileSchema = z.object({
  username: z.string().min(3, 'Le nom d\'utilisateur doit contenir au moins 3 caractères').max(50, 'Le nom d\'utilisateur ne peut pas dépasser 50 caractères'),
  email: z.string().email('Adresse email invalide'),
  full_name: z.string().optional(),
});

// Schéma pour le changement de mot de passe
const passwordSchema = z.object({
  current_password: z.string().min(1, 'Le mot de passe actuel est requis'),
  new_password: z.string().min(8, 'Le nouveau mot de passe doit contenir au moins 8 caractères'),
  confirm_password: z.string().min(1, 'La confirmation du mot de passe est requise')
}).refine((data) => data.new_password === data.confirm_password, {
  message: 'Les mots de passe ne correspondent pas',
  path: ['confirm_password'],
});

type ProfileFormData = z.infer<typeof profileSchema>;
type PasswordFormData = z.infer<typeof passwordSchema>;

export default function ProfilePage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [updateSuccess, setUpdateSuccess] = useState(false);
  const [updateError, setUpdateError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [isEditingProfile, setIsEditingProfile] = useState(false);
  const [isChangingPassword, setIsChangingPassword] = useState(false);

  // Form pour les informations de profil
  const { 
    register: registerProfile, 
    handleSubmit: handleSubmitProfile, 
    reset: resetProfile,
    formState: { errors: profileErrors, isSubmitting: profileSubmitting } 
  } = useForm<ProfileFormData>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      username: '',
      email: '',
      full_name: '',
    }
  });

  // Form pour le changement de mot de passe
  const { 
    register: registerPassword, 
    handleSubmit: handleSubmitPassword, 
    reset: resetPassword,
    formState: { errors: passwordErrors, isSubmitting: passwordSubmitting } 
  } = useForm<PasswordFormData>({
    resolver: zodResolver(passwordSchema),
    defaultValues: {
      current_password: '',
      new_password: '',
      confirm_password: '',
    }
  });

  // Récupérer les informations de l'utilisateur au chargement de la page
  useEffect(() => {
    const fetchUserProfile = async () => {
      setLoading(true);
      
      const token = getToken();
      if (!token) {
        router.push('/auth/login');
        return;
      }

      try {
        const userData = await authApi.getCurrentUser();
        if (userData) {
          setUser(userData);
          // Préremplir le formulaire avec les données de l'utilisateur
          resetProfile({
            username: userData.username,
            email: userData.email,
            full_name: userData.full_name || '',
          });
        } else {
          router.push('/auth/login');
        }
      } catch (error) {
        console.error('Erreur lors de la récupération du profil utilisateur', error);
        router.push('/auth/login');
      } finally {
        setLoading(false);
      }
    };

    fetchUserProfile();
  }, [router, resetProfile]);

  // Gérer la soumission du formulaire de profil
  const onSubmitProfile = async (data: ProfileFormData) => {
    setUpdateError(null);
    setUpdateSuccess(false);

    try {
      if (!user?._id) return;

      await userApi.update(user._id, data);
      
      // Mettre à jour l'utilisateur local
      setUser({
        ...user,
        ...data
      });
      
      setUpdateSuccess(true);
      setIsEditingProfile(false);
      
      // Masquer le message de succès après 3 secondes
      setTimeout(() => {
        setUpdateSuccess(false);
      }, 3000);
    } catch (error) {
      console.error('Erreur lors de la mise à jour du profil', error);
      if (error instanceof Error) {
        setUpdateError(error.message || 'Une erreur est survenue lors de la mise à jour du profil');
      } else {
        setUpdateError('Une erreur est survenue lors de la mise à jour du profil');
      }
    }
  };

  // Gérer la soumission du formulaire de changement de mot de passe
  const onSubmitPassword = async (data: PasswordFormData) => {
    setPasswordError(null);
    setPasswordSuccess(false);

    try {
      await authApi.changePassword(data.current_password, data.new_password);
      
      setPasswordSuccess(true);
      resetPassword();
      setIsChangingPassword(false);
      
      // Masquer le message de succès après 3 secondes
      setTimeout(() => {
        setPasswordSuccess(false);
      }, 3000);
    } catch (error) {
      console.error('Erreur lors du changement de mot de passe', error);
      if (error instanceof Error) {
        setPasswordError(error.message || 'Une erreur est survenue lors du changement de mot de passe');
      } else {
        setPasswordError('Une erreur est survenue lors du changement de mot de passe');
      }
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-blue-night">
        <div className="animate-pulse text-blue-400 text-xl">Chargement...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-blue-night p-6">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-2xl font-bold text-white mb-8">Mon Profil</h1>

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
              {isEditingProfile ? 'Annuler' : 'Modifier'}
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
                    Nom d'utilisateur
                  </label>
                  <input
                    id="username"
                    type="text"
                    {...registerProfile('username')}
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
                    {...registerProfile('email')}
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
                    {...registerProfile('full_name')}
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
                  {profileSubmitting ? (
                    <>
                      <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Enregistrement...
                    </>
                  ) : (
                    <>
                      <FiSave className="mr-2" />
                      Enregistrer
                    </>
                  )}
                </button>
              </div>
            </form>
          ) : (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <p className="text-sm font-medium text-gray-400">Nom d'utilisateur</p>
                  <p className="text-white">{user?.username}</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-400">Email</p>
                  <p className="text-white">{user?.email}</p>
                </div>
                <div className="md:col-span-2">
                  <p className="text-sm font-medium text-gray-400">Nom complet</p>
                  <p className="text-white">{user?.full_name || 'Non spécifié'}</p>
                </div>
              </div>
            </div>
          )}
        </div>

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
              {isChangingPassword ? 'Annuler' : 'Changer le mot de passe'}
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
                <label htmlFor="current_password" className="block text-sm font-medium text-gray-300 mb-1">
                  Mot de passe actuel
                </label>
                <input
                  id="current_password"
                  type="password"
                  {...registerPassword('current_password')}
                  className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                {passwordErrors.current_password && (
                  <p className="mt-1 text-sm text-red-400">{passwordErrors.current_password.message}</p>
                )}
              </div>

              <div>
                <label htmlFor="new_password" className="block text-sm font-medium text-gray-300 mb-1">
                  Nouveau mot de passe
                </label>
                <input
                  id="new_password"
                  type="password"
                  {...registerPassword('new_password')}
                  className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                {passwordErrors.new_password && (
                  <p className="mt-1 text-sm text-red-400">{passwordErrors.new_password.message}</p>
                )}
              </div>

              <div>
                <label htmlFor="confirm_password" className="block text-sm font-medium text-gray-300 mb-1">
                  Confirmer le nouveau mot de passe
                </label>
                <input
                  id="confirm_password"
                  type="password"
                  {...registerPassword('confirm_password')}
                  className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                {passwordErrors.confirm_password && (
                  <p className="mt-1 text-sm text-red-400">{passwordErrors.confirm_password.message}</p>
                )}
              </div>

              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={passwordSubmitting}
                  className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-500 transition-colors disabled:opacity-70"
                >
                  {passwordSubmitting ? (
                    <>
                      <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Enregistrement...
                    </>
                  ) : (
                    <>
                      <FiSave className="mr-2" />
                      Changer le mot de passe
                    </>
                  )}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}