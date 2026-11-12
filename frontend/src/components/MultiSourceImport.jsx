import React, { useState, useRef } from 'react';
import {
  GitBranch,
  MessageSquare,
  CheckSquare,
  UploadCloud,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import { importSourceWithProgress } from '../api/client';

const SOURCE_CONFIGS = [
  {
    key: 'git',
    endpoint: 'git',
    title: 'Git Activity Import',
    subtitle: 'Commit hashes, authors, dates, messages & changed files',
    formats: 'TXT, CSV, JSON',
    accept: '.txt,.csv,.json',
    icon: GitBranch,
  },
  {
    key: 'chat',
    endpoint: 'chat',
    title: 'Chat Export Import',
    subtitle: 'Speakers, timestamps, decisions, blockers & action items',
    formats: 'TXT, JSON',
    accept: '.txt,.json',
    icon: MessageSquare,
  },
  {
    key: 'tasks',
    endpoint: 'tasks',
    title: 'Task Records Import',
    subtitle: 'Task IDs, titles, statuses, assignees, priorities & due dates',
    formats: 'CSV, JSON',
    accept: '.csv,.json',
    icon: CheckSquare,
  },
];

function SourceImportCard({ cfg, onImportSuccess }) {
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const inputRef = useRef(null);

  const Icon = cfg.icon;

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      setResult(null);
      setError('');
    }
    e.target.value = '';
  };

  const handleImport = async () => {
    if (!selectedFile) return;
    setUploading(true);
    setProgress(0);
    setResult(null);
    setError('');
    try {
      const res = await importSourceWithProgress(cfg.endpoint, selectedFile, (pct) => {
        setProgress(pct);
      });
      setResult(res);
      setSelectedFile(null);
      if (onImportSuccess) onImportSuccess(res);
    } catch (err) {
      setError(err.message || 'Import failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200/80 shadow-sm p-5 flex flex-col justify-between space-y-4">
      <div>
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-lg bg-slate-100 text-navy-800 shrink-0">
            <Icon className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <h4 className="text-sm font-semibold text-slate-900">{cfg.title}</h4>
            <p className="text-xs text-slate-500 mt-0.5">{cfg.subtitle}</p>
          </div>
        </div>

        <div className="mt-4">
          <input
            ref={inputRef}
            type="file"
            accept={cfg.accept}
            onChange={handleFileChange}
            className="hidden"
          />
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            disabled={uploading}
            className="w-full px-3 py-2.5 rounded-lg border border-dashed border-slate-300 bg-slate-50/70 hover:bg-slate-50 hover:border-slate-400 text-xs text-slate-600 text-center transition-colors disabled:opacity-50"
          >
            {selectedFile ? (
              <span className="font-medium text-slate-800 truncate block">
                {selectedFile.name} ({(selectedFile.size / 1024).toFixed(1)} KB)
              </span>
            ) : (
              <span>Select {cfg.formats} file (max 20 MB)</span>
            )}
          </button>
        </div>

        {uploading && (
          <div className="mt-3">
            <div className="flex justify-between text-[11px] text-slate-500 mb-1">
              <span>Importing...</span>
              <span className="font-mono">{progress}%</span>
            </div>
            <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-accent transition-all duration-150"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {result && (
          <div className="mt-3 p-2.5 rounded-lg bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 flex items-start gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
            <div>
              <p className="font-medium">{result.message}</p>
              <p className="text-[11px] text-emerald-700 mt-0.5">
                Imported: {result.imported_count} &middot; Skipped duplicates: {result.skipped_duplicates}
              </p>
            </div>
          </div>
        )}

        {error && (
          <div className="mt-3 p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}
      </div>

      <button
        type="button"
        onClick={handleImport}
        disabled={!selectedFile || uploading}
        className="w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium rounded-lg bg-navy-900 text-white hover:bg-navy-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        <UploadCloud className="w-3.5 h-3.5" />
        {uploading ? 'Importing...' : 'Import Source'}
      </button>
    </div>
  );
}

export default function MultiSourceImport({ onImportSuccess }) {
  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-base font-semibold text-slate-900">
          Multi-Source Activity & Record Import
        </h3>
        <p className="text-xs text-slate-500 mt-0.5">
          Import Git commit logs, chat exports, and task records into the unified EvidenceChunk store with automatic duplicate detection.
        </p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {SOURCE_CONFIGS.map((cfg) => (
          <SourceImportCard
            key={cfg.key}
            cfg={cfg}
            onImportSuccess={onImportSuccess}
          />
        ))}
      </div>
    </div>
  );
}
