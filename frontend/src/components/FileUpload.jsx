import React, { useState } from 'react';
import { apiUrl } from '../api/client';

function FileUpload({ onUploadComplete }) {
  const [files, setFiles] = useState([]);
  const [message, setMessage] = useState('');
  const [uploading, setUploading] = useState(false);

  const handleDrop = (e) => {
    e.preventDefault();
    const dropped = Array.from(e.dataTransfer.files);
    setFiles(dropped);
  };

  const handleSelect = (e) => {
    setFiles(Array.from(e.target.files));
  };

  const upload = async () => {
    if (!files.length) return;
    setUploading(true);
    setMessage('');
    const formData = new FormData();
    files.forEach((f) => formData.append('files', f));
    try {
      const res = await fetch(apiUrl('/api/files/upload'), {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Upload failed');
      }
      const data = await res.json();
      setMessage('Upload successful');
      if (onUploadComplete) onUploadComplete();
    } catch (e) {
      setMessage(`Error: ${e.message}`);
    } finally {
      setUploading(false);
      setFiles([]);
    }
  };

  return (
    <div className="my-4">
      <div
        className="border-2 border-dashed border-gray-400 rounded p-8 text-center cursor-pointer bg-navy-dark hover:bg-navy"
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        onClick={() => document.getElementById('fileInput').click()}
      >
        <p className="text-gray-300">Drag & drop files here or click to browse</p>
        <input
          id="fileInput"
          type="file"
          multiple
          className="hidden"
          onChange={handleSelect}
        />
        {files.length > 0 && (
          <div className="mt-2 text-sm text-gray-200">
            {files.map((f) => (
              <div key={f.name}>{f.name} ({(f.size / 1024).toFixed(1)} KB)</div>
            ))}
          </div>
        )}
      </div>
      <button
        className="mt-2 px-4 py-2 bg-green-600 rounded disabled:opacity-50"
        onClick={upload}
        disabled={uploading || !files.length}
      >
        {uploading ? 'Uploading…' : 'Upload'}
      </button>
      {message && <p className="mt-2 text-sm">{message}</p>}
    </div>
  );
}

export default FileUpload;
