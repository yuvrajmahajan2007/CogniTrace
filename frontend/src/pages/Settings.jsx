import React from 'react';
import { Server, ExternalLink, RefreshCw, ShieldCheck, FileCheck } from 'lucide-react';
import StatusBadge from '../components/StatusBadge';
import { API_BASE_URL } from '../api/client';

export default function Settings({ backendStatus, onRetryHealth }) {
  const frontendOrigin =
    typeof window !== 'undefined' ? window.location.origin : '';
  const backendTarget = API_BASE_URL || `${frontendOrigin} (via proxy)`;
  const docsUrl = API_BASE_URL
    ? `${API_BASE_URL}/docs`
    : typeof window !== 'undefined'
    ? `${window.location.protocol}//${window.location.hostname}:8000/docs`
    : '/docs';
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-slate-900">Settings</h2>
        <p className="text-sm text-slate-500 mt-0.5">
          System configuration, backend connectivity, and extraction pipeline settings.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Backend Connection Card */}
        <div className="bg-white rounded-xl border border-slate-200/80 shadow-sm p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <Server className="w-4 h-4 text-navy-700" />
              <h3 className="text-sm font-semibold text-slate-900">
                Backend Connectivity
              </h3>
            </div>
            <StatusBadge
              status={backendStatus}
              label={
                backendStatus === 'connected'
                  ? 'Connected'
                  : backendStatus === 'checking'
                  ? 'Checking'
                  : 'Unreachable'
              }
            />
          </div>

          <dl className="divide-y divide-slate-100 text-xs">
            <div className="py-2.5 flex justify-between gap-4">
              <dt className="text-slate-500">Frontend Origin</dt>
              <dd className="font-mono text-slate-800">{frontendOrigin || '—'}</dd>
            </div>
            <div className="py-2.5 flex justify-between gap-4">
              <dt className="text-slate-500">Backend API Target</dt>
              <dd className="font-mono text-slate-800">{backendTarget}</dd>
            </div>
            <div className="py-2.5 flex justify-between gap-4">
              <dt className="text-slate-500">Health Endpoint</dt>
              <dd className="font-mono text-slate-800">GET /health</dd>
            </div>
          </dl>

          <div className="pt-2 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={onRetryHealth}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Test Connection
            </button>
            <a
              href={docsUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-navy-900 text-white hover:bg-navy-800"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              Open Swagger API Docs
            </a>
          </div>
        </div>

        {/* Ingestion Rules Card */}
        <div className="bg-white rounded-xl border border-slate-200/80 shadow-sm p-6 space-y-4">
          <div className="flex items-center gap-2.5">
            <FileCheck className="w-4 h-4 text-navy-700" />
            <h3 className="text-sm font-semibold text-slate-900">
              Document Ingestion Policy
            </h3>
          </div>

          <dl className="divide-y divide-slate-100 text-xs">
            <div className="py-2.5 flex justify-between gap-4">
              <dt className="text-slate-500">Supported Formats</dt>
              <dd className="font-mono text-slate-800">
                PDF, DOCX, TXT, MD, CSV, JSON
              </dd>
            </div>
            <div className="py-2.5 flex justify-between gap-4">
              <dt className="text-slate-500">Max File Size</dt>
              <dd className="font-mono text-slate-800">20 MB per file</dd>
            </div>
            <div className="py-2.5 flex justify-between gap-4">
              <dt className="text-slate-500">Evidence Chunk Size</dt>
              <dd className="font-mono text-slate-800">1,000 characters</dd>
            </div>
            <div className="py-2.5 flex justify-between gap-4">
              <dt className="text-slate-500">Database</dt>
              <dd className="font-mono text-slate-800">SQLite (cognitrace.db)</dd>
            </div>
          </dl>
        </div>

        {/* Extraction Mode Card */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200/80 shadow-sm p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <ShieldCheck className="w-4 h-4 text-navy-700" />
              <h3 className="text-sm font-semibold text-slate-900">
                Structured Claim Extraction (Phase 2)
              </h3>
            </div>
            <StatusBadge status="pending" label="Upcoming" />
          </div>
          <p className="text-xs text-slate-500 mt-2">
            Optional Gemini AI extraction with deterministic rule-based fallback will be configurable here once Phase 2 claim extraction endpoints are added to the backend. Human approval remains mandatory before any claim enters a final handover report.
          </p>
        </div>
      </div>
    </div>
  );
}
