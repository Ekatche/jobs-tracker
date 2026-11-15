import Link from "next/link";
import {
  FiLock,
  FiDatabase,
  FiUserCheck,
  FiEyeOff,
  FiTrash2,
  FiHelpCircle,
} from "react-icons/fi";

const FAQ_ITEMS = [
  {
    q: "Est-ce adapté si je n'envoie que quelques candidatures par mois ?",
    a: "Oui, tout à fait. Même avec 2 ou 3 candidatures actives, le suivi permet de retrouver immédiatement les détails exacts d'une offre lors d'un premier appel téléphonique ou pour savoir quand relancer sans hésiter.",
  },
  {
    q: "Mon employeur actuel peut-il voir mes démarches ?",
    a: "Non. Votre espace MonSuiviJob est strictement individuel et hermétique. Il n'existe aucun annuaire public de profils ni d'accès recruteur à vos données.",
  },
  {
    q: "Comment démarrer concrètement ?",
    a: "Vous créez votre compte en quelques secondes, puis vous ajoutez manuellement ou collez le lien de votre première candidature. Si vous le souhaitez, vous pouvez aussi importer votre CV pour faciliter vos rédactions.",
  },
  {
    q: "D'où proviennent les offres d'emploi affichées sur la plateforme ?",
    a: "Les offres sont indexées directement depuis les sites carrières officiels des entreprises (via leurs logiciels de recrutement directs comme Greenhouse, Lever, Ashby, Workable...) et complétées par les principales plateformes de l'emploi. Cela vous garantit des offres réelles, à jour, sans intermédiaires inutiles.",
  },
  {
    q: "Dois-je lancer une recherche manuellement tous les jours ?",
    a: "Non, c'est tout l'intérêt du système : une fois vos préférences de recherche renseignées dans votre profil (métiers, localisation, télétravail), le moteur veille automatiquement pour vous et met à jour votre catalogue sans que vous ayez à cliquer sur un bouton.",
  },
];

export default function LandingRgpdFaqFooter() {
  return (
    <>
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
              Une recherche d&apos;emploi implique des informations hautement personnelles
              (parcours, CV, coordonnées, rémunération). Notre modèle garantit une étanchéité
              complète.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800">
              <div className="w-10 h-10 rounded-lg bg-emerald-900/30 text-emerald-400 flex items-center justify-center mb-4">
                <FiEyeOff className="text-xl" />
              </div>
              <h4 className="font-bold text-white text-sm mb-2">Zéro revente de données</h4>
              <p className="text-xs text-slate-300 leading-relaxed">
                Vos démarches, CV et coordonnées ne sont jamais vendus ni cédés à des tiers, régies
                ou démarcheurs.
              </p>
            </div>

            <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800">
              <div className="w-10 h-10 rounded-lg bg-blue-900/30 text-blue-400 flex items-center justify-center mb-4">
                <FiDatabase className="text-xl" />
              </div>
              <h4 className="font-bold text-white text-sm mb-2">Hébergement sécurisé UE</h4>
              <p className="text-xs text-slate-300 leading-relaxed">
                Vos informations sont traitées selon les normes européennes et chiffrées en transit
                comme au repos.
              </p>
            </div>

            <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800">
              <div className="w-10 h-10 rounded-lg bg-amber-900/30 text-amber-400 flex items-center justify-center mb-4">
                <FiTrash2 className="text-xl" />
              </div>
              <h4 className="font-bold text-white text-sm mb-2">Droit à l&apos;oubli en 1 clic</h4>
              <p className="text-xs text-slate-300 leading-relaxed">
                Vous pouvez exporter l&apos;ensemble de vos données ou supprimer définitivement votre
                compte à tout moment.
              </p>
            </div>

            <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800">
              <div className="w-10 h-10 rounded-lg bg-indigo-900/30 text-indigo-400 flex items-center justify-center mb-4">
                <FiUserCheck className="text-xl" />
              </div>
              <h4 className="font-bold text-white text-sm mb-2">Contrôle intégral</h4>
              <p className="text-xs text-slate-300 leading-relaxed">
                Les suggestions fournies sont consultatives : aucun envoi de candidature ne
                s&apos;effectue sans votre action directe.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="py-16 md:py-20 bg-slate-900/30 border-b border-slate-800/80">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
              Questions fréquentes
            </h2>
            <p className="mt-2 text-slate-400 text-sm">
              Quelques éclaircissements pour démarrer l&apos;esprit tranquille.
            </p>
          </div>

          <div className="space-y-4">
            {FAQ_ITEMS.map(({ q, a }) => (
              <div key={q} className="p-5 rounded-xl bg-slate-900/80 border border-slate-800">
                <div className="flex items-start gap-3">
                  <FiHelpCircle className="text-blue-400 text-lg mt-0.5 shrink-0" />
                  <div>
                    <h4 className="text-sm sm:text-base font-semibold text-white">{q}</h4>
                    <p className="mt-1.5 text-xs sm:text-sm text-slate-300 leading-relaxed">
                      {a}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

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
                Offres d&apos;emploi
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
            <p>
              © {new Date().getFullYear()} MonSuiviJob. Conçu avec respect pour les candidats et la
              vie privée.
            </p>
            <p>Conforme au Règlement Général sur la Protection des Données (RGPD).</p>
          </div>
        </div>
      </footer>
    </>
  );
}
