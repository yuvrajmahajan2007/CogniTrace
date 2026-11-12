import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  FileText,
  Download,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Sparkles,
  Clock,
  FileCode,
  Eye,
  CheckSquare,
} from 'lucide-react';
import {
  generateReport,
  listReports,
  getReport,
  getClaimStats,
  getReportDownloadUrl,
} from '../api/client';
import StatusBadge from '../components/StatusBadge';
import StatCard from '../components/StatCard';

function formatInline(text) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g);
  return parts.map((part, idx) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={idx} className="font-semibold text-slate-900">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code
          key={idx}
          className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 font-mono text-xs"
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
      return (
        <em key={idx} className="italic text-slate-500">
          {part.slice(1, -1)}
        </em>
      );
    }
    return part;
  });
}

function MarkdownPreview({ content }) {
  const lines = (content || '').split(/\r?\n/);
  return (
    <div className="space-y-2 text-sm text-slate-700 leading-relaxed">
      {lines.map((line, i) => {
        if (!line.trim()) return <div key={i} className="h-1.5" />;
        if (line.startsWith('# ')) {
          return (
            <h2
              key={i}
              className="text-lg font-bold text-slate-900 pb-2 border-b border-slate-200"
            >
              {line.slice(2)}
            </h2>
          );
        }
        if (line.startsWith('## ')) {
          return (
            <h3
              key={i}
              className="text-sm font-semibold uppercase tracking-wider text-navy-800 pt-3 pb-1 border-b border-slate-100"
            >
              {line.slice(3)}
            </h3>
          );
        }
        if (line.startsWith('### ')) {
          return (
            <h4
              key={i}
              className="text-xs font-semibold text-slate-700 pt-2"
            >
              {line.slice(4)}
            </h4>
          );
        }
        if (line.startsWith('  - ')) {
          return (
            <div key={i} className="pl-6 text-xs text-slate-500 flex items-start gap-2">
              <span className="text-slate-400">&bull;</span>
              <span>{formatInline(line.slice(4))}</span>
            </div>
          );
        }
        if (line.startsWith('- ')) {
          return (
            <div key={i} className="pl-2 flex items-start gap-2">
              <span className="text-navy-700 font-bold">&bull;</span>
              <span>{formatInline(line.slice(2))}</span>
            </div>
          );
        }
        return <p key={i}>{formatInline(line)}</p>;
      })}
    </div>
  );
}

