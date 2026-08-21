import { create } from "zustand";

const STORAGE_KEY = "pos_cafeteria_auth";

function loadStoredAuth() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { token: null, user: null };
    const parsed = JSON.parse(raw);
    return {
      token: parsed.token ?? null,
      user: parsed.user ?? null,
    };
  } catch {
    return { token: null, user: null };
  }
}

function persistAuth(token, user) {
  if (token && user) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ token, user }));
  } else {
    localStorage.removeItem(STORAGE_KEY);
  }
}

const initial = loadStoredAuth();

export const useAuthStore = create((set) => ({
  token: initial.token,
  user: initial.user,
  authReady: false,

  login: (token, user) => {
    persistAuth(token, user);
    set({ token, user, authReady: true });
  },

  logout: () => {
    persistAuth(null, null);
    set({ token: null, user: null, authReady: true });
  },

  setAuthReady: (ready) => set({ authReady: ready }),
}));

window.authStore = useAuthStore;
