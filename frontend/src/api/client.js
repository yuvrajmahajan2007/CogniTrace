// API client for CogniTrace backend

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '');

export function apiUrl(path) {
  const normalized = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE_URL}${normalized}`;
}

export async function checkHealth() {
  const res = await fetch(apiUrl('/health'));
  if (!res.ok) {
    throw new Error(`Health check failed (${res.status})`);
  }
  return res.json();
}

export async function listFiles() {
  const res = await fetch(apiUrl('/api/files'));
  if (!res.ok) {
    throw new Error(`Failed to fetch files (${res.status})`);
  }
  return res.json();
}

export async function getFileDetail(fileId) {
  const res = await fetch(apiUrl(`/api/files/${fileId}`));
  if (!res.ok) {
    throw new Error(`Failed to fetch file details (${res.status})`);
  }
  return res.json();
}

export async function getFileContent(fileId) {
  const res = await fetch(apiUrl(`/api/files/${fileId}/content`));
  if (!res.ok) {
    throw new Error(`Failed to fetch evidence chunks (${res.status})`);
  }
  return res.json();
}

export async function deleteFile(fileId) {
  const res = await fetch(apiUrl(`/api/files/${fileId}`), { method: 'DELETE' });
  if (!res.ok) {
    let message = `Delete failed (${res.status})`;
    try {
      const err = await res.json();
      if (err.detail) message = err.detail;
    } catch {
      // ignore json parse error
    }
    throw new Error(message);
  }
  return res.json();
}

export function uploadFilesWithProgress(fileList, onProgress) {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    fileList.forEach((file) => {
      formData.append('files', file);
    });

    const xhr = new XMLHttpRequest();
    xhr.open('POST', apiUrl('/api/files/upload'));

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        const percent = Math.round((event.loaded / event.total) * 100);
        onProgress(percent);
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch {
          reject(new Error('Invalid response from server'));
        }
      } else {
        let message = `Upload failed (${xhr.status})`;
        try {
          const err = JSON.parse(xhr.responseText);
          if (err.detail) message = err.detail;
        } catch {
          // ignore
        }
        reject(new Error(message));
      }
    };

    xhr.onerror = () => {
      reject(new Error('Network error while uploading files'));
    };

    xhr.send(formData);
  });
}

// Phase 2: Claims & Verification API

export async function generateClaims({ use_gemini = false, clear_existing = false } = {}) {
  const res = await fetch(apiUrl('/api/claims/generate'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ use_gemini, clear_existing }),
  });
  if (!res.ok) {
    let message = `Failed to generate claims (${res.status})`;
    try {
      const err = await res.json();
      if (err.detail) message = err.detail;
    } catch {
      // ignore
    }
    throw new Error(message);
  }
  return res.json();
}

export async function listClaims({ status, claim_type, file_id } = {}) {
  const params = new URLSearchParams();
  if (status && status !== 'all') params.set('status', status);
  if (claim_type && claim_type !== 'all') params.set('claim_type', claim_type);
  if (file_id) params.set('file_id', String(file_id));
  const qs = params.toString();
  const res = await fetch(apiUrl(`/api/claims${qs ? `?${qs}` : ''}`));
  if (!res.ok) {
    throw new Error(`Failed to fetch claims (${res.status})`);
  }
  return res.json();
}

export async function getClaim(claimId) {
  const res = await fetch(apiUrl(`/api/claims/${claimId}`));
  if (!res.ok) {
    throw new Error(`Failed to fetch claim (${res.status})`);
  }
  return res.json();
}

export async function updateClaim(claimId, payload) {
  const res = await fetch(apiUrl(`/api/claims/${claimId}`), {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    let message = `Failed to update claim (${res.status})`;
    try {
      const err = await res.json();
      if (err.detail) message = err.detail;
    } catch {
      // ignore
    }
    throw new Error(message);
  }
  return res.json();
}

export async function listConflicts() {
  const res = await fetch(apiUrl('/api/claims/conflicts'));
  if (!res.ok) {
    throw new Error(`Failed to fetch conflicts (${res.status})`);
  }
  return res.json();
}

export async function getClaimStats() {
  const res = await fetch(apiUrl('/api/claims/stats'));
  if (!res.ok) {
    throw new Error(`Failed to fetch claim stats (${res.status})`);
  }
  return res.json();
}

// Phase 3: Handover Reports API

export async function generateReport(title = 'CogniTrace Project Handover Report') {
  const res = await fetch(apiUrl('/api/reports/generate'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) {
    let message = `Failed to generate report (${res.status})`;
    try {
      const err = await res.json();
      if (err.detail) message = err.detail;
    } catch {
      // ignore
    }
    throw new Error(message);
  }
  return res.json();
}

export async function listReports() {
  const res = await fetch(apiUrl('/api/reports'));
  if (!res.ok) {
    throw new Error(`Failed to fetch reports (${res.status})`);
  }
  return res.json();
}

export async function getReport(reportId) {
  const res = await fetch(apiUrl(`/api/reports/${reportId}`));
  if (!res.ok) {
    throw new Error(`Failed to fetch report (${res.status})`);
  }
  return res.json();
}

export function getReportDownloadUrl(reportId, format = 'pdf') {
  return apiUrl(`/api/reports/${reportId}/download?format=${encodeURIComponent(format)}`);
}

// Phase 4: Multi-Source Import API

export function importSourceWithProgress(endpointType, file, onProgress) {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append('file', file);

    const xhr = new XMLHttpRequest();
    xhr.open('POST', apiUrl(`/api/imports/${endpointType}`));

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch {
          reject(new Error('Invalid response from server'));
        }
      } else {
        let message = `Import failed (${xhr.status})`;
        try {
          const err = JSON.parse(xhr.responseText);
          if (err.detail) message = err.detail;
        } catch {
          // ignore
        }
        reject(new Error(message));
      }
    };

    xhr.onerror = () => {
      reject(new Error('Network error while importing source file'));
    };

    xhr.send(formData);
  });
}

export async function listImports(sourceType) {
  const qs = sourceType ? `?source_type=${encodeURIComponent(sourceType)}` : '';
  const res = await fetch(apiUrl(`/api/imports${qs}`));
  if (!res.ok) {
    throw new Error(`Failed to load imports (${res.status})`);
  }
  return res.json();
}

// Phase 4: AI Assistant Conversational & Dynamic Visualizations API

// Persistent browser identifier for chat history ownership
function getClientId() {
  let id = localStorage.getItem('cognitrace_client_id');
  if (!id) {
    id = 'client_' + Date.now() + '_' + Math.random().toString(36).substring(2, 10);
    localStorage.setItem('cognitrace_client_id', id);
  }
  return id;
}

export { getClientId };

export async function sendChatMessage(sessionId, message, conversationId = null) {
  const body = {
    message: message,
    client_id: getClientId(),
  };
  if (conversationId) {
    body.conversation_id = conversationId;
  } else {
    body.session_id = sessionId;
  }

  const res = await fetch(apiUrl('/api/chat/message'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    let detail = `Chat request failed (${res.status})`;
    try {
      const err = await res.json();
      if (err.detail) {
        detail = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail);
      }
    } catch {
      // ignore json parse error
    }
    throw new Error(detail);
  }

  return res.json();
}

export async function getChatSuggestions() {
  const res = await fetch(apiUrl('/api/chat/suggestions'));
  if (!res.ok) {
    throw new Error(`Failed to fetch suggestions (${res.status})`);
  }
  return res.json();
}

export async function getAnalyticsChart(dataset, chartType = null) {
  const params = new URLSearchParams({ dataset });
  if (chartType) params.append('chart_type', chartType);

  const res = await fetch(apiUrl(`/api/chat/analytics/chart?${params.toString()}`));
  if (!res.ok) {
    let detail = `Failed to fetch chart (${res.status})`;
    try {
      const err = await res.json();
      if (err.detail) detail = err.detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function clearChatSession(sessionId) {
  const res = await fetch(apiUrl(`/api/chat/session/${encodeURIComponent(sessionId)}`), {
    method: 'DELETE',
  });
  if (!res.ok) {
    throw new Error(`Failed to clear session (${res.status})`);
  }
  return res.json();
}

// Persistent Conversation CRUD APIs

export async function listConversations() {
  const clientId = getClientId();
  const res = await fetch(apiUrl(`/api/chat/conversations?client_id=${encodeURIComponent(clientId)}`));
  if (!res.ok) {
    throw new Error(`Failed to list conversations (${res.status})`);
  }
  return res.json();
}

export async function createConversation(title = null) {
  const body = {
    client_id: getClientId(),
  };
  if (title) body.title = title;

  const res = await fetch(apiUrl('/api/chat/conversations'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`Failed to create conversation (${res.status})`);
  }
  return res.json();
}

export async function getConversationDetail(conversationId) {
  const clientId = getClientId();
  const res = await fetch(apiUrl(`/api/chat/conversations/${encodeURIComponent(conversationId)}?client_id=${encodeURIComponent(clientId)}`));
  if (!res.ok) {
    throw new Error(`Failed to load conversation (${res.status})`);
  }
  return res.json();
}

export async function updateConversationTitle(conversationId, title) {
  const clientId = getClientId();
  const res = await fetch(apiUrl(`/api/chat/conversations/${encodeURIComponent(conversationId)}?client_id=${encodeURIComponent(clientId)}`), {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) {
    throw new Error(`Failed to rename conversation (${res.status})`);
  }
  return res.json();
}

export async function deleteConversation(conversationId) {
  const clientId = getClientId();
  const res = await fetch(apiUrl(`/api/chat/conversations/${encodeURIComponent(conversationId)}?client_id=${encodeURIComponent(clientId)}`), {
    method: 'DELETE',
  });
  if (!res.ok) {
    throw new Error(`Failed to delete conversation (${res.status})`);
  }
  return res.json();
}
