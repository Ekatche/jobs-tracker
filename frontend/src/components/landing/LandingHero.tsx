import Link from "next/link";
import { FiShield, FiClock, FiSearch, FiArrowRight } from "react-icons/fi";

export default function LandingHero() {
  return (
    <section className="relative pt-12 pb-16 md:pt-20 md:pb-24 overflow-hidden border-b border-slate-800/80">
      <div
        className="absolute -top-32 left-1/2 -translate-x-1/2 w-[700px] h-[350px] bg-gradient-to-b from-blue-600/15 via-indigo-600/10 to-transparent blur-3xl pointer-events-none -z-10"
        aria-hidden="true"
      />

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-center mb-6">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs sm:text-sm font-medium bg-slate-800/80 border border-slate-700/80 text-blue-300 shadow-sm">
            <FiShield className="text-emerald-400 text-base" />
            <span>Espace personnel sécurisé • 100% conforme RGPD • Zéro revente de données</span>
          </div>
        </div>

        <div className="text-center max-w-3xl mx-auto mb-10">
          <h1 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight leading-tight">
            Reprenez le contrôle de vos candidatures,{" "}
            <span className="bg-gradient-to-r from-blue-400 via-indigo-300 to-teal-300 bg-clip-text text-transparent">
              en toute sérénité
            </span>
          </h1>
          <p className="mt-5 text-base sm:text-lg text-slate-300 leading-relaxed font-normal">
            Un carnet de bord individuel pour regrouper vos démarches, savoir où vous en êtes
            avec chaque recruteur et préparer vos entretiens sans dispersion ni pression.
          </p>

          <div className="mt-8 flex flex-wrap items-center justify-center gap-3 sm:gap-4">
            <Link
              href="/auth/login"
              className="inline-flex items-center gap-2 px-5 py-3 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-sm transition-all shadow-lg shadow-blue-900/30 hover:-translate-y-0.5"
            >
              <span>Accéder à mon espace</span>
              <FiArrowRight className="text-base" />
            </Link>
            <Link
              href="/offers"
              className="inline-flex items-center gap-2 px-5 py-3 rounded-lg bg-slate-800/90 hover:bg-slate-700 border border-slate-700 text-slate-200 text-sm font-medium transition-colors"
            >
              <FiSearch className="text-base text-slate-400" />
              <span>Explorer les offres du moment</span>
            </Link>
          </div>
        </div>

        <div className="max-w-4xl mx-auto mt-10">
          <div className="bg-slate-900/90 rounded-2xl border border-slate-800 p-4 sm:p-6 shadow-2xl backdrop-blur-md">
            <div className="flex flex-wrap items-center justify-between gap-3 pb-4 mb-5 border-b border-slate-800">
              <div className="flex items-center gap-3">
                <div className="w-3 h-3 rounded-full bg-red-500/80" />
                <div className="w-3 h-3 rounded-full bg-amber-500/80" />
                <div className="w-3 h-3 rounded-full bg-emerald-500/80" />
                <span className="text-xs font-mono text-slate-400 ml-2">
                  Mon carnet de bord — Vue synthétique
                </span>
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-400 bg-slate-800/80 px-2.5 py-1 rounded-md border border-slate-700/60">
                <FiClock className="text-blue-400" />
                <span>Dernière mise à jour : Aujourd&apos;hui</span>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-5">
              <div className="bg-slate-800/40 rounded-xl p-3 border border-slate-800">
                <p className="text-xs text-slate-400 font-medium">Démarches en cours</p>
                <p className="text-2xl font-bold text-white mt-0.5">8</p>
                <p className="text-[11px] text-slate-400 mt-1">
                  Sur LinkedIn, Indeed et candidatures spontanées
                </p>
              </div>
              <div className="bg-slate-800/40 rounded-xl p-3 border border-slate-800">
                <p className="text-xs text-slate-400 font-medium">Entretiens programmés</p>
                <p className="text-2xl font-bold text-blue-400 mt-0.5">2</p>
                <p className="text-[11px] text-slate-400 mt-1">
                  Dont 1 échange technique cette semaine
                </p>
              </div>
              <div className="bg-slate-800/40 rounded-xl p-3 border border-slate-800">
                <p className="text-xs text-slate-400 font-medium">Relance conseillée</p>
                <p className="text-2xl font-bold text-amber-400 mt-0.5">1</p>
                <p className="text-[11px] text-slate-400 mt-1">
                  Délai de 10 jours atteint sans retour
                </p>
              </div>
            </div>

            <div className="space-y-2.5">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between p-3 rounded-lg bg-slate-800/30 border border-slate-800/80 hover:border-slate-700 transition-colors gap-2">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-md bg-blue-900/40 text-blue-300 flex items-center justify-center font-bold text-xs">
                    SN
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-white">Responsable Chef de Projet</p>
                    <p className="text-xs text-slate-400">Studio Nova • Paris (Hybride)</p>
                  </div>
                </div>
                <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 flex items-center gap-1.5 self-start sm:self-auto">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  Entretien RH (Mardi 14h)
                </span>
              </div>

              <div className="flex flex-col sm:flex-row sm:items-center justify-between p-3 rounded-lg bg-slate-800/30 border border-slate-800/80 hover:border-slate-700 transition-colors gap-2">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-md bg-indigo-900/40 text-indigo-300 flex items-center justify-center font-bold text-xs">
                    HL
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-white">Consultant Fonctionnel</p>
                    <p className="text-xs text-slate-400">HexaLab • Lyon (Télétravail partiel)</p>
                  </div>
                </div>
                <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-300 border border-amber-500/20 flex items-center gap-1.5 self-start sm:self-auto">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                  Relance courtoise suggérée
                </span>
              </div>

              <div className="flex flex-col sm:flex-row sm:items-center justify-between p-3 rounded-lg bg-slate-800/30 border border-slate-800/80 hover:border-slate-700 transition-colors gap-2">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-md bg-teal-900/40 text-teal-300 flex items-center justify-center font-bold text-xs">
                    AL
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-white">Chargé de Missions RH</p>
                    <p className="text-xs text-slate-400">Altius Conseil • Nantes</p>
                  </div>
                </div>
                <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-blue-500/10 text-blue-300 border border-blue-500/20 flex items-center gap-1.5 self-start sm:self-auto">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-400" />
                  Candidature envoyée
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
