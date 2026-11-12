import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import {
  UploadCloud,
  File,
  Trash2,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  RefreshCw,
  X,
} from 'lucide-react';
import { listFiles, uploadFilesWithProgress, deleteFile } from '../api/client';
import StatusBadge from '../components/StatusBadge';
import MultiSourceImport from '../components/MultiSourceImport';

const ALLOWED_EXTENSIONS = ['pdf', 'docx', 'txt', 'md', 'csv', 'json'];
const MAX_SIZE_BYTES = 20 * 1024 * 1024; // 20 MB

function formatBytes(bytes) {
  if (!bytes && bytes !== 0) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export default function UploadDocuments() {
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [feedback, setFeedback] = useState(null); // { type: 'success'|'error', message: string }

  const [documents, setDocuments] = useState([]);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [docsError, setDocsError] = useState('');
  const [deletingId, setDeletingId] = useState(null);

  const fileInputRef = useRef(null);

  const fetchDocuments = useCallback(async () => {
    try {
      const data = await listFiles();
      setDocuments(data);
      setDocsError('');
    } catch (err) {
      setDocsError(err.message || 'Failed to load uploaded documents');
    } finally {
      setLoadingDocs(false);
    }
  }, []);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  // Poll while any file is pending or processing
  useEffect(() => {
    const hasActive = documents.some(
      (d) => d.status === 'pending' || d.status === 'processing'
    );
    if (!hasActive) return;

    const timer = setInterval(() => {
      fetchDocuments();
    }, 2000);
    return () => clearInterval(timer);
  }, [documents, fetchDocuments]);

  const validateAndStageFiles = (incoming) => {
    setFeedback(null);
    const valid = [];
    const errors = [];

    incoming.forEach((file) => {
      const ext = file.name.split('.').pop()?.toLowerCase() || '';
      if (!ALLOWED_EXTENSIONS.includes(ext)) {
        errors.push(`${file.name}: unsupported format (.${ext})`);
      } else if (file.size > MAX_SIZE_BYTES) {
        errors.push(`${file.name}: exceeds 20 MB limit`);
      } else {
        valid.push(file);
      }
    });

    if (errors.length > 0) {
      setFeedback({
        type: 'error',
        message: errors.join(' | '),
      });
    }

    if (valid.length > 0) {
      setSelectedFiles((prev) => {
        const existingNames = new Set(prev.map((f) => `${f.name}-${f.size}`));
        const deduped = valid.filter(
          (f) => !existingNames.has(`${f.name}-${f.size}`)
        );
        return [...prev, ...deduped];
      });
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = Array.from(e.dataTransfer.files || []);
    if (dropped.length) validateAndStageFiles(dropped);
  };

  const handleFileInput = (e) => {
    const picked = Array.from(e.target.files || []);
    if (picked.length) validateAndStageFiles(picked);
    e.target.value = '';
  };

  const removeStaged = (index) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (selectedFiles.length === 0) return;
    setUploading(true);
    setProgress(0);
    setFeedback(null);

    try {
      const result = await uploadFilesWithProgress(selectedFiles, (pct) => {
        setProgress(pct);
      });
      const count = result?.uploaded?.length || selectedFiles.length;
      setFeedback({
        type: 'success',
        message: `Uploaded ${count} document${count === 1 ? '' : 's'}. Background parsing started.`,
      });
      setSelectedFiles([]);
      await fetchDocuments();
    } catch (err) {
      setFeedback({
        type: 'error',
        message: err.message || 'Upload failed',
      });
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (doc) => {
    setDeletingId(doc.id);
    try {
      await deleteFile(doc.id);
      await fetchDocuments();
    } catch (err) {
      setFeedback({
        type: 'error',
        message: `Failed to delete ${doc.filename}: ${err.message}`,
      });
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-slate-900">Upload Documents</h2>
        <p className="text-sm text-slate-500 mt-0.5">
          Ingest project artifacts (PDF, DOCX, TXT, MD, CSV, JSON) up to 20 MB per file for evidence chunk extraction.
        </p>
      </div>

      {/* Upload Card */}
      <div className="bg-white rounded-xl border border-slate-200/80 shadow-sm p-6">
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          onClick={() => !uploading && fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer ${
            isDragging
              ? 'border-accent bg-blue-50/60'
              : 'border-slate-300 bg-slate-50/60 hover:bg-slate-50 hover:border-slate-400'
          } ${uploading ? 'opacity-60 pointer-events-none' : ''}`}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.txt,.md,.csv,.json"
            className="hidden"
            onChange={handleFileInput}
          />
          <div className="w-12 h-12 rounded-full bg-white border border-slate-200 shadow-sm flex items-center justify-center mx-auto text-navy-700">
            <UploadCloud className="w-6 h-6" />
          </div>
          <p className="mt-3 text-sm font-medium text-slate-800">
            Drag and drop project files here, or click to browse
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Supported: PDF, DOCX, TXT, MD, CSV, JSON &middot; Max 20 MB per file
          </p>
        </div>

        {/* Staged Files */}
        {selectedFiles.length > 0 && (
          <div className="mt-4 space-y-2">
            <div className="flex items-center justify-between text-xs font-medium text-slate-600">
              <span>Ready to upload ({selectedFiles.length})</span>
              {!uploading && (
                <button
                  type="button"
                  onClick={() => setSelectedFiles([])}
                  className="text-slate-500 hover:text-slate-800"
                >
                  Clear all
                </button>
              )}
            </div>
            <ul className="divide-y divide-slate-100 border border-slate-200 rounded-lg bg-white">
              {selectedFiles.map((file, idx) => (
                <li
                  key={`${file.name}-${idx}`}
                  className="px-3.5 py-2.5 flex items-center justify-between gap-3 text-sm"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <File className="w-4 h-4 text-slate-400 shrink-0" />
                    <span className="truncate font-medium text-slate-700">
                      {file.name}
                    </span>
                    <span className="text-xs text-slate-400 shrink-0">
                      {formatBytes(file.size)}
                    </span>
                  </div>
                  {!uploading && (
                    <button
                      type="button"
                      onClick={() => removeStaged(idx)}
                      className="p-1 text-slate-400 hover:text-rose-600 rounded"
                      aria-label={`Remove ${file.name}`}
                    >
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Progress Bar */}
        {uploading && (
          <div className="mt-4">
            <div className="flex items-center justify-between text-xs text-slate-600 mb-1.5">
              <span>Uploading to backend...</span>
              <span className="font-mono">{progress}%</span>
            </div>
            <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-accent transition-all duration-150"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {/* Feedback Alert */}
        {feedback && (
          <div
            className={`mt-4 p-3.5 rounded-lg border text-xs flex items-start gap-2.5 ${
              feedback.type === 'success'
                ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                : 'bg-rose-50 border-rose-200 text-rose-800'
            }`}
          >
            {feedback.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
            ) : (
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            )}
            <span>{feedback.message}</span>
          </div>
        )}

        {/* Upload Button */}
        <div className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={handleUpload}
            disabled={uploading || selectedFiles.length === 0}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-navy-900 text-white hover:bg-navy-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <UploadCloud className="w-4 h-4" />
            {uploading ? 'Uploading...' : `Upload ${selectedFiles.length > 0 ? `(${selectedFiles.length})` : ''}`}
          </button>
        </div>
      </div>

      {/* Multi-Source Import Section */}
      <MultiSourceImport onImportSuccess={fetchDocuments} />

      {/* Uploaded Documents Table */}
      <div className="bg-white rounded-xl border border-slate-200/80 shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-200/80 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">
              Uploaded Documents ({documents.length})
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Files are parsed asynchronously into indexed evidence chunks.
            </p>
          </div>
          <button
            type="button"
            onClick={fetchDocuments}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
        </div>

        {docsError && (
          <div className="p-4 bg-rose-50 border-b border-rose-200 text-xs text-rose-800">
            {docsError}
          </div>
        )}

        {loadingDocs ? (
          <div className="p-8 text-center text-sm text-slate-500">
            Loading documents...
          </div>
        ) : documents.length === 0 ? (
          <div className="p-10 text-center text-sm text-slate-500">
            No documents uploaded yet. Use the dropzone above to upload your first file.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50/80 text-xs uppercase text-slate-500 border-b border-slate-200/80">
                <tr>
                  <th className="px-5 py-3 font-medium">Filename</th>
                  <th className="px-4 py-3 font-medium">Source</th>
                  <th className="px-4 py-3 font-medium">Type</th>
                  <th className="px-4 py-3 font-medium">Size</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {documents.map((doc) => (
                  <tr key={doc.id} className="hover:bg-slate-50/60">
                    <td className="px-5 py-3">
                      <p className="font-medium text-slate-800 truncate max-w-xs">
                        {doc.filename}
                      </p>
                      {doc.error_message && (
                        <p className="text-xs text-rose-600 mt-0.5">
                          {doc.error_message}
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs font-mono text-slate-600">
                      <span className="px-2 py-0.5 rounded bg-slate-100 border border-slate-200 uppercase text-[11px]">
                        {doc.source_type || 'document'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs font-mono text-slate-500">
                      {doc.filename.split('.').pop()?.toUpperCase() || '—'}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500 whitespace-nowrap">
                      {formatBytes(doc.size_bytes)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <StatusBadge status={doc.status} />
                    </td>
                    <td className="px-5 py-3 text-right whitespace-nowrap space-x-2">
                      {doc.status === 'completed' && (
                        <Link
                          to={`/evidence?fileId=${doc.id}`}
                          className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-md border border-slate-200 text-slate-700 hover:bg-slate-50"
                        >
                          <ExternalLink className="w-3 h-3" />
                          Evidence
                        </Link>
                      )}
                      <button
                        type="button"
                        onClick={() => handleDelete(doc)}
                        disabled={deletingId === doc.id}
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-md border border-rose-200 text-rose-700 hover:bg-rose-50 disabled:opacity-50"
                      >
                        <Trash2 className="w-3 h-3" />
                        {deletingId === doc.id ? 'Deleting...' : 'Delete'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
