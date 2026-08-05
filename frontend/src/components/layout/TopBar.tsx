import { memo } from 'react';
import { useLocation, Link } from 'react-router-dom';
import { Trash2, Sparkles } from 'lucide-react';
import { ConfirmPopover } from '../shared/ConfirmPopover';

const pageNames: Record<string, string> = {
  '/chat': 'Chat',
  '/resume': 'Resume Tailor',
  '/cover-letter': 'Cover Letter',
  '/interview': 'Interview Prep',
};

interface TopBarProps {
  onClearChat?: () => void;
}

export const TopBar = memo(function TopBar({ onClearChat }: TopBarProps) {
  const location = useLocation();
  const pageName = pageNames[location.pathname] ?? 'CareerAI';
  const isChat = location.pathname === '/chat';

  return (
    <header className="h-14 flex items-center justify-between px-6 border-b border-border bg-bg-surface shrink-0">
      <div className="flex items-center gap-3">
        <Link to="/" className="flex items-center gap-1.5 text-text-secondary hover:text-accent transition-colors">
          <Sparkles size={16} />
        </Link>
        <span className="text-text-tertiary">/</span>
        <h1 className="text-base font-semibold text-text-primary">{pageName}</h1>
      </div>

      <div className="flex items-center gap-3">
        {isChat && onClearChat && (
          <ConfirmPopover
            message="This will clear your chat history. Continue?"
            confirmLabel="Clear"
            variant="danger"
            onConfirm={onClearChat}
            trigger={
              <button className="flex items-center gap-1.5 text-xs text-text-secondary hover:text-danger transition-colors px-2 py-1 rounded-md hover:bg-danger/10">
                <Trash2 size={14} />
                <span>Clear Chat</span>
              </button>
            }
          />
        )}
      </div>
    </header>
  );
});
