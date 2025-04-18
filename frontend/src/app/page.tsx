import { FiCheck, FiFilter, FiList } from 'react-icons/fi';

export default function Home() {
  return (
    <div className="min-h-screen bg-blue-night text-white">
      {/* Section héro avec dégradé subtil */}
      <section className="relative overflow-hidden py-20">
        {/* Cercles décoratifs d'arrière-plan */}
        <div className="absolute -top-24 -right-24 w-96 h-96 rounded-full bg-blue-500 opacity-10 blur-3xl"></div>
        <div className="absolute bottom-0 left-20 w-80 h-80 rounded-full bg-indigo-600 opacity-10 blur-3xl"></div>
        
        <div className="container mx-auto px-4 relative z-10">
          <div className="max-w-3xl mx-auto text-center">
            <h1 className="text-4xl md:text-5xl font-bold text-white mb-6 leading-tight">
              Simplifiez le suivi de vos candidatures
            </h1>
            <p className="text-xl text-gray-300 mb-10 leading-relaxed">
              Une application simple qui vous permet de centraliser et suivre toutes vos candidatures 
              envoyées à différentes entreprises via différents sites d'emploi.
            </p>
          </div>
        </div>
      </section>

      {/* Section fonctionnalités */}
      <section className="bg-blue-night-lighter py-20">
        <div className="container mx-auto px-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="bg-blue-night p-8 rounded-xl shadow-md hover:shadow-lg transition-shadow border border-gray-800">
              <div className="bg-blue-900/30 w-12 h-12 flex items-center justify-center rounded-full mb-4">
                <FiList className="text-xl text-blue-400" />
              </div>
              <h3 className="text-xl font-semibold text-white mb-3">Centralisation</h3>
              <p className="text-gray-300 leading-relaxed">
                Regroupez toutes vos candidatures au même endroit, quelle que soit la plateforme d'emploi utilisée.
              </p>
            </div>
            <div className="bg-blue-night p-8 rounded-xl shadow-md hover:shadow-lg transition-shadow border border-gray-800">
              <div className="bg-blue-900/30 w-12 h-12 flex items-center justify-center rounded-full mb-4">
                <FiFilter className="text-xl text-blue-400" />
              </div>
              <h3 className="text-xl font-semibold text-white mb-3">Organisation</h3>
              <p className="text-gray-300 leading-relaxed">
                Triez et filtrez vos candidatures par statut, entreprise ou date pour une visibilité optimale.
              </p>
            </div>
            <div className="bg-blue-night p-8 rounded-xl shadow-md hover:shadow-lg transition-shadow border border-gray-800">
              <div className="bg-blue-900/30 w-12 h-12 flex items-center justify-center rounded-full mb-4">
                <FiCheck className="text-xl text-blue-400" />
              </div>
              <h3 className="text-xl font-semibold text-white mb-3">Suivi efficace</h3>
              <p className="text-gray-300 leading-relaxed">
                Suivez l'évolution de chaque candidature et ne manquez plus aucun retour ou entretien.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
