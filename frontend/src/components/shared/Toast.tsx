import { X } from 'lucide-react';
import { useToastStore } from '../../stores/toastStore';
import type { ToastMessage } from '../../types/api';

const typeStyles: Record<ToastMessage['type'], string> = {
  success: 'border-l-4 border-success bg-success/10',
  error: 'border-l-4 border-danger bg-danger/10',
  info: 'border-l-4 border-accent bg-accent/10',
  warning: 'border-l-4 border-warning bg-warning/10',
};

const iconMap: Record<ToastMessage['type'], string> = {
  success: '✓',
  error: '✕',
  info: 'ℹ',
  warning: '⚠',
};

function ToastItem({ toast }: { toast: ToastMessage }) {
  const dismiss = useToastStore((s) => s.dismissToast);

  return (
    <div
      className={`toast-enter flex items-start gap-3 px-4 py-3 rounded-lg shadow-lg min-w-[300px] max-w-[420px] ${typeStyles[toast.type]}`}
      style={{ background: 'var(--bg-elevated)' }}
    >
      <span className={`text-sm font-mono mt-0.5 ${
        toast.type === 'success' ? 'text-success'
        : toast.type === 'error' ? 'text-danger'
        : toast.type === 'warning' ? 'text-warning'
        : 'text-accent'
      }`}>
        {iconMap[toast.type]}
      </span>
      <p className="text-sm text-text-primary flex-1">{toast.message}</p>
      <button
        onClick={() => dismiss(toast.id)}
        className="text-text-secondary hover:text-text-primary transition-colors shrink-0"
      >
        <X size={14} />
      </button>
    </div>
  );
}

export function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none">
      {toasts.map((toast) => (
        <div key={toast.id} className="pointer-events-auto">
          <ToastItem toast={toast} />
        </div>
      ))}
    </div>
  );
}
