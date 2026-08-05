import { memo } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  MessageSquare,
  FileText,
  PenLine,
  Briefcase,
  ChevronLeft,
  ChevronRight,
  SquarePen,
  Home,
} from 'lucide-react';
import { useUiStore } from '../../stores/uiStore';

const navItems = [
  { to: '/chat', label: 'Chat', icon: MessageSquare },
  { to: '/resume', label: 'Resume Tailor', icon: FileText },
  { to: '/cover-letter', label: 'Cover Letter', icon: PenLine },
  { to: '/interview', label: 'Interview Prep', icon: Briefcase },
];

interface SidebarProps {
  onNewChat?: () => void;
}

export const Sidebar = memo(function Sidebar({ onNewChat }: SidebarProps) {
  const { sidebarCollapsed, toggleSidebar, backendHealthy } = useUiStore();
  const navigate = useNavigate();

  const handleNewChat = () => {
    navigate('/chat');
    onNewChat?.();
  };

  return (
    <aside
      className="hidden lg:flex flex-col bg-bg-surface border-r border-border h-full transition-all duration-300"
      style={{ width: sidebarCollapsed ? '64px' : '240px' }}
    >
      {/* Logo */}
      <div className="h-14 flex items-center border-b border-border px-4 shrink-0">
        {sidebarCollapsed ? (
          <span className="text-xl font-bold text-accent font-mono">C</span>
        ) : (
          <span className="text-lg font-bold text-accent tracking-tight">CareerAI</span>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 flex flex-col gap-1 p-3">
        {/* Home / Landing */}
        <NavLink
          to="/"
          className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors text-sm ${
              isActive
                ? 'bg-accent/20 text-accent font-medium'
                : 'text-text-secondary hover:text-text-primary hover:bg-bg-elevated'
            }`
          }
        >
          <Home size={20} className="shrink-0" />
          {!sidebarCollapsed && <span>Home</span>}
        </NavLink>

        <div className="h-px bg-border my-2" />

        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors text-sm ${
                isActive
                  ? 'bg-accent/20 text-accent font-medium'
                  : 'text-text-secondary hover:text-text-primary hover:bg-bg-elevated'
              }`
            }
          >
            <item.icon size={20} className="shrink-0" />
            {!sidebarCollapsed && <span>{item.label}</span>}
          </NavLink>
        ))}

        {/* New Chat */}
        <button
          onClick={handleNewChat}
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors text-sm text-text-secondary hover:text-text-primary hover:bg-bg-elevated mt-2 border-t border-border pt-4"
        >
          <SquarePen size={20} className="shrink-0" />
          {!sidebarCollapsed && <span>New Chat</span>}
        </button>
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={toggleSidebar}
        className="flex items-center justify-center h-10 mx-3 mb-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-elevated transition-colors"
      >
        {sidebarCollapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
      </button>

      {/* Health dot */}
      <div className="px-4 py-3 border-t border-border flex items-center gap-2 shrink-0">
        <span
          className={`w-2 h-2 rounded-full shrink-0 ${
            backendHealthy ? 'bg-success' : 'bg-danger'
          }`}
        />
        {!sidebarCollapsed && (
          <span className="text-xs text-text-secondary">
            {backendHealthy ? 'Connected' : 'Disconnected'}
          </span>
        )}
      </div>
    </aside>
  );
});
