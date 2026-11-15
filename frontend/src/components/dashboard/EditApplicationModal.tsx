"use client";

import { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { FiX, FiSave, FiCheck, FiArchive, FiTrash2 } from "react-icons/fi";
import { applicationApi } from "@/lib/api";
import { format } from "date-fns";
import { Application } from "@/types/application";
import {
  applicationSchema,
  type ApplicationFormData,
  EDIT_APP_STATUSES,
} from "./application-modal/applicationFormSchema";
import ApplicationFormFields from "./application-modal/ApplicationFormFields";
import ApplicationNotesEditor from "./application-modal/ApplicationNotesEditor";

interface EditApplicationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  application: Application | null;
}

export default function EditApplicationModal({
  isOpen,
  onClose,
  onSuccess,
  application,
}: EditApplicationModalProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showSuccessMessage, setShowSuccessMessage] = useState(false);
  const [actionType, setActionType] = useState<"update" | "delete" | "archive" | null>(null);

  const [notes, setNotes] = useState<string[]>([]);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ApplicationFormData>({
    resolver: zodResolver(applicationSchema),
    defaultValues: {
      company: "",
      position: "",
      location: "",
      status: "Candidature envoyée",
      url: "",
      application_date: format(new Date(), "yyyy-MM-dd"),
      description: "",
    },
  });

  useEffect(() => {
    if (application) {
      reset({
        company: application.company,
        position: application.position,
        location: application.location || "",
        status: application.status,
        url: application.url || "",
        application_date: application.application_date.substring(0, 10),
        description: application.description || "",
      });
    }
  }, [application, reset]);

  useEffect(() => {
    setNotes(application?.notes || []);
  }, [application]);

  const handleDeleteApplication = async () => {
    if (!application?._id) return;
    if (
      !confirm(
        "Êtes-vous sûr de vouloir supprimer cette candidature ? Cette action est irréversible."
      )
    ) {
      return;
    }

    try {
      setIsSubmitting(true);
      setError(null);
      setActionType("delete");
      await applicationApi.delete(application._id);
      setShowSuccessMessage(true);
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 1000);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Une erreur est survenue lors de la suppression de la candidature"
      );
      setIsSubmitting(false);
    }
  };

  const onSubmit = async (data: ApplicationFormData) => {
    if (!application?._id) return;
    setIsSubmitting(true);
    setError(null);
    setShowSuccessMessage(false);
    setActionType("update");

    try {
      await applicationApi.update(application._id, {
        ...data,
        url: data.url === "" ? undefined : data.url,
        notes,
      });
      setShowSuccessMessage(true);
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 1500);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Une erreur est survenue lors de la modification de la candidature"
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggleArchive = async () => {
    if (!application) return;
    try {
      setIsSubmitting(true);
      setActionType("archive");
      await applicationApi.update(application._id, {
        ...application,
        archived: !application.archived,
      });
      setShowSuccessMessage(true);
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 1500);
    } catch (err) {
      console.error("Erreur lors de l'archivage/désarchivage:", err);
      setError("Une erreur est survenue lors de l'archivage/désarchivage de la candidature");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen || !application) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black/60 backdrop-blur-sm flex items-center justify-center">
      <div className="relative bg-blue-night-lighter rounded-lg shadow-xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto border border-gray-700">
        <div className="flex justify-between items-center px-6 py-4 border-b border-gray-700">
          <h2 className="text-xl font-semibold text-white flex items-center">
            <FiSave className="mr-2" /> Modifier la candidature
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors"
            disabled={isSubmitting}
          >
            <FiX className="text-xl" />
          </button>
        </div>

        <div className="p-6">
          {error && (
            <div className="bg-red-900/40 border border-red-600 text-red-200 p-3 rounded-md mb-4">
              {error}
            </div>
          )}

          {showSuccessMessage && (
            <div
              className={`${
                actionType === "delete"
                  ? "bg-red-900/40 border-red-600"
                  : "bg-green-900/40 border-green-600"
              } border p-3 rounded-md mb-4 flex items-center text-white`}
            >
              <FiCheck className="mr-2" />
              {actionType === "delete"
                ? "Candidature supprimée avec succès !"
                : actionType === "archive"
                ? "Candidature archivée avec succès !"
                : "Candidature modifiée avec succès !"}
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <ApplicationFormFields
              register={register}
              errors={errors}
              statuses={EDIT_APP_STATUSES}
              descriptionRows={4}
              urlPlaceholder="https://..."
            />

            <ApplicationNotesEditor notes={notes} onChange={setNotes} />

            <div className="flex justify-between space-x-3 pt-4 border-t border-gray-700">
              <button
                type="button"
                onClick={handleDeleteApplication}
                className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors flex items-center"
                disabled={isSubmitting || showSuccessMessage}
              >
                <FiTrash2 className="w-4 h-4 mr-1" />
                Supprimer
              </button>

              <button
                type="button"
                onClick={handleToggleArchive}
                className={`px-4 py-2 ${
                  application?.archived ? "bg-blue-600 hover:bg-blue-700" : "bg-gray-600 hover:bg-gray-700"
                } text-white rounded-md transition-colors flex items-center`}
                disabled={isSubmitting || showSuccessMessage}
              >
                <FiArchive className="mr-2" />
                {application?.archived ? "Désarchiver" : "Archiver"}
              </button>

              <div className="flex space-x-3">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 bg-gray-700 text-white rounded-md hover:bg-gray-600 transition-colors"
                  disabled={isSubmitting || showSuccessMessage}
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-500 transition-colors flex items-center"
                  disabled={isSubmitting || showSuccessMessage}
                >
                  <FiSave className="mr-2" />
                  {isSubmitting
                    ? actionType === "delete"
                      ? "Suppression..."
                      : "Enregistrement..."
                    : showSuccessMessage
                    ? actionType === "delete"
                      ? "Supprimée"
                      : "Enregistrée"
                    : "Enregistrer"}
                </button>
              </div>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
