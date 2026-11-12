import React, { useEffect, useState, useCallback } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import {
  Search,
  FileText,
  MapPin,
  RefreshCw,
  AlertCircle,
  UploadCloud,
} from 'lucide-react';
import { listFiles, getFileContent } from '../api/client';

export default function EvidenceExplorer() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialFileId = searchParams.get('fileId') || 'all';

  const [files, setFiles] = useState([]);
  const [selectedFileId, setSelectedFileId] = useState(initialFileId);
  const [sourceTypeFilter, setSourceTypeFilter] = useState('all');
  const [chunks, setChunks] = useState([]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadEvidence = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const fileList = await listFiles();
      const completed = fileList.filter((f) => f.status === 'completed');
      setFiles(completed);

      if (completed.length === 0) {
        setChunks([]);
        return;
      }

      const targets =
        selectedFileId === 'all'
          ? completed
          : completed.filter((f) => String(f.id) === String(selectedFileId));

      const results = await Promise.all(
        targets.map(async (file) => {
          const fileChunks = await getFileContent(file.id);
          return fileChunks.map((chunk) => ({
            ...chunk,
            filename: file.filename,
            contentType: file.content_type,
            fileSourceType: file.source_type || chunk.source_type || 'document',
          }));
        })
      );

      setChunks(results.flat());
    } catch (err) {
      setError(err.message || 'Failed to load evidence chunks');
    } finally {
      setLoading(false);
    }
  }, [selectedFileId]);

  useEffect(() => {
    loadEvidence();
  }, [loadEvidence]);

  const handleFileChange = (value) => {
    setSelectedFileId(value);
    if (value === 'all') {
      searchParams.delete('fileId');
    } else {
      searchParams.set('fileId', value);
    }
    setSearchParams(searchParams);
  };

  const filteredChunks = chunks.filter((c) => {
    const st = c.source_type || c.fileSourceType || 'document';
    if (sourceTypeFilter !== 'all' && st !== sourceTypeFilter) return false;
    if (!query.trim()) return true;
    const q = query.toLowerCase();
    return (
      c.text.toLowerCase().includes(q) ||
      c.filename.toLowerCase().includes(q) ||
      (c.record_id && c.record_id.toLowerCase().includes(q)) ||
      (c.author && c.author.toLowerCase().includes(q)) ||
      (c.json_path && c.json_path.toLowerCase().includes(q))
    );
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold text-slate-900">
            Evidence Explorer
          </h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Inspect extracted text chunks and exact source locations across parsed documents.
          </p>
        </div>
        <button
          type="button"
          onClick={loadEvidence}
          disabled={loading}
          className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded-lg border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Filters Bar */}
      <div className="bg-white rounded-xl border border-slate-200/80 shadow-sm p-4 flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search evidence text, filename, or JSON path..."
            className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent"
          />
        </div>
        <div className="sm:w-44">
          <select
            value={sourceTypeFilter}
            onChange={(e) => setSourceTypeFilter(e.target.value)}
            className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent"
          >
            <option value="all">All Sources</option>
            <option value="document">Documents</option>
            <option value="git">Git Activity</option>
            <option value="chat">Chat Exports</option>
            <option value="task">Task Records</option>
          </select>
        </div>
        <div className="sm:w-64">
          <select
            value={selectedFileId}
            onChange={(e) => handleFileChange(e.target.value)}
            className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent"
          >
            <option value="all">All Parsed Documents ({files.length})</option>
            {files.map((f) => (
              <option key={f.id} value={String(f.id)}>
                {f.filename}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 flex items-start gap-3 text-sm text-rose-800">
          <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
          <div>
            <p className="font-medium">Unable to load evidence</p>
            <p className="text-xs text-rose-700 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* Results */}
      {loading ? (
        <div className="bg-white rounded-xl border border-slate-200/80 p-10 text-center text-sm text-slate-500">
          Loading extracted evidence chunks...
        </div>
      ) : files.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200/80 p-12 text-center">
          <div className="w-10 h-10 rounded-full bg-slate-100 text-slate-400 flex items-center justify-center mx-auto mb-3">
            <FileText className="w-5 h-5" />
          </div>
          <p className="text-sm font-medium text-slate-700">
            No parsed documents available
          </p>
          <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
            Upload and parse project documents first to inspect extracted evidence chunks and source citations.
          </p>
          <Link
            to="/upload"
            className="mt-4 inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium rounded-lg bg-navy-900 text-white hover:bg-navy-800"
          >
            <UploadCloud className="w-3.5 h-3.5" />
            Go to Upload Documents
          </Link>
        </div>
      ) : filteredChunks.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200/80 p-10 text-center text-sm text-slate-500">
          No evidence chunks match your current filter.
        </div>
      ) : (
        <div className="space-y-3">
          <div className="text-xs text-slate-500 px-1">
            Showing <span className="font-semibold text-slate-700">{filteredChunks.length}</span> evidence chunk{filteredChunks.length === 1 ? '' : 's'}
          </div>
          {filteredChunks.map((chunk) => (
            <div
              key={`${chunk.file_id}-${chunk.id}`}
              className="bg-white rounded-xl border border-slate-200/80 shadow-sm p-5 hover:border-slate-300 transition-colors"
            >
              <div className="flex flex-wrap items-center justify-between gap-2 pb-3 mb-3 border-b border-slate-100">
                <div className="flex items-center gap-2 min-w-0">
                  <FileText className="w-4 h-4 text-navy-600 shrink-0" />
                  <span className="text-sm font-semibold text-slate-800 truncate">
                    {chunk.filename}
                  </span>
                  <span className="text-xs font-mono text-slate-400">
                    #chunk-{chunk.chunk_index}
                  </span>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <span className="px-2 py-0.5 rounded-md bg-navy-900/5 text-navy-800 border border-navy-200 text-xs font-mono uppercase">
                    {chunk.source_type || chunk.fileSourceType || 'document'}
                  </span>
                  {chunk.record_id && (
                    <span className="px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 border border-blue-200 text-xs font-mono">
                      ID: {chunk.record_id}
                    </span>
                  )}
                  {chunk.author && (
                    <span className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 text-xs">
                      {chunk.author}
                    </span>
                  )}
                  {chunk.record_timestamp && (
                    <span className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 text-xs font-mono">
                      {chunk.record_timestamp}
                    </span>
                  )}
                  {chunk.page_number !== null && chunk.page_number !== undefined && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 text-xs font-mono">
                      <MapPin className="w-3 h-3 text-slate-500" />
                      Page {chunk.page_number}
                    </span>
                  )}
                  {chunk.line_number !== null && chunk.line_number !== undefined && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 text-xs font-mono">
                      <MapPin className="w-3 h-3 text-slate-500" />
                      Line {chunk.line_number}
                    </span>
                  )}
                  {chunk.json_path && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 text-xs font-mono">
                      <MapPin className="w-3 h-3 text-slate-500" />
                      {chunk.json_path}
                    </span>
                  )}
                </div>
              </div>

              <pre className="whitespace-pre-wrap font-sans text-sm text-slate-700 leading-relaxed">
                {chunk.text}
              </pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
