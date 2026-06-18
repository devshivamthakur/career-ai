import { memo } from 'react';
import { NavLink } from 'react-router-dom';
import { MessageSquare, FileText, PenLine, Briefcase } from 'lucide-react';

const tabs = [
  { to: '/chat', label: 'Chat', icon: MessageSquare },
  { to: '/resume', label: 'Resume', icon: FileText },
  { to: '/cover-letter', label: 'Letter', icon: PenLine },
  { to: '/interview', label: 'Interview', icon: Briefcase },
];

export const BottomNav = memo(function BottomNav() {
  return (
    <nav className="lg:hidden fixed bottom-0 left-0 right-0 z-50 bg-bg-surface border-t border-border">
      <div className="flex items-center justify-around h-16">
        {tabs.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            className={({ isActive }) =>
              `flex flex-col items-center gap-1 px-3 py-2 transition-colors ${
                isActive
                  ? 'text-accent'
                  : 'text-text-secondary hover:text-text-primary'
              }`
            }
          >
            <tab.icon size={20} />
            <span className="text-xs font-medium">{tab.label}</span>
          </NavLink>
        ))}
      </div>
    </nav>
  );
});
