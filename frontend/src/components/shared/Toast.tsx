import { memo } from 'react';
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from 'lucide-react';
import { useToastStore } from '../../stores/toastStore';
import type { ToastMessage } from '../../types/api';

const typeConfig: Record<ToastMessage['type'], {
  icon: typeof CheckCircle;
  iconColor: string;
  bgSoft: string;
  borderColor: string;
}> = {
  success: { icon: CheckCircle, iconColor: 'text-success', bgSoft: 'bg-success/10', borderColor: 'border-success' },
  error: { icon: AlertCircle, iconColor: 'text-danger', bgSoft: 'bg-danger/10', borderColor: 'border-danger' },
  info: { icon: Info, iconColor: 'text-info', bgSoft: 'bg-info/10', borderColor: 'border-info' },
  warning: { icon: AlertTriangle, iconColor: 'text-warning', bgSoft: 'bg-warning/10', borderColor: 'border-warning' },
};

const ToastItem = memo(function ToastItem({ toast }: { toast: ToastMessage }) {
  const dismiss = useToastStore((s) => s.dismissToast);
  const config = typeConfig[toast.type];
  const Icon = config.icon;

  return (
    <div
      className={`toast-enter flex items-start gap-3 px-4 py-3 rounded-lg shadow-lg min-w-[300px] max-w-[420px] border-l-4 ${config.borderColor} ${config.bgSoft}`}
      style={{ background: 'var(--bg-elevated)' }}
    >
      <Icon size={16} className={`${config.iconColor} mt-0.5 shrink-0`} />
      <p className="text-sm text-text-primary flex-1">{toast.message}</p>
      <button
        onClick={() => dismiss(toast.id)}
        className="text-text-tertiary hover:text-text-primary transition-colors shrink-0"
      >
        <X size={14} />
      </button>
    </div>
  );
});

export const ToastContainer = memo(function ToastContainer() {
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
});