export default function HandoverReports() {
  const [reports, setReports] = useState([]);
  const [selectedReport, setSelectedReport] = useState(null);
  const [claimStats, setClaimStats] = useState({
    approved_claims: 0,
    pending_claims: 0,
    rejected_claims: 0,
    unresolved_conflicts: 0,
  });
  const [titleInput, setTitleInput] = useState('CogniTrace Project Handover Report');
  const [rawMode, setRawMode] = useState(false);

  const [loading, setLoading] = useState(true);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');
  const [feedback, setFeedback] = useState('');

  const selectReportById = useCallback(async (reportId) => {
    setLoadingPreview(true);
    try {
      const detail = await getReport(reportId);
      setSelectedReport(detail);
    } catch (err) {
      setError(err.message || 'Failed to load report preview');
    } finally {
      setLoadingPreview(false);
    }
  }, []);

  const loadReports = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [reportsList, stats] = await Promise.all([
        listReports(),
        getClaimStats(),
      ]);
      setReports(reportsList);
      setClaimStats(stats);

      if (reportsList.length > 0) {
        await selectReportById(reportsList[0].id);
      } else {
        setSelectedReport(null);
      }
    } catch (err) {
      setError(err.message || 'Failed to load handover reports');
    } finally {
      setLoading(false);
    }
  }, [selectReportById]);

  useEffect(() => {
    loadReports();
  }, [loadReports]);

  const handleGenerate = async (e) => {
    e.preventDefault();
    setGenerating(true);
    setError('');
    setFeedback('');
    try {
      const created = await generateReport(titleInput);
      setFeedback(
        `Generated "${created.title}" with ${created.approved_claims_count} approved claim(s).`
      );
      const updatedList = await listReports();
      setReports(updatedList);
      setSelectedReport(created);
    } catch (err) {
      setError(err.message || 'Failed to generate handover report');
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold text-slate-900">
            Handover Reports
          </h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Generate, preview, and download evidence-linked handover reports from human-approved claims only.
          </p>
        </div>
        <button
          type="button"
          onClick={loadReports}
          disabled={loading}
          className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded-lg border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Readiness Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Approved Claims Ready"
          value={claimStats.approved_claims}
          subtitle="Included in generated reports"
          loading={loading}
        />
        <StatCard
          title="Excluded Pending/Rejected"
          value={claimStats.pending_claims + claimStats.rejected_claims}
          subtitle={`${claimStats.pending_claims} pending, ${claimStats.rejected_claims} rejected`}
          loading={loading}
        />
        <StatCard
          title="Unresolved Conflicts"
          value={claimStats.unresolved_conflicts}
          subtitle="Separated into Conflicts section"
          loading={loading}
        />
        <StatCard
          title="Generated Reports"
          value={reports.length}
          subtitle="Persisted in SQLite"
          loading={loading}
        />
      </div>

      {/* Generate Report Form */}
      <form
        onSubmit={handleGenerate}
        className="bg-white rounded-xl border border-slate-200/80 shadow-sm p-5 flex flex-col sm:flex-row items-stretch sm:items-end gap-3"
      >
        <div className="flex-1">
          <label
            htmlFor="reportTitle"
            className="block text-xs font-medium text-slate-600 mb-1.5"
          >
            Report Title
          </label>
          <input
            id="reportTitle"
            type="text"
            value={titleInput}
            onChange={(e) => setTitleInput(e.target.value)}
            placeholder="CogniTrace Project Handover Report"
            className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent"
          />
        </div>
        <button
          type="submit"
          disabled={generating}
          className="inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-navy-900 text-white hover:bg-navy-800 disabled:opacity-50 transition-colors"
        >
          <Sparkles className="w-4 h-4" />
          {generating ? 'Generating...' : 'Generate Handover Report'}
        </button>
      </form>

      {/* Feedback & Error Alerts */}
      {feedback && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 flex items-start gap-2.5 text-xs text-emerald-900">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
          <span>{feedback}</span>
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 flex items-start gap-2.5 text-xs text-rose-800">
          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {/* History + Preview Split */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Report History */}
        <div className="bg-white rounded-xl border border-slate-200/80 shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-200/80 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-navy-700" />
              <h3 className="text-sm font-semibold text-slate-900">
                Report History ({reports.length})
              </h3>
            </div>
          </div>

          {loading ? (
            <div className="p-6 text-center text-xs text-slate-500">
              Loading report history...
            </div>
          ) : reports.length === 0 ? (
            <div className="p-8 text-center">
              <FileText className="w-8 h-8 text-slate-300 mx-auto mb-2" />
              <p className="text-xs font-medium text-slate-700">
                No reports generated yet
              </p>
              <p className="text-xs text-slate-500 mt-1">
                Click "Generate Handover Report" above to compile approved claims.
              </p>
            </div>
          ) : (
            <ul className="divide-y divide-slate-100 max-h-[540px] overflow-y-auto">
              {reports.map((rep) => {
                const isSelected = selectedReport?.id === rep.id;
                return (
                  <li key={rep.id}>
                    <button
                      type="button"
                      onClick={() => selectReportById(rep.id)}
                      className={`w-full text-left px-5 py-3.5 transition-colors ${
                        isSelected
                          ? 'bg-slate-100/90 border-l-4 border-l-navy-900'
                          : 'hover:bg-slate-50'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-semibold text-slate-800 truncate">
                          #{rep.id} {rep.title}
                        </span>
                        <StatusBadge
                          status="completed"
                          label={`${rep.approved_claims_count} claims`}
                        />
                      </div>
                      <p className="text-[11px] text-slate-500 mt-1">
                        {new Date(rep.created_at).toLocaleString()} &middot;{' '}
                        {rep.source_files_count} source doc(s)
                      </p>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* Report Preview */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200/80 shadow-sm overflow-hidden flex flex-col">
          <div className="px-5 py-4 border-b border-slate-200/80 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 min-w-0">
              <FileText className="w-4 h-4 text-navy-700 shrink-0" />
              <h3 className="text-sm font-semibold text-slate-900 truncate">
                {selectedReport
                  ? `Preview: ${selectedReport.title}`
                  : 'Report Preview'}
              </h3>
            </div>

            {selectedReport && (
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => setRawMode((v) => !v)}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50"
                >
                  {rawMode ? (
                    <>
                      <Eye className="w-3.5 h-3.5" />
                      Formatted
                    </>
                  ) : (
                    <>
                      <FileCode className="w-3.5 h-3.5" />
                      Raw Markdown
                    </>
                  )}
                </button>

                <a
                  href={getReportDownloadUrl(selectedReport.id, 'markdown')}
                  download
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                >
                  <Download className="w-3.5 h-3.5" />
                  Markdown (.md)
                </a>

                <a
                  href={getReportDownloadUrl(selectedReport.id, 'pdf')}
                  download
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-navy-900 text-white hover:bg-navy-800"
                >
                  <Download className="w-3.5 h-3.5" />
                  Download PDF
                </a>
              </div>
            )}
          </div>

          <div className="p-6 flex-1 overflow-y-auto max-h-[600px]">
            {loadingPreview ? (
              <div className="py-12 text-center text-sm text-slate-500">
                Loading report preview...
              </div>
            ) : !selectedReport ? (
              <div className="py-14 text-center">
                <CheckSquare className="w-9 h-9 text-slate-300 mx-auto mb-3" />
                <p className="text-sm font-medium text-slate-800">
                  No handover report selected
                </p>
                <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
                  Approve verified claims in{' '}
                  <Link to="/claims" className="text-accent-dark underline">
                    Claim Verification
                  </Link>{' '}
                  and click "Generate Handover Report" to create downloadable Markdown and PDF deliverables.
                </p>
              </div>
            ) : rawMode ? (
              <pre className="whitespace-pre-wrap font-mono text-xs text-slate-700 bg-slate-50 p-4 rounded-lg border border-slate-200">
                {selectedReport.markdown_content}
              </pre>
            ) : (
              <MarkdownPreview content={selectedReport.markdown_content} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
