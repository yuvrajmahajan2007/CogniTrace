import React from 'react';

export default function StatCard({ title, value, subtitle, icon: Icon, loading = false, muted = false }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-sm hover:border-slate-300 transition-colors">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wider text-slate-500">
            {title}
          </p>
          <div className="mt-2 flex items-baseline gap-2">
            {loading ? (
              <div className="h-8 w-16 bg-slate-100 rounded animate-pulse" />
            ) : (
              <p className={`text-2xl font-semibold tracking-tight ${muted ? 'text-slate-400' : 'text-slate-900'}`}>
                {value}
              </p>
            )}
          </div>
          {subtitle && (
            <p className="mt-1.5 text-xs text-slate-500 truncate">{subtitle}</p>
          )}
        </div>
        {Icon && (
          <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200/70 text-slate-600 shrink-0">
            <Icon className="w-5 h-5" />
          </div>
        )}
      </div>
    </div>
  );
}
