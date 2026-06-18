import { memo, useState, useRef, useEffect } from 'react';

interface ConfirmPopoverProps {
  trigger: React.ReactNode;
  title?: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  variant?: 'danger' | 'default';
}

export const ConfirmPopover = memo(function ConfirmPopover({
  trigger,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  onConfirm,
  variant = 'default',
}: ConfirmPopoverProps) {
  const [isOpen, setIsOpen] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (e: MouseEvent) => {
      if (
        popoverRef.current &&
        !popoverRef.current.contains(e.target as Node) &&
        triggerRef.current &&
        !triggerRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsOpen(false);
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKey);
    };
  }, [isOpen]);

  return (
    <div className="relative inline-block">
      <div ref={triggerRef} onClick={() => setIsOpen(!isOpen)}>
        {trigger}
      </div>

      {isOpen && (
        <div
          ref={popoverRef}
          className="absolute right-0 top-full mt-2 z-50 min-w-[260px]"
        >
          <div className="bg-bg-elevated border border-border rounded-lg shadow-xl p-4">
            {title && (
              <p className="text-sm font-semibold text-text-primary mb-1">{title}</p>
            )}
            <p className="text-sm text-text-secondary mb-4">{message}</p>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setIsOpen(false)}
                className="px-3 py-1.5 text-sm text-text-secondary hover:text-text-primary transition-colors rounded-md hover:bg-bg-base"
              >
                {cancelLabel}
              </button>
              <button
                onClick={() => {
                  onConfirm();
                  setIsOpen(false);
                }}
                className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                  variant === 'danger'
                    ? 'bg-danger/20 text-danger hover:bg-danger/30'
                    : 'bg-accent/20 text-accent hover:bg-accent/30'
                }`}
              >
                {confirmLabel}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
});
