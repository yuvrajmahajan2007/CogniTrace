import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  UploadCloud,
  Search,
  CheckSquare,
  FileText,
  Settings,
  Layers,
  X,
} from 'lucide-react';
import { API_BASE_URL } from '../api/client';

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/upload', label: 'Upload Documents', icon: UploadCloud },
  { to: '/evidence', label: 'Evidence Explorer', icon: Search },
  { to: '/claims', label: 'Claim Verification', icon: CheckSquare },
  { to: '/reports', label: 'Handover Reports', icon: FileText },
  { to: '/settings', label: 'Settings', icon: Settings },
];

export default function Sidebar({ backendStatus, isOpen, onClose }) {
  const statusColor =
    backendStatus === 'connected'
      ? 'bg-emerald-400'
      : backendStatus === 'checking'
      ? 'bg-amber-400'
      : 'bg-rose-400';

  const statusText =
    backendStatus === 'connected'
      ? 'Connected'
      : backendStatus === 'checking'
      ? 'Checking...'
      : 'Unreachable';

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-30 bg-slate-900/50 lg:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-40 w-64 bg-navy-900 text-slate-200 flex flex-col border-r border-navy-800 transition-transform duration-200 lg:static lg:translate-x-0 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Brand Header */}
        <div className="h-16 px-5 flex items-center justify-between border-b border-navy-800">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center text-white shadow-sm">
              <Layers className="w-4 h-4" />
            </div>
            <div>
              <span className="font-semibold text-white tracking-tight text-base block leading-none">
                CogniTrace
              </span>
              <span className="text-[11px] text-navy-200 tracking-wide mt-1 block">
                Handover Intelligence
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="lg:hidden p-1 rounded text-navy-200 hover:text-white hover:bg-navy-800"
            aria-label="Close navigation"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          <div className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-wider text-navy-300">
            Workspace
          </div>
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={onClose}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-navy-700/80 text-white border border-navy-600/60'
                    : 'text-navy-100 hover:bg-navy-800 hover:text-white border border-transparent'
                }`
              }
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        {/* Backend Health Footer */}
        <div className="p-4 border-t border-navy-800">
          <div className="rounded-lg bg-navy-950/60 border border-navy-800 px-3 py-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-navy-200">Backend API</span>
              <span className="inline-flex items-center gap-1.5 text-xs font-medium text-white">
                <span className={`w-2 h-2 rounded-full ${statusColor}`} />
                {statusText}
              </span>
            </div>
            <p className="text-[11px] font-mono text-navy-300 mt-1 truncate">
              {API_BASE_URL || 'Proxied API (/api)'}
            </p>
          </div>
        </div>
      </aside>
    </>
  );
}
