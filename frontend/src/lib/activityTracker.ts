import { removeToken, removeRefreshToken } from './auth';

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

// Démarre le tracking de l'activité utilisateur
export const startActivityTracking = () => {
  const updateActivity = () => {
    const now = Date.now();
    // Throttle pour limiter la fréquence des MAJ
    if (now - lastUpdateTime < UPDATE_THROTTLE) {
      return;
    }
    lastUpdateTime = now;
    lastActivityTime = now;
  };

  // Enregistre les écouteurs
  activityEvents.forEach(event => {
    window.addEventListener(event, updateActivity);
  });

  // MAJ initiale
  updateActivity();

  // Nettoyage
  return () => {
    activityEvents.forEach(event => {
      window.removeEventListener(event, updateActivity);
    });
  };
};

// Récupère le timestamp de la dernière activité
export const getLastActivityTime = () => lastActivityTime;