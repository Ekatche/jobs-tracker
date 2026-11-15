import Link from "next/link";
import {
  FiBriefcase,
  FiShield,
  FiCheckCircle,
  FiFileText,
  FiSearch,
  FiArrowRight,
  FiCalendar,
  FiLayers,
  FiFilter,
  FiTarget,
  FiRefreshCw,
} from "react-icons/fi";

export default function LandingToolsAndPipeline() {
  return (
    <>
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
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-6 sm:p-7 hover:border-slate-700 transition-colors">
              <div className="w-12 h-12 rounded-xl bg-blue-900/30 border border-blue-700/40 flex items-center justify-center mb-5 text-blue-400">
                <FiBriefcase className="text-2xl" />
              </div>
              <h3 className="text-lg font-bold text-white mb-2">
                1. Le Carnet de bord des candidatures
              </h3>
              <p className="text-sm text-slate-300 leading-relaxed mb-4">
                Regroupez au même endroit toutes les annonces auxquelles vous avez répondu, quel que
                soit le site d&apos;origine. Chaque fiche conserve l&apos;annonce originale, la date
                d&apos;envoi et vos notes.
              </p>
              <div className="pt-3 border-t border-slate-800 text-xs text-slate-400 flex items-center gap-2">
                <FiCheckCircle className="text-emerald-400 shrink-0" />
                <span>
                  Bénéfice : Quand un recruteur vous appelle, vous retrouvez le contexte en 5
                  secondes.
                </span>
              </div>
            </div>

            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-6 sm:p-7 hover:border-slate-700 transition-colors">
              <div className="w-12 h-12 rounded-xl bg-indigo-900/30 border border-indigo-700/40 flex items-center justify-center mb-5 text-indigo-400">
                <FiFileText className="text-2xl" />
              </div>
              <h3 className="text-lg font-bold text-white mb-2">
                2. L&apos;Assistant de préparation ciblée
              </h3>
              <p className="text-sm text-slate-300 leading-relaxed mb-4">
                Une aide pour reformuler vos lettres de motivation et messages d&apos;accroche en
                mettant en valeur vos expériences réelles face aux critères demandés par
                l&apos;entreprise.
              </p>
              <div className="pt-3 border-t border-slate-800 text-xs text-slate-400 flex items-center gap-2">
                <FiCheckCircle className="text-emerald-400 shrink-0" />
                <span>
                  Bénéfice : Aucune phrase générique, vous gardez la main sur le texte final.
                </span>
              </div>
            </div>

            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-6 sm:p-7 hover:border-slate-700 transition-colors">
              <div className="w-12 h-12 rounded-xl bg-teal-900/30 border border-teal-700/40 flex items-center justify-center mb-5 text-teal-400">
                <FiSearch className="text-2xl" />
              </div>
              <h3 className="text-lg font-bold text-white mb-2">
                3. Le Radar d&apos;opportunités sans bruit
              </h3>
              <p className="text-sm text-slate-300 leading-relaxed mb-4">
                Consultez des offres d&apos;emploi qualifiées selon vos souhaits précis
                (localisation, télétravail, type de contrat) sans vous perdre dans des centaines de
                notifications inutiles.
              </p>
              <div className="pt-3 border-t border-slate-800 text-xs text-slate-400 flex items-center gap-2">
                <FiCheckCircle className="text-emerald-400 shrink-0" />
                <span>
                  Bénéfice : Une lecture rapide des critères clés pour décider si l&apos;offre vaut
                  votre temps.
                </span>
              </div>
            </div>

            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-6 sm:p-7 hover:border-slate-700 transition-colors">
              <div className="w-12 h-12 rounded-xl bg-amber-900/30 border border-amber-700/40 flex items-center justify-center mb-5 text-amber-400">
                <FiCalendar className="text-2xl" />
              </div>
              <h3 className="text-lg font-bold text-white mb-2">
                4. L&apos;Échéancier de relance courtoise
              </h3>
              <p className="text-sm text-slate-300 leading-relaxed mb-4">
                Un rappel temporel bien dosé (généralement 7 à 12 jours après l&apos;envoi) pour vous
                indiquer le bon moment pour recontacter l&apos;entreprise avec professionnalisme.
              </p>
              <div className="pt-3 border-t border-slate-800 text-xs text-slate-400 flex items-center gap-2">
                <FiCheckCircle className="text-emerald-400 shrink-0" />
                <span>
                  Bénéfice : Ne plus jamais laisser une opportunité s&apos;éteindre par simple
                  oubli.
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="py-16 md:py-24 bg-slate-950/70 border-b border-slate-800/80">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto mb-14">
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs sm:text-sm font-medium bg-blue-900/30 border border-blue-700/50 text-blue-300 mb-4 shadow-sm">
              <FiSearch className="text-blue-400" />
              <span>Transparence &amp; Simplicité • Zéro boîte noire</span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
              Comment fonctionne notre recherche &amp; veille d&apos;offres ?
            </h2>
            <p className="mt-3 text-slate-300 text-sm sm:text-base leading-relaxed">
              Fini de passer 2 heures par jour à écumer manuellement 15 plateformes différentes.
              Découvrez comment notre moteur sélectionne, filtre et organise les meilleures
              opportunités pour vous.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {[
              {
                step: "Étape 01",
                title: "Veille directe & multi-sources",
                body: "Le système scrute en continu les espaces carrières officiels des entreprises (Greenhouse, Lever, Ashby, Workable...) ainsi que les principales plateformes de l'emploi en fonction de vos métiers cibles, localisations et critères de télétravail.",
                foot: "Accès direct aux offres à la source",
                Icon: FiLayers,
                box: "bg-blue-900/30 border-blue-700/40 text-blue-400",
                pill: "text-blue-400/80 bg-blue-950/80 border-blue-800/40",
              },
              {
                step: "Étape 02",
                title: "Nettoyage & Déduplication",
                body: "Une même annonce multi-diffusée sur plusieurs sites est instantanément reconnue et regroupée en une fiche unique. Les titres et descriptions sont épurés des balises parasites et des mentions légales encombrantes.",
                foot: "Zéro doublon, lecture nette et fluide",
                Icon: FiFilter,
                box: "bg-indigo-900/30 border-indigo-700/40 text-indigo-400",
                pill: "text-indigo-400/80 bg-indigo-950/80 border-indigo-800/40",
              },
              {
                step: "Étape 03",
                title: "Décryptage d'adéquation",
                body: "Les exigences clés (compétences réelles, responsabilités, niveau d'expérience requis) sont synthétisées clairement. Vous comprenez en 30 secondes ce que le recruteur recherche sans devoir lire des pavés de texte.",
                foot: "Points forts & signaux d'attention",
                Icon: FiTarget,
                box: "bg-teal-900/30 border-teal-700/40 text-teal-400",
                pill: "text-teal-400/80 bg-teal-950/80 border-teal-800/40",
              },
              {
                step: "Étape 04",
                title: "Pilotage 100 % automatique",
                body: "La veille s'exécute de façon autonome et programmée en arrière-plan. Vous recevez directement les opportunités qualifiées dans votre espace sans avoir à relancer manuellement de requêtes.",
                foot: "Mise à jour régulière sans effort",
                Icon: FiRefreshCw,
                box: "bg-amber-900/30 border-amber-700/40 text-amber-400",
                pill: "text-amber-400/80 bg-amber-950/80 border-amber-800/40",
              },
            ].map(({ step, title, body, foot, Icon, box, pill }) => (
              <div
                key={step}
                className="relative bg-slate-900/90 border border-slate-800 rounded-2xl p-6 flex flex-col justify-between hover:border-slate-700 transition-all hover:-translate-y-1"
              >
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <div
                      className={`w-12 h-12 rounded-xl border flex items-center justify-center ${box}`}
                    >
                      <Icon className="text-2xl" />
                    </div>
                    <span
                      className={`text-xs font-mono font-bold px-2.5 py-1 rounded-md border ${pill}`}
                    >
                      {step}
                    </span>
                  </div>
                  <h3 className="text-base font-bold text-white mb-2">{title}</h3>
                  <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">{body}</p>
                </div>
                <div className="mt-5 pt-3 border-t border-slate-800 text-[11px] text-slate-400 flex items-center gap-1.5">
                  <FiCheckCircle className="text-emerald-400 shrink-0 text-xs" />
                  <span>{foot}</span>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-10 p-5 rounded-2xl bg-gradient-to-r from-blue-900/20 via-indigo-900/20 to-teal-900/20 border border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400 shrink-0">
                <FiShield className="text-xl" />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-white">
                  Isolation &amp; Confidentialité garantie
                </h4>
                <p className="text-xs text-slate-400">
                  Chaque candidat dispose de ses propres critères de recherche et de ses données
                  privées. Vos interactions (offres sauvegardées, candidatures, lettres et CVs)
                  restent strictement confidentielles.
                </p>
              </div>
            </div>
            <Link
              href="/offers"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600/90 hover:bg-blue-600 text-white text-xs font-medium transition-colors shrink-0"
            >
              <span>Voir le catalogue d&apos;offres</span>
              <FiArrowRight />
            </Link>
          </div>
        </div>
      </section>
    </>
  );
}
