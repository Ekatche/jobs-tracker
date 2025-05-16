"use client";

import {
  FiCheckCircle,
  FiAlertCircle,
  FiInfo,
  FiAlertTriangle,
  FiX,
} from "react-icons/fi";
import { useNotification } from "@/contexts/NotificationContext";

// Types pour les notifications
type NotificationType = "success" | "error" | "info" | "warning";

// Interface pour un objet notification
interface NotificationItem {
  id: string;
  type: NotificationType;
  message: string;
}

// Interface locale pour le contexte avec removeNotification
interface ExtendedNotificationContext {
  notifications: NotificationItem[];
  removeNotification: (id: string) => void;
}

export default function NotificationContainer() {
  // Utilisez type casting vers l'interface locale
  const { notifications, removeNotification } =
    useNotification() as ExtendedNotificationContext;

  // Fonction pour obtenir l'icône selon le type
  const getIcon = (type: NotificationType) => {
    switch (type) {
      case "success":
        return <FiCheckCircle className="h-5 w-5" />;
      case "error":
        return <FiAlertCircle className="h-5 w-5" />;
      case "info":
        return <FiInfo className="h-5 w-5" />;
      case "warning":
        return <FiAlertTriangle className="h-5 w-5" />;
      default:
        return <FiInfo className="h-5 w-5" />;
    }
  };

  // Fonction pour obtenir les couleurs selon le type
  const getColors = (type: NotificationType) => {
    switch (type) {
      case "success":
        return "bg-green-900/40 border-green-600 text-green-200";
      case "error":
        return "bg-red-900/40 border-red-600 text-red-200";
      case "info":
        return "bg-blue-900/40 border-blue-600 text-blue-200";
      case "warning":
        return "bg-amber-900/40 border-amber-600 text-amber-200";
      default:
        return "bg-gray-800 border-gray-700 text-gray-200";
    }
  };

  if (notifications.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col space-y-2 max-w-md">
      {notifications.map((notification) => (
        <div
          key={notification.id}
          className={`p-4 rounded-md shadow-lg border ${getColors(notification.type)} flex items-start animate-slide-up`}
        >
          <div className="flex-shrink-0 mr-3">{getIcon(notification.type)}</div>
          <div className="flex-1 mr-2">
            <p>{notification.message}</p>
          </div>
          <button
            onClick={() => removeNotification(notification.id)}
            className="flex-shrink-0 text-gray-400 hover:text-white transition-colors"
          >
            <FiX className="h-5 w-5" />
          </button>
        </div>
      ))}
    </div>
  );
}
