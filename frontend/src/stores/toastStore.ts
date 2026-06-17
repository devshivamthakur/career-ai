import { create } from 'zustand';
import type { ToastMessage } from '../types/api';

interface ToastState {
  toasts: ToastMessage[];
  showToast: (message: string, type: ToastMessage['type']) => void;
  dismissToast: (id: string) => void;
}

let toastId = 0;

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],

  showToast: (message, type) => {
    const id = String(++toastId);
    const toast: ToastMessage = { id, message, type };
    set((state) => ({ toasts: [...state.toasts, toast] }));

    // Auto-dismiss after 4 seconds
    setTimeout(() => {
      set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
    }, 4000);
  },

  dismissToast: (id) =>
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),
}));
