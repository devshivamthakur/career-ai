import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { BottomNav } from './BottomNav';
import { ToastContainer } from '../shared/Toast';
import { useHealthCheck } from '../../hooks/useHealthCheck';
import { useChatSession } from '../../hooks/useChatSession';

export function Shell() {
  useHealthCheck();
  const { clearSession } = useChatSession();

  return (
    <div className="flex h-full w-full">
      {/* Sidebar — desktop */}
      <Sidebar onNewChat={clearSession} />

      {/* Main content area */}
      <div className="flex-1 flex flex-col min-w-0 h-full">
        <TopBar onClearChat={clearSession} />

        <main className="flex-1 overflow-hidden pb-16 lg:pb-0">
          <Outlet />
        </main>

        {/* Mobile bottom nav */}
        <BottomNav />
      </div>

      {/* Global toast container */}
      <ToastContainer />
    </div>
  );
}
