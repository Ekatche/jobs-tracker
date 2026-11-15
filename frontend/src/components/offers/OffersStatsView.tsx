"use client";

import type { ReactNode } from "react";
import { FiBriefcase, FiExternalLink, FiGrid, FiMapPin } from "react-icons/fi";
import type { JobOfferStats } from "@/lib/api";

interface OffersStatsViewProps {
  stats: JobOfferStats | null;
  loading: boolean;
}

function RankedStatCard({
  title,
  icon,
  items,
  countClassName,
  loading,
}: {
  title: string;
  icon: ReactNode;
  items?: Array<{ _id: string; count: number }>;
  countClassName: string;
  loading: boolean;
}) {
  return (
    <div className="bg-blue-night-lighter rounded-lg p-6 border border-gray-700">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">{title}</h3>
        {icon}
      </div>
      {loading ? (
        <div className="animate-pulse space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="flex justify-between">
              <div className="h-4 bg-gray-600 rounded w-2/3" />
              <div className="h-4 bg-gray-600 rounded w-8" />
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-3 max-h-48 overflow-y-auto">
          {items && items.length > 0 ? (
            items.slice(0, 8).map((entry) => (
              <div key={entry._id} className="flex items-center justify-between">
                <span className="text-gray-300 truncate text-sm">{entry._id}</span>
                <span className={`${countClassName} font-medium text-sm`}>{entry.count}</span>
              </div>
            ))
          ) : (
            <p className="text-gray-400 text-sm">Aucune donnée</p>
          )}
        </div>
      )}
    </div>
  );
}

export default function OffersStatsView({ stats, loading }: OffersStatsViewProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 xl:grid-cols-4 gap-6">
      <div className="bg-blue-night-lighter rounded-lg p-6 border border-gray-700">
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="text-gray-400 text-sm">Total des offres</p>
            <p className="text-3xl font-bold text-blue-400">
              {loading ? "..." : stats?.total_offers?.toLocaleString() || 0}
            </p>
            <p className="text-gray-500 text-xs mt-1">
              Toutes offres en base, sans vos filtres de l&apos;onglet Offres
            </p>
          </div>
          <FiGrid className="w-10 h-10 text-blue-400" />
        </div>
      </div>

      <RankedStatCard
        title="Top Sites Web"
        icon={<FiExternalLink className="w-6 h-6 text-green-400" />}
        items={stats?.top_websites}
        countClassName="text-green-400"
        loading={loading}
      />
      <RankedStatCard
        title="Top Entreprises"
        icon={<FiBriefcase className="w-6 h-6 text-purple-400" />}
        items={stats?.top_companies}
        countClassName="text-purple-400"
        loading={loading}
      />
      <RankedStatCard
        title="Top Villes"
        icon={<FiMapPin className="w-6 h-6 text-orange-400" />}
        items={stats?.top_cities}
        countClassName="text-orange-400"
        loading={loading}
      />
    </div>
  );
}
