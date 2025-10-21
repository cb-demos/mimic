/**
 * Global application state store using Zustand
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface AppState {
  // UI State
  drawerOpen: boolean;
  setDrawerOpen: (open: boolean) => void;
  toggleDrawer: () => void;

  // Current Environment
  currentEnvironment: string | null;
  setCurrentEnvironment: (env: string | null) => void;
}

/**
 * Main application store with persistence
 */
export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      // UI state
      drawerOpen: true,
      setDrawerOpen: (open) => set({ drawerOpen: open }),
      toggleDrawer: () => set((state) => ({ drawerOpen: !state.drawerOpen })),

      // Environment state
      currentEnvironment: null,
      setCurrentEnvironment: (env) => set({ currentEnvironment: env }),
    }),
    {
      name: 'mimic-app-store', // localStorage key
      partialize: (state) => ({
        // Only persist these values
        drawerOpen: state.drawerOpen,
      }),
    }
  )
);
