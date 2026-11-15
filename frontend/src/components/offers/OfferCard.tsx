"use client";

import { memo, useState } from "react";
import Link from "next/link";
import {
  FiBookmark,
  FiCalendar,
  FiCheckCircle,
  FiClock,
  FiExternalLink,
  FiEye,
  FiEyeOff,
  FiFileText,
  FiMapPin,
  FiPlus,
  FiRefreshCw,
} from "react-icons/fi";
import type { JobOffer } from "@/lib/api";
import { cleanDescriptionPreview, formatAddedDate, formatOfferDate } from "@/lib/offerFormatters";
import OfferCardBadges from "@/components/offers/OfferCardBadges";

export interface OfferCardProps {
  offer: JobOffer;
  currentPage: number;
  regeneratingId: string | null;
  onToggleSeen: (offerId: string, currentlySeen?: boolean) => void;
  onToggleSaveOffer: (offerId: string, currentInteraction?: string | null) => void;
  onRegenerateDescription: (offerId: string) => void;
  onHideOffer: (offerId: string) => void;
  onApplyToOffer: (offer: JobOffer) => void;
}

const OfferCard = memo(function OfferCard({
  offer,
  currentPage,
  regeneratingId,
  onToggleSeen,
  onToggleSaveOffer,
  onRegenerateDescription,
  onHideOffer,
  onApplyToOffer,
}: OfferCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const cleanedDescription = cleanDescriptionPreview(offer.description);
  const isSaved = offer.user_interaction === "saved";
  const addedDateText = formatAddedDate(offer.created_at);

  return (
    <div
      className={`bg-slate-900/80 hover:bg-slate-900/95 rounded-2xl p-5 shadow-lg hover:shadow-xl transition-all duration-200 border border-slate-800 hover:border-blue-500/40 relative group flex flex-col justify-between backdrop-blur-sm ${
        offer.seen ? "opacity-60" : ""
      }`}
    >
      {/* Quick action buttons */}
      <div className="absolute top-3 right-3 flex items-center gap-1 z-10">
        <button
          type="button"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onToggleSeen(offer.id, offer.seen);
          }}
          className={`p-1.5 rounded-lg border transition-all ${
            offer.seen
              ? "bg-slate-700/60 text-slate-300 border-slate-600 opacity-100"
              : "bg-slate-800 hover:bg-emerald-500/20 text-slate-400 hover:text-emerald-300 border-slate-700 opacity-0 group-hover:opacity-100"
          }`}
          title={offer.seen ? "Marquer comme non vue" : "Marquer comme vue"}
        >
          {offer.seen ? <FiCheckCircle className="w-3.5 h-3.5" /> : <FiEye className="w-3.5 h-3.5" />}
        </button>
        <button
          type="button"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onToggleSaveOffer(offer.id, offer.user_interaction);
          }}
          className={`p-1.5 rounded-lg border transition-all ${
            isSaved
              ? "bg-amber-500/20 text-amber-300 border-amber-500/40 opacity-100"
              : "bg-slate-800 hover:bg-amber-500/20 text-slate-400 hover:text-amber-300 border-slate-700 opacity-0 group-hover:opacity-100"
          }`}
          title={isSaved ? "Retirer des favoris" : "Sauvegarder cette offre"}
        >
          <FiBookmark className={`w-3.5 h-3.5 ${isSaved ? "fill-amber-400 text-amber-400" : ""}`} />
        </button>
        <button
          type="button"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onRegenerateDescription(offer.id);
          }}
          disabled={regeneratingId === offer.id}
          className="opacity-0 group-hover:opacity-100 bg-slate-800 hover:bg-blue-600 text-slate-300 hover:text-white p-1.5 rounded-lg border border-slate-700 transition-all disabled:opacity-50"
          title="Régénérer la description par IA"
        >
          <FiRefreshCw className={`w-3.5 h-3.5 ${regeneratingId === offer.id ? "animate-spin" : ""}`} />
        </button>
        <button
          type="button"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onHideOffer(offer.id);
          }}
          className="opacity-0 group-hover:opacity-100 bg-slate-800 hover:bg-rose-600 text-slate-300 hover:text-white p-1.5 rounded-lg border border-slate-700 transition-all"
          title="Masquer cette offre pour mon compte"
        >
          <FiEyeOff className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="flex flex-col h-full">
        <div className="flex-1">
          <div className="flex items-center gap-3 pr-12">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600/80 to-indigo-600/80 border border-white/10 flex items-center justify-center font-bold text-white text-sm shrink-0 shadow-sm shadow-blue-500/10">
              {offer.entreprise ? offer.entreprise.charAt(0).toUpperCase() : "?"}
            </div>
            <div className="min-w-0 flex-1">
              <h4 className="text-xs font-semibold text-slate-300 truncate">{offer.entreprise}</h4>
              {offer.localisation && offer.localisation !== "Non spécifié" && (
                <div className="flex items-center gap-1 text-slate-400 text-[11px] truncate mt-0.5">
                  <FiMapPin className="w-3 h-3 text-blue-400 shrink-0" />
                  <span className="truncate">{offer.localisation}</span>
                </div>
              )}
            </div>
          </div>

          <Link href={`/offers/${offer.id}?page=${currentPage}`} className="group/title block">
            <h3 className="text-base font-bold text-white group-hover/title:text-blue-400 transition-colors line-clamp-2 mt-3 mb-2.5 leading-snug">
              {offer.poste}
            </h3>
          </Link>

          <OfferCardBadges offer={offer} />

          {!cleanedDescription ? (
            <div className="mb-3 bg-slate-950/40 p-2.5 rounded-xl border border-dashed border-slate-800 flex items-center justify-between">
              <span className="text-slate-500 text-xs italic">Description non générée</span>
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  onRegenerateDescription(offer.id);
                }}
                disabled={regeneratingId === offer.id}
                className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 font-medium disabled:opacity-50"
              >
                <FiRefreshCw className={`w-3 h-3 ${regeneratingId === offer.id ? "animate-spin" : ""}`} />
                <span>{regeneratingId === offer.id ? "Génération..." : "Régénérer"}</span>
              </button>
            </div>
          ) : (
            <div className="mb-3 bg-slate-950/40 p-3 rounded-xl border border-slate-800/80">
              <p
                className={`text-slate-300 text-xs leading-relaxed whitespace-pre-line ${
                  !isExpanded ? "line-clamp-3" : "max-h-56 overflow-y-auto"
                }`}
              >
                {cleanedDescription}
              </p>
              {cleanedDescription.length > 150 && (
                <button
                  type="button"
                  onClick={() => setIsExpanded(!isExpanded)}
                  className="mt-2 text-[11px] text-blue-400 hover:text-blue-300 font-semibold focus:outline-none flex items-center gap-1 transition-colors"
                >
                  {isExpanded ? "Voir moins ▲" : "Voir plus ▼"}
                </button>
              )}
            </div>
          )}

          {offer.competences_cles && offer.competences_cles.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-3">
              {offer.competences_cles.slice(0, 3).map((comp, idx) => (
                <span
                  key={idx}
                  className="px-2 py-0.5 bg-slate-800/80 text-slate-300 text-[11px] rounded border border-slate-700/50"
                >
                  {comp}
                </span>
              ))}
              {offer.competences_cles.length > 3 && (
                <span className="text-[11px] text-slate-400 self-center">
                  +{offer.competences_cles.length - 3}
                </span>
              )}
            </div>
          )}

          <div className="flex flex-col gap-1 mb-4 text-xs text-slate-400">
            {addedDateText && (
              <div className="flex items-center gap-1.5 text-emerald-400 font-medium">
                <FiClock className="w-3.5 h-3.5 shrink-0 text-emerald-400" />
                <span>{addedDateText}</span>
              </div>
            )}
            <div className="flex items-center gap-1.5 text-slate-400">
              <FiCalendar className="w-3.5 h-3.5 shrink-0" />
              <span>Publication : {formatOfferDate(offer.date || "")}</span>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 pt-3 border-t border-slate-800">
          <Link
            href={`/offers/${offer.id}?page=${currentPage}`}
            className="flex-1 min-w-[88px] bg-slate-800/90 hover:bg-slate-700 text-slate-200 hover:text-white px-3 py-2 rounded-xl text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 border border-slate-700/80 hover:border-slate-600 shadow-sm"
            title="Consulter l'évaluation détaillée"
          >
            <FiEye className="w-3.5 h-3.5 text-blue-400" />
            <span>Détails</span>
          </Link>

          <Link
            href={`/resumes?generate_offer_id=${offer.id}`}
            className="flex-1 min-w-[88px] bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 hover:text-white px-3 py-2 rounded-xl text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 border border-indigo-500/30 shadow-sm"
            title="Générer un CV adapté sur-mesure pour cette offre"
          >
            <FiFileText className="w-3.5 h-3.5 text-indigo-400" />
            <span>CV Adapté</span>
          </Link>

          {offer.url && (
            <a
              href={offer.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 min-w-[88px] bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 hover:text-white px-3 py-2 rounded-xl text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 border border-blue-500/30"
            >
              <FiExternalLink className="w-3.5 h-3.5" />
              <span>Offre</span>
            </a>
          )}

          <button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              onApplyToOffer(offer);
            }}
            className="flex-1 min-w-[88px] bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white px-3.5 py-2 rounded-xl text-xs font-semibold transition-all shadow-sm shadow-emerald-500/20 flex items-center justify-center gap-1.5"
            title="Postuler à cette offre"
          >
            <FiPlus className="w-3.5 h-3.5" />
            <span>Postuler</span>
          </button>
        </div>
      </div>
    </div>
  );
});

export default OfferCard;
