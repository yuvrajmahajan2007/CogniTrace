import React, { useEffect, useState, useCallback } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { checkHealth } from './api/client';
import Layout from './components/Layout';
import DashboardOverview from './pages/DashboardOverview';
import UploadDocuments from './pages/UploadDocuments';
import EvidenceExplorer from './pages/EvidenceExplorer';
import ClaimVerification from './pages/ClaimVerification';
import HandoverReports from './pages/HandoverReports';
import Settings from './pages/Settings';

const PAGE_META = {
  '/': {
    title: 'Dashboard',
    subtitle: 'Project handover intelligence overview',
  },
  '/upload': {
    title: 'Upload Documents',
    subtitle: 'Ingest PDF, DOCX, TXT, MD, CSV, and JSON sources',
  },
  '/evidence': {
    title: 'Evidence Explorer',
    subtitle: 'Traceable text chunks and source references',
  },
  '/claims': {
    title: 'Claim Verification',
    subtitle: 'Human-in-the-loop review and approval',
  },
  '/reports': {
    title: 'Handover Reports',
    subtitle: 'Approved knowledge and verified citations',
  },
  '/settings': {
    title: 'Settings',
    subtitle: 'System connectivity and ingestion rules',
  },
};

function AppShell() {
  const location = useLocation();
  const [backendStatus, setBackendStatus] = useState('checking');
  const [healthError, setHealthError] = useState('');

  const verifyHealth = useCallback(async () => {
    setBackendStatus('checking');
    setHealthError('');
    try {
      const data = await checkHealth();
      if (data?.status === 'ok') {
        setBackendStatus('connected');
      } else {
        setBackendStatus('unreachable');
        setHealthError('Unexpected health response');
      }
    } catch (err) {
      setBackendStatus('unreachable');
      setHealthError(err?.message || 'Network or CORS error');
    }
  }, []);

  useEffect(() => {
    verifyHealth();
    const interval = setInterval(verifyHealth, 30000);
    return () => clearInterval(interval);
  }, [verifyHealth]);

  const meta = PAGE_META[location.pathname] || {
    title: 'CogniTrace',
    subtitle: 'Project Handover Intelligence',
  };

  return (
    <Layout
      title={meta.title}
      subtitle={meta.subtitle}
      backendStatus={backendStatus}
      healthError={healthError}
      onRetryHealth={verifyHealth}
    >
      <Routes>
        <Route path="/" element={<DashboardOverview />} />
        <Route path="/upload" element={<UploadDocuments />} />
        <Route path="/evidence" element={<EvidenceExplorer />} />
        <Route path="/claims" element={<ClaimVerification />} />
        <Route path="/reports" element={<HandoverReports />} />
        <Route
          path="/settings"
          element={<Settings backendStatus={backendStatus} onRetryHealth={verifyHealth} />}
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  );
}
