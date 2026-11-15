"use client";

import { FieldErrors, UseFormRegister } from "react-hook-form";
import { FiCalendar } from "react-icons/fi";
import type { ApplicationFormData } from "./applicationFormSchema";

interface ApplicationFormFieldsProps {
  register: UseFormRegister<ApplicationFormData>;
  errors: FieldErrors<ApplicationFormData>;
  statuses: string[];
  descriptionRows?: number;
  urlPlaceholder?: string;
}

export default function ApplicationFormFields({
  register,
  errors,
  statuses,
  descriptionRows = 3,
  urlPlaceholder = "https://exemple.com/offre",
}: ApplicationFormFieldsProps) {
  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="col-span-1">
          <label htmlFor="company" className="block text-sm font-medium text-gray-300 mb-1">
            Entreprise *
          </label>
          <input
            id="company"
            type="text"
            {...register("company")}
            className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          {errors.company && (
            <p className="mt-1 text-sm text-red-400">{errors.company.message}</p>
          )}
        </div>

        <div className="col-span-1">
          <label htmlFor="position" className="block text-sm font-medium text-gray-300 mb-1">
            Poste *
          </label>
          <input
            id="position"
            type="text"
            {...register("position")}
            className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          {errors.position && (
            <p className="mt-1 text-sm text-red-400">{errors.position.message}</p>
          )}
        </div>

        <div className="col-span-1">
          <label htmlFor="location" className="block text-sm font-medium text-gray-300 mb-1">
            Localisation
          </label>
          <input
            id="location"
            type="text"
            {...register("location")}
            className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Ex: Paris, Remote, etc."
          />
        </div>

        <div className="col-span-1">
          <label htmlFor="status" className="block text-sm font-medium text-gray-300 mb-1">
            Statut *
          </label>
          <select
            id="status"
            {...register("status")}
            className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {statuses.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          {errors.status && (
            <p className="mt-1 text-sm text-red-400">{errors.status.message}</p>
          )}
        </div>

        <div className="col-span-1">
          <label htmlFor="url" className="block text-sm font-medium text-gray-300 mb-1">
            URL de l&apos;offre
          </label>
          <input
            id="url"
            type="text"
            {...register("url")}
            className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder={urlPlaceholder}
          />
          {errors.url && (
            <p className="mt-1 text-sm text-red-400">{errors.url.message}</p>
          )}
        </div>

        <div className="col-span-1">
          <label
            htmlFor="application_date"
            className="block text-sm font-medium text-gray-300 mb-1"
          >
            Date de candidature *
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <FiCalendar className="text-gray-400" />
            </div>
            <input
              id="application_date"
              type="date"
              {...register("application_date")}
              className="w-full rounded-md bg-blue-night border border-gray-700 py-2 pl-10 pr-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          {errors.application_date && (
            <p className="mt-1 text-sm text-red-400">{errors.application_date.message}</p>
          )}
        </div>
      </div>

      <div>
        <label htmlFor="description" className="block text-sm font-medium text-gray-300 mb-1">
          Description
        </label>
        <textarea
          id="description"
          {...register("description")}
          rows={descriptionRows}
          className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Description du poste, compétences requises, etc."
        />
      </div>
    </>
  );
}
