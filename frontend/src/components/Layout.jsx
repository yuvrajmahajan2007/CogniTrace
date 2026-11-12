import React, { useState } from 'react';
import { Menu, RefreshCw } from 'lucide-react';
import Sidebar from './Sidebar';
import StatusBadge from './StatusBadge';

export default function Layout({
  title,
  subtitle,
  backendStatus,
  onRetryHealth,
  children,
}) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen flex bg-surface text-slate-800">
      <Sidebar
        backendStatus={backendStatus}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Bar */}
        <header className="h-16 bg-white border-b border-slate-200/80 px-4 sm:px-6 lg:px-8 flex items-center justify-between sticky top-0 z-20">
          <div className="flex items-center gap-3 min-w-0">
            <button
              type="button"
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden p-2 rounded-lg text-slate-600 hover:bg-slate-100"
              aria-label="Open navigation"
            >
              <Menu className="w-5 h-5" />
            </button>
            <div className="min-w-0">
              <h1 className="text-base sm:text-lg font-semibold text-slate-900 truncate">
                {title}
              </h1>
              {subtitle && (
                <p className="text-xs text-slate-500 truncate hidden sm:block">
                  {subtitle}
                </p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <StatusBadge
              status={backendStatus}
              label={`Backend: ${backendStatus === 'connected' ? 'Connected' : backendStatus === 'checking' ? 'Checking' : 'Unreachable'}`}
            />
            {backendStatus !== 'connected' && onRetryHealth && (
              <button
                type="button"
                onClick={onRetryHealth}
                className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 transition-colors"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                Retry
              </button>
            )}
          </div>
        </header>

        {/* Backend Unreachable Banner */}
        {backendStatus === 'unreachable' && (
          <div className="bg-rose-50 border-b border-rose-200 px-4 sm:px-6 lg:px-8 py-2.5">
            <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-2 text-xs text-rose-800">
              <span>
                Unable to reach the CogniTrace backend at{' '}
                <code className="font-mono bg-rose-100 px-1 py-0.5 rounded">
                  http://127.0.0.1:8000
                </code>
                . Ensure the FastAPI server is running.
              </span>
              {onRetryHealth && (
                <button
                  type="button"
                  onClick={onRetryHealth}
                  className="font-medium underline hover:no-underline"
                >
                  Check connection
                </button>
              )}
            </div>
          </div>
        )}

        {/* Main Content */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8">
          <div className="max-w-7xl mx-auto">{children}</div>
        </main>
      </div>
    </div>
  );
}
