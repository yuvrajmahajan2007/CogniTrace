import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Sparkles,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Edit3,
  Save,
  X,
  FileText,
  MapPin,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  History,
  UploadCloud,
  AlertCircle,
} from 'lucide-react';
import {
  generateClaims,
  listClaims,
  updateClaim,
  listConflicts,
  getClaimStats,
} from '../api/client';
import StatusBadge from '../components/StatusBadge';
import StatCard from '../components/StatCard';

const CLAIM_TYPE_LABELS = {
  technology: 'Technology',
  architecture_decision: 'Architecture Decision',
  completed_feature: 'Completed Feature',
  pending_feature: 'Pending Feature',
  blocker_risk: 'Blocker / Risk',
  dependency: 'Dependency',
  todo_fixme: 'TODO / FIXME',
  project_decision: 'Project Decision',
};

const CLAIM_TYPE_STYLES = {
  technology: 'bg-indigo-50 text-indigo-700 border-indigo-200',
  architecture_decision: 'bg-purple-50 text-purple-700 border-purple-200',
  completed_feature: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  pending_feature: 'bg-amber-50 text-amber-700 border-amber-200',
  blocker_risk: 'bg-rose-50 text-rose-700 border-rose-200',
  dependency: 'bg-sky-50 text-sky-700 border-sky-200',
  todo_fixme: 'bg-orange-50 text-orange-700 border-orange-200',
  project_decision: 'bg-slate-100 text-slate-700 border-slate-300',
};

function isIncompleteFragment(text) {
  const s = (text || '').trim();
  if (s.length < 28) return true;
  if (/^[a-z]/.test(s)) return true;
  if (/[,;:-]$/.test(s)) return true;
  if (s === s.toUpperCase() && s.length < 60) return true;
  return false;
}

