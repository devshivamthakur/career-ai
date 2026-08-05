import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Shell } from './components/layout/Shell';
import LandingPage from './pages/LandingPage';

const ChatPage = lazy(() => import('./pages/ChatPage'));
const ResumePage = lazy(() => import('./pages/ResumePage'));
const CoverLetterPage = lazy(() => import('./pages/CoverLetterPage'));
const InterviewPage = lazy(() => import('./pages/InterviewPage'));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 10000),
      staleTime: 30000,
      refetchOnWindowFocus: false,
    },
  },
});

function PageFallback() {
  return (
    <div className="flex items-center justify-center h-full">
      <div className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Suspense fallback={<PageFallback />}>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route element={<Shell />}>
              <Route path="/chat" element={<ChatPage />} />
              <Route path="/resume" element={<ResumePage />} />
              <Route path="/cover-letter" element={<CoverLetterPage />} />
              <Route path="/interview" element={<InterviewPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
