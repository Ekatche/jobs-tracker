'use client';

import React, { createContext, useContext, useState, ReactNode } from 'react';
import { FiCheck, FiAlertTriangle, FiX } from 'react-icons/fi';

type NotificationType = 'success' | 'error' | 'info';

interface Notification {
  type: NotificationType;
  message: string;
}

interface NotificationItem extends Notification {
  id: string;
}

interface NotificationContextType {
  notifications: NotificationItem[];
  addNotification: (type: NotificationType, message: string) => void;
  removeNotification: (id: string) => void;
}

const NotificationContext = createContext<NotificationContextType | null>(null);

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);

  const addNotification = (type: NotificationType, message: string) => {
    const id = new Date().getTime().toString();
    setNotifications(prev => [...prev, { id, type, message }]);
    setTimeout(() => {
      removeNotification(id);
    }, 3000);
  };

  const removeNotification = (id: string) => {
    setNotifications(prev => prev.filter(notification => notification.id !== id));
  };

  return (
    <NotificationContext.Provider value={{ 
      notifications, 
      addNotification, 
      removeNotification 
    }}>
      {children}
      {notifications.map(notification => (
        <div key={notification.id} className="fixed bottom-4 right-4 z-50">
          <div className={`p-4 rounded-md shadow-lg flex items-center ${
            notification.type === 'success' ? 'bg-green-900/90 text-green-200 border border-green-600' :
            notification.type === 'error' ? 'bg-red-900/90 text-red-200 border border-red-600' :
            'bg-blue-900/90 text-blue-200 border border-blue-600'
          }`}>
            {notification.type === 'success' && <FiCheck className="mr-2" />}
            {notification.type === 'error' && <FiAlertTriangle className="mr-2" />}
            <span>{notification.message}</span>
            <button onClick={() => removeNotification(notification.id)} className="ml-4 text-gray-400 hover:text-white">
              <FiX />
            </button>
          </div>
        </div>
      ))}
    </NotificationContext.Provider>
  );
}

export function useNotification() {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotification must be used within a NotificationProvider');
  }
  return context;
}