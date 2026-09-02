import { jwtDecode } from "jwt-decode"; // Importation correcte
import Cookies from "js-cookie";
import axios from "axios";

export interface User {
  id: string;
  username: string;
  email: string;
  full_name: string | null;
}

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface RegisterCredentials {
  username: string;
  email: string;
  password: string;
  full_name?: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function login(credentials: LoginCredentials) {
  try {
    const formData = new FormData();
    formData.append("username", credentials.username);
    formData.append("password", credentials.password);

    const response = await axios.post(`${API_URL}/auth/token`, formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });

    // Assurez-vous que le token est correctement enregistré
    Cookies.set("token", response.data.access_token, { expires: 1 });

    return response.data;
  } catch (error) {
    // Gestion d'erreur...
  }
}

export async function register(credentials: RegisterCredentials) {
  const response = await fetch(`${API_URL}/auth/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(credentials),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to register");
  }

  return await response.json();
}

export async function logout() {
  Cookies.remove("token");
  removeRefreshToken();
}

export function getToken() {
  return Cookies.get("token");
}

interface JwtPayload {
  exp: number;
  sub: string;
  // Add other JWT claims as needed
}

export function isAuthenticated() {
  const token = getToken();
  console.log("Token:", token); // Debugging line
  if (!token) return false;

  try {
    const decoded: JwtPayload = jwtDecode(token);
    const currentTime = Date.now() / 1000;
    return decoded.exp > currentTime;
  } catch {
    return false;
  }
}

export async function getCurrentUser(): Promise<User | null> {
  const token = getToken();
  if (!token) return null;

  try {
    const response = await fetch(`${API_URL}/auth/me`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      throw new Error("Failed to get user");
    }

    return await response.json();
  } catch {
    return null;
  }
}

// Ajouter ces fonctions si elles ne sont pas déjà définies
export function removeToken() {
  Cookies.remove("token");
}

const REFRESH_TOKEN_KEY = "refreshToken";
const REMEMBER_ME_KEY = "rememberMe";

/**
 * "Se souvenir de moi" : le refresh token va dans localStorage (survit à la
 * fermeture du navigateur) plutôt que sessionStorage (effacé à la fermeture).
 */
export function setRememberMe(remember: boolean) {
  if (remember) {
    localStorage.setItem(REMEMBER_ME_KEY, "1");
  } else {
    localStorage.removeItem(REMEMBER_ME_KEY);
  }
}

export function getRememberMe(): boolean {
  return localStorage.getItem(REMEMBER_ME_KEY) === "1";
}

function getRefreshTokenStorage(): Storage {
  return getRememberMe() ? localStorage : sessionStorage;
}

export function removeRefreshToken() {
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  sessionStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(REMEMBER_ME_KEY);
}

export function setRefreshToken(token: string) {
  getRefreshTokenStorage().setItem(REFRESH_TOKEN_KEY, token);
}

export function getRefreshToken() {
  return getRefreshTokenStorage().getItem(REFRESH_TOKEN_KEY);
}

/**
 * Enregistre le jeton d'authentification dans un cookie
 * @param token Le jeton JWT à stocker
 * @param expireInDays Durée de validité du cookie en jours (par défaut: 1 jour)
 */
export function setToken(token: string, expireInDays: number = 1) {
  Cookies.set("token", token, { expires: expireInDays });
}