export default function ClaimVerification() {
  const [claims, setClaims] = useState([]);
  const [conflicts, setConflicts] = useState([]);
  const [stats, setStats] = useState({
    total_claims: 0,
    pending_claims: 0,
    approved_claims: 0,
    rejected_claims: 0,
    total_conflicts: 0,
    unresolved_conflicts: 0,
    insufficient_evidence_count: 0,
  });

  const [statusFilter, setStatusFilter] = useState('all');
  const [typeFilter, setTypeFilter] = useState('all');
  const [useGemini, setUseGemini] = useState(false);

  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');
  const [feedback, setFeedback] = useState(null);

  // Per-claim UI state
  const [expandedEvidence, setExpandedEvidence] = useState({});
  const [expandedHistory, setExpandedHistory] = useState({});
  const [editingId, setEditingId] = useState(null);
  const [editText, setEditText] = useState('');
  const [comments, setComments] = useState({});
  const [savingId, setSavingId] = useState(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [claimsData, statsData, conflictsData] = await Promise.all([
        listClaims({ status: statusFilter, claim_type: typeFilter }),
        getClaimStats(),
        listConflicts(),
      ]);
      setClaims(claimsData);
      setStats(statsData);
      setConflicts(conflictsData);
    } catch (err) {
      setError(err.message || 'Failed to load claims from backend');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, typeFilter]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleGenerate = async () => {
    setGenerating(true);
    setFeedback(null);
    setError('');
    try {
      const res = await generateClaims({ use_gemini: useGemini });
      setFeedback({ type: 'success', message: res.message });
      await loadData();
    } catch (err) {
      setError(err.message || 'Failed to generate claims');
    } finally {
      setGenerating(false);
    }
  };

  const handleAction = async (claimId, newStatus) => {
    setSavingId(claimId);
    setError('');
    try {
      const comment = comments[claimId] || '';
      await updateClaim(claimId, {
        status: newStatus,
        comment: comment.trim() || undefined,
      });
      setComments((prev) => ({ ...prev, [claimId]: '' }));
      await loadData();
    } catch (err) {
      setError(err.message || 'Failed to save reviewer decision');
    } finally {
      setSavingId(null);
    }
  };

  const startEdit = (claim) => {
    setEditingId(claim.id);
    setEditText(claim.claim_text);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditText('');
  };

  const saveEdit = async (claimId) => {
    if (!editText.trim()) return;
    setSavingId(claimId);
    setError('');
    try {
      const comment = comments[claimId] || '';
      await updateClaim(claimId, {
        claim_text: editText.trim(),
        comment: comment.trim() || undefined,
      });
      setEditingId(null);
      setEditText('');
      setComments((prev) => ({ ...prev, [claimId]: '' }));
      await loadData();
    } catch (err) {
      setError(err.message || 'Failed to save claim edit');
    } finally {
      setSavingId(null);
    }
  };

  const toggleEvidence = (id) => {
    setExpandedEvidence((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const toggleHistory = (id) => {
    setExpandedHistory((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="space-y-6">
      {/* Header & Generate Controls */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold text-slate-900">
            Claim Verification
          </h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Generate evidence-linked claims from parsed documents, inspect citations, and record human decisions.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <label className="inline-flex items-center gap-2 text-xs text-slate-600 bg-white px-3 py-2 rounded-lg border border-slate-200 cursor-pointer">
            <input
              type="checkbox"
              checked={useGemini}
              onChange={(e) => setUseGemini(e.target.checked)}
              className="rounded border-slate-300 text-navy-900 focus:ring-navy-900"
            />
            <span>Optional Gemini AI (rule-based fallback)</span>
          </label>

          <button
            type="button"
            onClick={loadData}
            disabled={loading}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded-lg border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>

          <button
            type="button"
            onClick={handleGenerate}
            disabled={generating}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-medium rounded-lg bg-navy-900 text-white hover:bg-navy-800 disabled:opacity-50 transition-colors"
          >
            <Sparkles className="w-3.5 h-3.5" />
            {generating ? 'Generating Claims...' : 'Generate Candidate Claims'}
          </button>
        </div>
      </div>

      {/* Feedback & Errors */}
      {feedback && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 flex items-start gap-3 text-xs text-emerald-900">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
          <span>{feedback.message}</span>
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 flex items-start gap-3 text-xs text-rose-800">
          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard
          title="Total Claims"
          value={stats.total_claims}
          subtitle="Evidence-linked"
          loading={loading}
        />
        <StatCard
          title="Pending Review"
          value={stats.pending_claims}
          subtitle="Awaiting human decision"
          loading={loading}
        />
        <StatCard
          title="Approved"
          value={stats.approved_claims}
          subtitle="Verified for handover"
          loading={loading}
        />
        <StatCard
          title="Rejected"
          value={stats.rejected_claims}
          subtitle="Excluded from report"
          loading={loading}
        />
        <StatCard
          title="Potential Conflicts"
          value={stats.total_conflicts}
          subtitle={`${stats.insufficient_evidence_count} brief/ambiguous`}
          loading={loading}
        />
      </div>

      {/* Conflicts & Missing Evidence Panel */}
      {conflicts.length > 0 && (
        <div className="bg-amber-50/70 rounded-xl border border-amber-200 p-5 space-y-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-700" />
            <h3 className="text-sm font-semibold text-amber-950">
              Flagged Contradictions & Evidence Warnings ({conflicts.length})
            </h3>
          </div>
          <div className="space-y-2.5">
            {conflicts.map((flag) => (
              <div
                key={flag.id}
                className="bg-white rounded-lg border border-amber-200/80 p-3.5 text-xs space-y-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold uppercase tracking-wider text-[11px] text-amber-800">
                    {flag.conflict_type === 'contradiction'
                      ? 'Potential Contradiction'
                      : 'Insufficient Supporting Evidence'}
                  </span>
                </div>
                <p className="text-slate-700">{flag.description}</p>
                {flag.claim_a && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2 pt-1">
                    <div className="p-2 rounded bg-slate-50 border border-slate-200">
                      <span className="font-medium text-slate-600 block mb-0.5">
                        Claim #{flag.claim_a.id} ({flag.claim_a.source_filename})
                      </span>
                      <span className="text-slate-800">{flag.claim_a.claim_text}</span>
                    </div>
                    {flag.claim_b && (
                      <div className="p-2 rounded bg-slate-50 border border-slate-200">
                        <span className="font-medium text-slate-600 block mb-0.5">
                          Claim #{flag.claim_b.id} ({flag.claim_b.source_filename})
                        </span>
                        <span className="text-slate-800">{flag.claim_b.claim_text}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filter Bar */}
      <div className="bg-white rounded-xl border border-slate-200/80 shadow-sm p-4 flex flex-col sm:flex-row gap-3 items-center justify-between">
        <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
          {['all', 'pending', 'approved', 'rejected'].map((st) => (
            <button
              key={st}
              type="button"
              onClick={() => setStatusFilter(st)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-colors ${
                statusFilter === st
                  ? 'bg-navy-900 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {st}
            </button>
          ))}
        </div>

        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="w-full sm:w-56 px-3 py-1.5 text-xs rounded-lg border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-accent/20"
        >
          <option value="all">All Categories</option>
          {Object.entries(CLAIM_TYPE_LABELS).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
      </div>

      {/* Claims List */}
      {loading ? (
        <div className="bg-white rounded-xl border border-slate-200/80 p-10 text-center text-sm text-slate-500">
          Loading candidate claims...
        </div>
      ) : claims.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200/80 p-12 text-center">
          <p className="text-sm font-medium text-slate-800">
            No claims found for the current view
          </p>
          <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
            Upload and parse project documents first, then click "Generate Candidate Claims" to extract traceable claims from stored evidence chunks.
          </p>
          <div className="mt-4 flex items-center justify-center gap-3">
            <Link
              to="/upload"
              className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50"
            >
              <UploadCloud className="w-3.5 h-3.5" />
              Upload Documents
            </Link>
            <button
              type="button"
              onClick={handleGenerate}
              disabled={generating}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium rounded-lg bg-navy-900 text-white hover:bg-navy-800"
            >
              <Sparkles className="w-3.5 h-3.5" />
              Generate Claims
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {claims.map((claim) => {
            const isEditing = editingId === claim.id;
            const showEvidence = !!expandedEvidence[claim.id];
            const showHistory = !!expandedHistory[claim.id];
            const isSaving = savingId === claim.id;
            const categoryLabel = CLAIM_TYPE_LABELS[claim.claim_type] || claim.claim_type;
            const categoryStyle =
              CLAIM_TYPE_STYLES[claim.claim_type] ||
              'bg-slate-100 text-slate-700 border-slate-200';

            return (
              <div
                key={claim.id}
                className="bg-white rounded-xl border border-slate-200/80 shadow-sm p-5 space-y-4"
              >
                {/* Top Metadata Row */}
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-mono text-slate-400">
                      #{claim.id}
                    </span>
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${categoryStyle}`}
                    >
                      {categoryLabel}
                    </span>
                    <StatusBadge status={claim.status} />
                    {(claim.insufficient_evidence || isIncompleteFragment(claim.claim_text)) && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-800 border border-amber-200">
                        <AlertTriangle className="w-3 h-3" />
                        Fragment / Needs Context
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-2 text-xs text-slate-500">
                    <FileText className="w-3.5 h-3.5 text-slate-400" />
                    <span className="font-medium text-slate-700">
                      {claim.source_filename}
                    </span>
                    <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-mono text-[11px]">
                      {claim.extraction_method}
                    </span>
                  </div>
                </div>

                {/* Claim Text or Edit Form */}
                {isEditing ? (
                  <div className="space-y-2">
                    <textarea
                      value={editText}
                      onChange={(e) => setEditText(e.target.value)}
                      rows={3}
                      className="w-full p-3 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent"
                    />
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => saveEdit(claim.id)}
                        disabled={isSaving || !editText.trim()}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-navy-900 text-white hover:bg-navy-800 disabled:opacity-50"
                      >
                        <Save className="w-3.5 h-3.5" />
                        Save Edit
                      </button>
                      <button
                        type="button"
                        onClick={cancelEdit}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50"
                      >
                        <X className="w-3.5 h-3.5" />
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-slate-800 leading-relaxed font-medium">
                    {claim.claim_text}
                  </p>
                )}

                {/* Primary Citation Summary + Action Bar */}
                <div className="pt-3 border-t border-slate-100 flex flex-col lg:flex-row lg:items-center justify-between gap-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={() => toggleEvidence(claim.id)}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50"
                    >
                      <MapPin className="w-3.5 h-3.5 text-slate-500" />
                      View Source Evidence ({claim.citations?.length || 0})
                      {showEvidence ? (
                        <ChevronUp className="w-3.5 h-3.5" />
                      ) : (
                        <ChevronDown className="w-3.5 h-3.5" />
                      )}
                    </button>

                    {claim.review_history?.length > 0 && (
                      <button
                        type="button"
                        onClick={() => toggleHistory(claim.id)}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50"
                      >
                        <History className="w-3.5 h-3.5 text-slate-500" />
                        History ({claim.review_history.length})
                      </button>
                    )}
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <input
                      type="text"
                      value={comments[claim.id] || ''}
                      onChange={(e) =>
                        setComments((prev) => ({
                          ...prev,
                          [claim.id]: e.target.value,
                        }))
                      }
                      placeholder="Reviewer comment (optional)..."
                      className="px-2.5 py-1.5 text-xs rounded-lg border border-slate-200 w-full sm:w-52 focus:outline-none focus:ring-2 focus:ring-accent/20"
                    />
                    <button
                      type="button"
                      onClick={() => startEdit(claim)}
                      disabled={isSaving || isEditing}
                      className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50 disabled:opacity-40"
                    >
                      <Edit3 className="w-3.5 h-3.5" />
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => handleAction(claim.id, 'approved')}
                      disabled={isSaving || claim.status === 'approved'}
                      className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-40 transition-colors"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Approve
                    </button>
                    <button
                      type="button"
                      onClick={() => handleAction(claim.id, 'rejected')}
                      disabled={isSaving || claim.status === 'rejected'}
                      className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg bg-rose-600 text-white hover:bg-rose-700 disabled:opacity-40 transition-colors"
                    >
                      <XCircle className="w-3.5 h-3.5" />
                      Reject
                    </button>
                  </div>
                </div>

                {/* Expanded Source Evidence */}
                {showEvidence && (
                  <div className="rounded-lg bg-slate-50 border border-slate-200 p-4 space-y-2.5">
                    <p className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
                      Traceable Source Citations
                    </p>
                    {claim.citations?.map((cit) => (
                      <div
                        key={cit.id}
                        className="bg-white rounded-md border border-slate-200 p-3 space-y-1.5"
                      >
                        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
                          <span className="font-semibold text-slate-800">
                            {cit.filename}
                          </span>
                          {cit.source_type && cit.source_type !== 'document' && (
                            <span className="font-mono uppercase bg-blue-50 text-blue-700 border border-blue-200 px-1.5 py-0.5 rounded">
                              {cit.source_type}
                            </span>
                          )}
                          {cit.record_id && (
                            <span className="font-mono bg-slate-100 px-1.5 py-0.5 rounded">
                              ID: {cit.record_id}
                            </span>
                          )}
                          <span className="font-mono bg-slate-100 px-1.5 py-0.5 rounded">
                            chunk #{cit.evidence_chunk_id}
                          </span>
                          {cit.page_number !== null && cit.page_number !== undefined && (
                            <span className="font-mono bg-slate-100 px-1.5 py-0.5 rounded">
                              Page {cit.page_number}
                            </span>
                          )}
                          {cit.line_number !== null && cit.line_number !== undefined && (
                            <span className="font-mono bg-slate-100 px-1.5 py-0.5 rounded">
                              Line {cit.line_number}
                            </span>
                          )}
                          {cit.json_path && (
                            <span className="font-mono bg-slate-100 px-1.5 py-0.5 rounded">
                              {cit.json_path}
                            </span>
                          )}
                        </div>
                        <div className="space-y-1">
                          <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                            Original Source Context
                          </p>
                          <pre className="whitespace-pre-wrap font-sans text-xs text-slate-700 bg-slate-50/70 p-2.5 rounded border border-slate-100 leading-relaxed">
                            {cit.surrounding_context || cit.excerpt}
                          </pre>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Expanded Review History */}
                {showHistory && (
                  <div className="rounded-lg bg-slate-50 border border-slate-200 p-4 space-y-2">
                    <p className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
                      Review History
                    </p>
                    {claim.review_history?.map((rh) => (
                      <div
                        key={rh.id}
                        className="text-xs bg-white rounded border border-slate-200 p-2.5 flex flex-wrap items-center justify-between gap-2"
                      >
                        <div>
                          <span className="font-semibold capitalize text-slate-800">
                            {rh.action}
                          </span>
                          {rh.previous_status !== rh.new_status && (
                            <span className="text-slate-500 ml-1.5">
                              ({rh.previous_status} &rarr; {rh.new_status})
                            </span>
                          )}
                          {rh.comment && (
                            <p className="text-slate-600 mt-0.5">
                              Comment: {rh.comment}
                            </p>
                          )}
                        </div>
                        <span className="text-slate-400 font-mono text-[11px]">
                          {new Date(rh.reviewed_at).toLocaleString()}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
