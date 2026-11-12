import React from 'react';

const STATUS_STYLES = {
  completed: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  approved: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  connected: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  processing: 'bg-blue-50 text-blue-700 border-blue-200',
  pending: 'bg-amber-50 text-amber-700 border-amber-200',
  failed: 'bg-rose-50 text-rose-700 border-rose-200',
  rejected: 'bg-rose-50 text-rose-700 border-rose-200',
  unreachable: 'bg-rose-50 text-rose-700 border-rose-200',
  checking: 'bg-slate-100 text-slate-600 border-slate-200',
  unavailable: 'bg-slate-100 text-slate-600 border-slate-200',
};

const DOT_STYLES = {
  completed: 'bg-emerald-500',
  approved: 'bg-emerald-500',
  connected: 'bg-emerald-500',
  processing: 'bg-blue-500',
  pending: 'bg-amber-500',
  failed: 'bg-rose-500',
  rejected: 'bg-rose-500',
  unreachable: 'bg-rose-500',
  checking: 'bg-slate-400',
  unavailable: 'bg-slate-400',
};

export default function StatusBadge({ status, label }) {
  const key = (status || '').toLowerCase();
  const badgeClass = STATUS_STYLES[key] || 'bg-slate-100 text-slate-700 border-slate-200';
  const dotClass = DOT_STYLES[key] || 'bg-slate-400';

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${badgeClass}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${dotClass}`} />
      {label || status}
    </span>
  );
}
