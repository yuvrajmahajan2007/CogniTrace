import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  FileText,
  Database,
  Clock,
  CheckCircle2,
  UploadCloud,
  Search,
  ArrowRight,
  RefreshCw,
  AlertCircle,
  Globe,
  Unlock,
  Shield,
} from 'lucide-react';
import { listFiles, getFileContent, getClaimStats } from '../api/client';
import StatCard from '../components/StatCard';
import StatusBadge from '../components/StatusBadge';

function formatBytes(bytes) {
  if (!bytes && bytes !== 0) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function formatDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function DashboardOverview() {
  const [files, setFiles] = useState([]);
  const [totalChunks, setTotalChunks] = useState(0);
  const [claimStats, setClaimStats] = useState({
    total_claims: 0,
    pending_claims: 0,
    approved_claims: 0,
    rejected_claims: 0,
    unresolved_conflicts: 0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadOverview = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [fileList, stats] = await Promise.all([
        listFiles(),
        getClaimStats().catch(() => null),
      ]);
      setFiles(fileList);
      if (stats) {
        setClaimStats(stats);
      }

      const completedFiles = fileList.filter((f) => f.status === 'completed');
      if (completedFiles.length > 0) {
        const chunkArrays = await Promise.all(
          completedFiles.map((f) => getFileContent(f.id).catch(() => []))
        );
        const sum = chunkArrays.reduce((acc, arr) => acc + arr.length, 0);
        setTotalChunks(sum);
      } else {
        setTotalChunks(0);
      }
    } catch (err) {
      setError(err.message || 'Unable to load dashboard data from backend');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadOverview();
  }, [loadOverview]);

  const completedCount = files.filter((f) => f.status === 'completed').length;
  const failedCount = files.filter((f) => f.status === 'failed').length;
  const recentFiles = [...files].sort(
    (a, b) => new Date(b.uploaded_at) - new Date(a.uploaded_at)
  ).slice(0, 6);

  return (
    <div className="space-y-6">
      {/* Header Row */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold text-slate-900">
            Project Handover Overview
          </h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Live ingestion metrics and evidence extraction status from the CogniTrace backend.
          </p>
        </div>
        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={loadOverview}
            disabled={loading}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded-lg border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-50 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <Link
            to="/upload"
            className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium rounded-lg bg-navy-900 text-white hover:bg-navy-800 transition-colors"
          >
            <UploadCloud className="w-3.5 h-3.5" />
            Upload Documents
          </Link>
        </div>
      </div>

      {/* Open Access & Future Scalability Banner */}
      <div className="bg-white rounded-xl border border-slate-200/80 shadow-sm overflow-hidden">
        <div className="grid grid-cols-1 lg:grid-cols-3 divide-y lg:divide-y-0 lg:divide-x divide-slate-200/80">
          {/* Open Access — Judge Evaluation */}
          <div className="lg:col-span-2 p-5 flex items-start gap-3.5">
            <div className="p-2.5 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-700 shrink-0">
              <Globe className="w-5 h-5" />
            </div>
            <div className="min-w-0 space-y-1.5">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-sm font-semibold text-slate-900">
                  Open Access — Judge Evaluation
                </h3>
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                  <Unlock className="w-3 h-3" />
                  Public Demo
                </span>
              </div>
              <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
                CogniTrace is openly accessible for hackathon judges. No login or registration is required. Feel free to explore document ingestion, evidence verification, claim review and handover report generation.
              </p>
            </div>
          </div>

          {/* Future Scalability */}
          <div className="p-5 bg-slate-50/70 flex items-start gap-3">
            <div className="p-2 rounded-lg bg-white border border-slate-200 text-slate-500 shrink-0">
              <Shield className="w-4 h-4" />
            </div>
            <div className="min-w-0 space-y-1">
              <div className="flex items-center gap-2">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-700">
                  Future Scalability
                </h3>
              </div>
              <p className="text-xs text-slate-500 leading-relaxed">
                CogniTrace can also be extended into a login-based platform with secure user authentication, team access and role-based permissions for organizational use.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 flex items-start gap-3 text-sm text-rose-800">
          <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="font-medium">Failed to load project metrics</p>
            <p className="text-xs text-rose-700 mt-0.5">{error}</p>
          </div>
          <button
            type="button"
            onClick={loadOverview}
            className="text-xs font-medium underline hover:no-underline"
          >
            Retry
          </button>
        </div>
      )}

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          title="Uploaded Documents"
          value={files.length}
          subtitle={
            files.length === 0
              ? 'No documents uploaded yet'
              : `${completedCount} parsed${failedCount ? `, ${failedCount} failed` : ''}`
          }
          icon={FileText}
          loading={loading}
        />
        <StatCard
          title="Extracted Evidence Chunks"
          value={totalChunks}
          subtitle={
            totalChunks > 0
              ? `Across ${completedCount} parsed document${completedCount === 1 ? '' : 's'}`
              : 'Upload and parse documents to extract chunks'
          }
          icon={Database}
          loading={loading}
        />
        <StatCard
          title="Claims Awaiting Verification"
          value={claimStats.pending_claims}
          subtitle={
            claimStats.total_claims === 0
              ? 'Run claim generation to extract claims'
              : `${claimStats.total_claims} total (${claimStats.unresolved_conflicts} conflict flags)`
          }
          icon={Clock}
          loading={loading}
        />
        <StatCard
          title="Approved Claims"
          value={claimStats.approved_claims}
          subtitle={
            claimStats.rejected_claims > 0
              ? `${claimStats.rejected_claims} rejected by reviewer`
              : 'Human-verified project knowledge'
          }
          icon={CheckCircle2}
          loading={loading}
        />
      </div>

      {/* Two-Column Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Documents */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200/80 shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-200/80 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">
                Recent Uploaded Documents
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Stored in SQLite via <code className="font-mono">/api/files</code>
              </p>
            </div>
            <Link
              to="/upload"
              className="text-xs font-medium text-accent-dark hover:underline inline-flex items-center gap-1"
            >
              Manage all
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          {loading ? (
            <div className="p-8 text-center text-sm text-slate-500">
              Loading documents...
            </div>
          ) : recentFiles.length === 0 ? (
            <div className="p-10 text-center">
              <div className="w-10 h-10 rounded-full bg-slate-100 text-slate-400 flex items-center justify-center mx-auto mb-3">
                <FileText className="w-5 h-5" />
              </div>
              <p className="text-sm font-medium text-slate-700">
                No documents uploaded yet
              </p>
              <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                Upload project PDFs, DOCX files, meeting notes, CSVs, or JSON exports to begin extracting traceable evidence.
              </p>
              <Link
                to="/upload"
                className="mt-4 inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium rounded-lg bg-navy-900 text-white hover:bg-navy-800 transition-colors"
              >
                <UploadCloud className="w-3.5 h-3.5" />
                Upload First Document
              </Link>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50/80 text-xs uppercase text-slate-500 border-b border-slate-200/80">
                  <tr>
                    <th className="px-5 py-3 font-medium">Document</th>
                    <th className="px-4 py-3 font-medium">Size</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-5 py-3 font-medium text-right">Uploaded</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {recentFiles.map((file) => (
                    <tr key={file.id} className="hover:bg-slate-50/60 transition-colors">
                      <td className="px-5 py-3 font-medium text-slate-800 max-w-[220px] truncate">
                        {file.filename}
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-500 whitespace-nowrap">
                        {formatBytes(file.size_bytes)}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <StatusBadge status={file.status} />
                      </td>
                      <td className="px-5 py-3 text-xs text-slate-500 text-right whitespace-nowrap">
                        {formatDate(file.uploaded_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Workflow Pipeline Status */}
        <div className="bg-white rounded-xl border border-slate-200/80 shadow-sm p-5 flex flex-col justify-between space-y-5">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">
              Handover Pipeline Status
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Current MVP module readiness
            </p>

            <div className="mt-4 space-y-3">
              <div className="p-3 rounded-lg border border-emerald-200 bg-emerald-50/50">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-emerald-900">
                    Phase 1: Document Ingestion
                  </span>
                  <StatusBadge status="completed" label="Active" />
                </div>
                <p className="text-xs text-emerald-800/80 mt-1">
                  Upload, parse, chunk, and inspect PDF, DOCX, TXT, MD, CSV, and JSON files.
                </p>
              </div>

              <div className="p-3 rounded-lg border border-emerald-200 bg-emerald-50/50">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-emerald-900">
                    Phase 2: Claim Extraction & Review
                  </span>
                  <StatusBadge status="completed" label="Active" />
                </div>
                <p className="text-xs text-emerald-800/80 mt-1">
                  Rule-based claim generation, conflict detection, and human approval workflow.
                </p>
              </div>

              <div className="p-3 rounded-lg border border-emerald-200 bg-emerald-50/50">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-emerald-900">
                    Phase 3: Handover Report Export
                  </span>
                  <StatusBadge status="completed" label="Active" />
                </div>
                <p className="text-xs text-emerald-800/80 mt-1">
                  Compile approved claims with source citations into Markdown and PDF reports.
                </p>
              </div>
            </div>
          </div>

          <div className="pt-3 border-t border-slate-100 flex items-center justify-between">
            <Link
              to="/evidence"
              className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-700 hover:text-navy-900"
            >
              <Search className="w-3.5 h-3.5" />
              Explore Evidence Chunks
            </Link>
            <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
          </div>
        </div>
      </div>
    </div>
  );
}
