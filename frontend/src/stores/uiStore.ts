import { create } from 'zustand';

interface UiState {
  sidebarCollapsed: boolean;
  backendHealthy: boolean;

  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  setBackendHealth: (healthy: boolean) => void;
}

const SIDEBAR_KEY = 'careerAI_sidebar_collapsed';

function getInitialSidebar(): boolean {
  try {
    const stored = localStorage.getItem(SIDEBAR_KEY);
    if (stored !== null) return JSON.parse(stored);
  } catch {
    // ignore
  }
  return window.innerWidth < 1024;
}

export const useUiStore = create<UiState>((set) => ({
  sidebarCollapsed: getInitialSidebar(),
  backendHealthy: false,

  toggleSidebar: () =>
    set((state) => {
      const next = !state.sidebarCollapsed;
      localStorage.setItem(SIDEBAR_KEY, JSON.stringify(next));
      return { sidebarCollapsed: next };
    }),

  setSidebarCollapsed: (collapsed) => {
    localStorage.setItem(SIDEBAR_KEY, JSON.stringify(collapsed));
    set({ sidebarCollapsed: collapsed });
  },

  setBackendHealth: (healthy) => set({ backendHealthy: healthy }),
}));
