import type { Metadata } from "next";
import Link from "next/link";
import {
  FiBriefcase,
  FiShield,
  FiCheckCircle,
  FiClock,
  FiFileText,
  FiSearch,
  FiLock,
  FiDatabase,
  FiUserCheck,
  FiArrowRight,
  FiCalendar,
  FiCheck,
  FiEyeOff,
  FiTrash2,
  FiHelpCircle,
} from "react-icons/fi";

export const metadata: Metadata = {
  title: "MonSuiviJob — Votre espace personnel de suivi de candidatures",
  description:
    "Organisez simplement vos démarches d'emploi, gardez le fil de vos relances et préparez vos entretiens dans un cadre respectueux de votre vie privée (RGPD).",
};

export default function Home() {
  return (
    <div className="min-h-screen bg-blue-night text-slate-100 selection:bg-blue-600 selection:text-white">
      {/* ============================================================ */}
      {/* 1. HERO SECTION INFORMATIVE & APAISANTE                       */}
      {/* ============================================================ */}
      <section className="relative pt-12 pb-16 md:pt-20 md:pb-24 overflow-hidden border-b border-slate-800/80">
        {/* Halos lumineux discrets d'arrière-plan */}
        <div
          className="absolute -top-32 left-1/2 -translate-x-1/2 w-[700px] h-[350px] bg-gradient-to-b from-blue-600/15 via-indigo-600/10 to-transparent blur-3xl pointer-events-none -z-10"
          aria-hidden="true"
        />

        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Badge de confiance et de positionnement éthique */}
          <div className="flex justify-center mb-6">
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs sm:text-sm font-medium bg-slate-800/80 border border-slate-700/80 text-blue-300 shadow-sm">
              <FiShield className="text-emerald-400 text-base" />
              <span>Espace personnel sécurisé • 100% conforme RGPD • Zéro revente de données</span>
            </div>
          </div>

          {/* Titre et proposition de valeur claire */}
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

            {/* CTAs sobres et mesurés (accès direct, sans agressivité) */}
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

          {/* APERÇU VISUEL RÉALISTE : Mini-tableau de bord transparent */}
          <div className="max-w-4xl mx-auto mt-10">
            <div className="bg-slate-900/90 rounded-2xl border border-slate-800 p-4 sm:p-6 shadow-2xl backdrop-blur-md">
              {/* En-tête de la maquette démonstrative */}
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
                  <span>Dernière mise à jour : Aujourd'hui</span>
                </div>
              </div>

              {/* Indicateurs clés vulgarisés */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-5">
                <div className="bg-slate-800/40 rounded-xl p-3 border border-slate-800">
                  <p className="text-xs text-slate-400 font-medium">Démarches en cours</p>
                  <p className="text-2xl font-bold text-white mt-0.5">8</p>
                  <p className="text-[11px] text-slate-400 mt-1">Sur LinkedIn, Indeed et candidatures spontanées</p>
                </div>
                <div className="bg-slate-800/40 rounded-xl p-3 border border-slate-800">
                  <p className="text-xs text-slate-400 font-medium">Entretiens programmés</p>
                  <p className="text-2xl font-bold text-blue-400 mt-0.5">2</p>
                  <p className="text-[11px] text-slate-400 mt-1">Dont 1 échange technique cette semaine</p>
                </div>
                <div className="bg-slate-800/40 rounded-xl p-3 border border-slate-800">
                  <p className="text-xs text-slate-400 font-medium">Relance conseillée</p>
                  <p className="text-2xl font-bold text-amber-400 mt-0.5">1</p>
                  <p className="text-[11px] text-slate-400 mt-1">Délai de 10 jours atteint sans retour</p>
                </div>
              </div>

              {/* Exemples réalistes de candidatures suivies */}
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
                  <div className="flex items-center gap-2 self-start sm:self-auto">
                    <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                      Entretien RH (Mardi 14h)
                    </span>
                  </div>
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
                  <div className="flex items-center gap-2 self-start sm:self-auto">
                    <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-300 border border-amber-500/20 flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                      Relance courtoise suggérée
                    </span>
                  </div>
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
                  <div className="flex items-center gap-2 self-start sm:self-auto">
                    <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-blue-500/10 text-blue-300 border border-blue-500/20 flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-blue-400" />
                      Candidature envoyée
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ============================================================ */}
      {/* 2. NOS OUTILS EXPLIQUÉS SIMPLEMENT (VULGARISATION ACCESSIBLE) */}
      {/* ============================================================ */}
      <section className="py-16 md:py-24 bg-slate-900/50 border-b border-slate-800/80">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-14">
            <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
              Des outils pratiques, pensés pour clarifier votre quotidien
            </h2>
            <p className="mt-3 text-slate-300 text-sm sm:text-base leading-relaxed">
              Pas de jargon technique : chaque fonctionnalité répond à un besoin concret pour
              éviter les oublis et aborder sereinement chaque étape du recrutement.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Outil 1 : Carnet de bord */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-6 sm:p-7 hover:border-slate-700 transition-colors">
              <div className="w-12 h-12 rounded-xl bg-blue-900/30 border border-blue-700/40 flex items-center justify-center mb-5 text-blue-400">
                <FiBriefcase className="text-2xl" />
              </div>
              <h3 className="text-lg font-bold text-white mb-2">
                1. Le Carnet de bord des candidatures
              </h3>
              <p className="text-sm text-slate-300 leading-relaxed mb-4">
                Regroupez au même endroit toutes les annonces auxquelles vous avez répondu, quel que soit
                le site d'origine. Chaque fiche conserve l'annonce originale, la date d'envoi et vos notes.
              </p>
              <div className="pt-3 border-t border-slate-800 text-xs text-slate-400 flex items-center gap-2">
                <FiCheckCircle className="text-emerald-400 shrink-0" />
                <span>Bénéfice : Quand un recruteur vous appelle, vous retrouvez le contexte en 5 secondes.</span>
              </div>
            </div>

            {/* Outil 2 : Assistant de préparation */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-6 sm:p-7 hover:border-slate-700 transition-colors">
              <div className="w-12 h-12 rounded-xl bg-indigo-900/30 border border-indigo-700/40 flex items-center justify-center mb-5 text-indigo-400">
                <FiFileText className="text-2xl" />
              </div>
              <h3 className="text-lg font-bold text-white mb-2">
                2. L'Assistant de préparation ciblée
              </h3>
              <p className="text-sm text-slate-300 leading-relaxed mb-4">
                Une aide pour reformuler vos lettres de motivation et messages d'accroche en mettant
                en valeur vos expériences réelles face aux critères demandés par l'entreprise.
              </p>
              <div className="pt-3 border-t border-slate-800 text-xs text-slate-400 flex items-center gap-2">
                <FiCheckCircle className="text-emerald-400 shrink-0" />
                <span>Bénéfice : Aucune phrase générique, vous gardez la main sur le texte final.</span>
              </div>
            </div>

            {/* Outil 3 : Radar d'offres */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-6 sm:p-7 hover:border-slate-700 transition-colors">
              <div className="w-12 h-12 rounded-xl bg-teal-900/30 border border-teal-700/40 flex items-center justify-center mb-5 text-teal-400">
                <FiSearch className="text-2xl" />
              </div>
              <h3 className="text-lg font-bold text-white mb-2">
                3. Le Radar d'opportunités sans bruit
              </h3>
              <p className="text-sm text-slate-300 leading-relaxed mb-4">
                Consultez des offres d'emploi qualifiées selon vos souhaits précis (localisation, télétravail,
                type de contrat) sans vous perdre dans des centaines de notifications inutiles.
              </p>
              <div className="pt-3 border-t border-slate-800 text-xs text-slate-400 flex items-center gap-2">
                <FiCheckCircle className="text-emerald-400 shrink-0" />
                <span>Bénéfice : Une lecture rapide des critères clés pour décider si l'offre vaut votre temps.</span>
              </div>
            </div>

            {/* Outil 4 : Suivi des relances */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-6 sm:p-7 hover:border-slate-700 transition-colors">
              <div className="w-12 h-12 rounded-xl bg-amber-900/30 border border-amber-700/40 flex items-center justify-center mb-5 text-amber-400">
                <FiCalendar className="text-2xl" />
              </div>
              <h3 className="text-lg font-bold text-white mb-2">
                4. L'Échéancier de relance courtoise
              </h3>
              <p className="text-sm text-slate-300 leading-relaxed mb-4">
                Un rappel temporel bien dosé (généralement 7 à 12 jours après l'envoi) pour vous indiquer
                le bon moment pour recontacter l'entreprise avec professionnalisme.
              </p>
              <div className="pt-3 border-t border-slate-800 text-xs text-slate-400 flex items-center gap-2">
                <FiCheckCircle className="text-emerald-400 shrink-0" />
                <span>Bénéfice : Ne plus jamais laisser une opportunité s'éteindre par simple oubli.</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ============================================================ */}
      {/* 3. ENGAGEMENT RGPD & CONFIDENTIALITÉ TRANSPARENTE             */}
      {/* ============================================================ */}
      <section className="py-16 md:py-24 border-b border-slate-800/80 bg-blue-night">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-14">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 mb-3">
              <FiLock className="text-xs" />
              <span>Conformité Réglementaire Européenne</span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
              Vos données vous appartiennent. Strictement.
            </h2>
            <p className="mt-3 text-slate-300 text-sm sm:text-base leading-relaxed">
              Une recherche d'emploi implique des informations hautement personnelles (parcours, CV,
              coordonnées, rémunération). Notre modèle garantit une étanchéité complète.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800">
              <div className="w-10 h-10 rounded-lg bg-emerald-900/30 text-emerald-400 flex items-center justify-center mb-4">
                <FiEyeOff className="text-xl" />
              </div>
              <h4 className="font-bold text-white text-sm mb-2">Zéro revente de données</h4>
              <p className="text-xs text-slate-300 leading-relaxed">
                Vos démarches, CV et coordonnées ne sont jamais vendus ni cédés à des tiers, régies ou démarcheurs.
              </p>
            </div>

            <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800">
              <div className="w-10 h-10 rounded-lg bg-blue-900/30 text-blue-400 flex items-center justify-center mb-4">
                <FiDatabase className="text-xl" />
              </div>
              <h4 className="font-bold text-white text-sm mb-2">Hébergement sécurisé UE</h4>
              <p className="text-xs text-slate-300 leading-relaxed">
                Vos informations sont traitées selon les normes européennes et chiffrées en transit comme au repos.
              </p>
            </div>

            <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800">
              <div className="w-10 h-10 rounded-lg bg-amber-900/30 text-amber-400 flex items-center justify-center mb-4">
                <FiTrash2 className="text-xl" />
              </div>
              <h4 className="font-bold text-white text-sm mb-2">Droit à l'oubli en 1 clic</h4>
              <p className="text-xs text-slate-300 leading-relaxed">
                Vous pouvez exporter l'ensemble de vos données ou supprimer définitivement votre compte à tout moment.
              </p>
            </div>

            <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800">
              <div className="w-10 h-10 rounded-lg bg-indigo-900/30 text-indigo-400 flex items-center justify-center mb-4">
                <FiUserCheck className="text-xl" />
              </div>
              <h4 className="font-bold text-white text-sm mb-2">Contrôle intégral</h4>
              <p className="text-xs text-slate-300 leading-relaxed">
                Les suggestions fournies sont consultatives : aucun envoi de candidature ne s'effectue sans votre action directe.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ============================================================ */}
      {/* 4. QUESTIONS FRÉQUENTES VULGARISÉES (FAQ)                    */}
      {/* ============================================================ */}
      <section className="py-16 md:py-20 bg-slate-900/30 border-b border-slate-800/80">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
              Questions fréquentes
            </h2>
            <p className="mt-2 text-slate-400 text-sm">
              Quelques éclaircissements pour démarrer l'esprit tranquille.
            </p>
          </div>

          <div className="space-y-4">
            <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800">
              <div className="flex items-start gap-3">
                <FiHelpCircle className="text-blue-400 text-lg mt-0.5 shrink-0" />
                <div>
                  <h4 className="text-sm sm:text-base font-semibold text-white">
                    Est-ce adapté si je n'envoie que quelques candidatures par mois ?
                  </h4>
                  <p className="mt-1.5 text-xs sm:text-sm text-slate-300 leading-relaxed">
                    Oui, tout à fait. Même avec 2 ou 3 candidatures actives, le suivi permet de retrouver immédiatement
                    les détails exacts d'une offre lors d'un premier appel téléphonique ou pour savoir quand relancer sans hésiter.
                  </p>
                </div>
              </div>
            </div>

            <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800">
              <div className="flex items-start gap-3">
                <FiHelpCircle className="text-blue-400 text-lg mt-0.5 shrink-0" />
                <div>
                  <h4 className="text-sm sm:text-base font-semibold text-white">
                    Mon employeur actuel peut-il voir mes démarches ?
                  </h4>
                  <p className="mt-1.5 text-xs sm:text-sm text-slate-300 leading-relaxed">
                    Non. Votre espace MonSuiviJob est strictement individuel et hermétique. Il n'existe aucun annuaire
                    public de profils ni d'accès recruteur à vos données.
                  </p>
                </div>
              </div>
            </div>

            <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800">
              <div className="flex items-start gap-3">
                <FiHelpCircle className="text-blue-400 text-lg mt-0.5 shrink-0" />
                <div>
                  <h4 className="text-sm sm:text-base font-semibold text-white">
                    Comment démarrer concrètement ?
                  </h4>
                  <p className="mt-1.5 text-xs sm:text-sm text-slate-300 leading-relaxed">
                    Vous créez votre compte en quelques secondes, puis vous ajoutez manuellement ou collez le lien de votre
                    première candidature. Si vous le souhaitez, vous pouvez aussi importer votre CV pour faciliter vos rédactions.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ============================================================ */}
      {/* 5. PIED DE PAGE SOBRE & MENTIONS ÉTHIQUES                     */}
      {/* ============================================================ */}
      <footer className="py-12 bg-slate-950 text-slate-400 border-t border-slate-800 text-xs">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex items-center gap-3">
              <div className="w-7 h-7 rounded-md bg-blue-600 flex items-center justify-center text-white font-bold text-xs">
                M
              </div>
              <span className="font-bold text-sm text-white">MonSuiviJob</span>
              <span className="text-slate-500">•</span>
              <span className="text-slate-400">Le carnet de bord serein de vos candidatures</span>
            </div>

            <div className="flex items-center gap-6 text-xs">
              <Link href="/offers" className="hover:text-white transition-colors">
                Offres d'emploi
              </Link>
              <Link href="/auth/login" className="hover:text-white transition-colors">
                Connexion
              </Link>
              <Link href="/auth/register" className="hover:text-white transition-colors">
                Créer un compte
              </Link>
            </div>
          </div>

          <div className="mt-8 pt-6 border-t border-slate-900 flex flex-col sm:flex-row items-center justify-between gap-3 text-slate-500 text-[11px]">
            <p>© {new Date().getFullYear()} MonSuiviJob. Conçu avec respect pour les candidats et la vie privée.</p>
            <p>Conforme au Règlement Général sur la Protection des Données (RGPD).</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
