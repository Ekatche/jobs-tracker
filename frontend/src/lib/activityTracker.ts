import { removeToken, removeRefreshToken } from './auth';

const INACTIVITY_TIMEOUT = 30 * 60 * 1000; // 30 minutes en millisecondes
let inactivityTimer: NodeJS.Timeout | null = null;
let lastActivityTime: number = Date.now();
let lastUpdateTime = 0;
const UPDATE_THROTTLE = 5000; // 5 secondes

// Événements à surveiller pour détecter l'activité utilisateur
const activityEvents = [
  'mousedown',
  'mousemove',
  'keypress',
  'scroll',
  'touchstart',
  'click',
  'keydown'
];

const logout = () => {
  console.log("Inactivité détectée, déconnexion...");
  removeToken();
  removeRefreshToken();
  window.location.href = '/auth/login?session=expired';
};

export const startActivityTracking = () => {
  // Mettre à jour le temps d'activité
  const updateActivity = () => {
    const now = Date.now();
    // Limiter les mises à jour fréquentes
    if (now - lastUpdateTime < UPDATE_THROTTLE) {
      return;
    }
    
    lastUpdateTime = now;
    lastActivityTime = now;
    
    // Réinitialiser le timer d'inactivité
    if (inactivityTimer) {
      clearTimeout(inactivityTimer);
    }
    
    // Configurer un nouveau timer
    inactivityTimer = setTimeout(() => {
      // Si aucune activité n'est détectée pendant INACTIVITY_TIMEOUT
      console.log("Inactivité détectée, déconnexion...");
      removeToken();
      removeRefreshToken();
      window.location.href = '/auth/login?session=expired';
    }, INACTIVITY_TIMEOUT);
  };
  
  // Ajouter les écouteurs d'événements
  activityEvents.forEach(event => {
    window.addEventListener(event, updateActivity);
  });
  
  // Initialiser le timer
  updateActivity();
  
  // Retourner une fonction de nettoyage
  return () => {
    activityEvents.forEach(event => {
      window.removeEventListener(event, updateActivity);
    });
    
    if (inactivityTimer) {
      clearTimeout(inactivityTimer);
    }
  };
};

export const getLastActivityTime = () => {
  return lastActivityTime;
};