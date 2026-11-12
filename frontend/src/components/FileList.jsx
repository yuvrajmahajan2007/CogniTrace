import React, { useEffect, useState } from 'react';
import Modal from './Modal';

function FileList({ refresh }) {
  const [files, setFiles] = useState([]);
  const [selected, setSelected] = useState(null);
  const [content, setContent] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const fetchFiles = async () => {
    try {
      const res = await fetch('/api/files');
      const data = await res.json();
      setFiles(data);
    } catch (e) {
      setError('Failed to load files');
    }
  };

  useEffect(() => {
    fetchFiles();
  }, [refresh]);

  const viewContent = async (file) => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`/api/files/${file.id}/content`);
      if (!res.ok) throw new Error('Unable to fetch content');
      const data = await res.json();
      setContent(data);
      setSelected(file);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const deleteFile = async (fileId) => {
    if (!window.confirm('Delete this file?')) return;
    try {
      const res = await fetch(`/api/files/${fileId}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Delete failed');
      // refresh list
      fetchFiles();
    } catch (e) {
      alert(e.message);
    }
  };

  return (
    <div className="my-4">
      <h2 className="text-xl font-semibold mb-2 text-white">Uploaded Files</h2>
      {error && <p className="text-red-400">{error}</p>}
      <table className="min-w-full table-auto text-sm text-left text-gray-200">
        <thead className="bg-navy-dark">
          <tr>
            <th className="px-2 py-1">Name</th>
            <th className="px-2 py-1">Size (KB)</th>
            <th className="px-2 py-1">Status</th>
            <th className="px-2 py-1">Actions</th>
          </tr>
        </thead>
        <tbody>
          {files.map((f) => (
            <tr key={f.id} className="border-b border-gray-700">
              <td className="px-2 py-1">{f.filename}</td>
              <td className="px-2 py-1">{(f.size_bytes / 1024).toFixed(1)}</td>
              <td className="px-2 py-1">{f.status}</td>
              <td className="px-2 py-1 space-x-2">
                <button className="px-2 py-1 bg-blue-600 rounded" onClick={() => viewContent(f)} disabled={f.status !== 'completed'}>
                  View
                </button>
                <button className="px-2 py-1 bg-red-600 rounded" onClick={() => deleteFile(f.id)}>
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {selected && (
        <Modal onClose={() => setSelected(null)} title={selected.filename}>
          {loading ? (
            <p>Loading...</p>
          ) : (
            <div className="max-h-96 overflow-auto">
              {content.map((c) => (
                <div key={c.id} className="mb-2 border-b border-gray-600 pb-1">
                  <pre className="whitespace-pre-wrap text-xs text-gray-300">{c.text}</pre>
                  <div className="text-xs text-gray-400 mt-1">
                    {c.page_number && <span>Page: {c.page_number} </span>}
                    {c.line_number && <span>Line: {c.line_number} </span>}
                    {c.json_path && <span>Path: {c.json_path}</span>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Modal>
      )}
    </div>
  );
}

export default FileList;
