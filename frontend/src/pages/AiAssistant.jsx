import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Sparkles,
  Send,
  RotateCcw,
  FileText,
  BarChart2,
  PieChart as PieIcon,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  ShieldCheck,
  Bot,
  User,
  Info,
  HelpCircle,
  Database,
  GitCommit,
  MessageSquare,
  ListTodo,
  Plus,
  Trash2,
  History,
  PanelLeftOpen,
  PanelLeftClose,
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import {
  sendChatMessage,
  getChatSuggestions,
  clearChatSession,
  listConversations,
  createConversation,
  getConversationDetail,
  deleteConversation,
  getClientId,
} from '../api/client';

// Palette for dynamic charts
const CHART_COLORS = [
  '#3b82f6', // blue
  '#10b981', // emerald
  '#f59e0b', // amber
  '#ef4444', // red
  '#8b5cf6', // purple
  '#06b6d4', // cyan
  '#ec4899', // pink
  '#64748b', // slate
];

function generateSessionId() {
  const rand = Math.random().toString(36).substring(2, 9);
  return `sess_${Date.now()}_${rand}`;
}

// Lightweight, safe markdown formatter for assistant answers
function FormattedMarkdown({ content }) {
  if (!content) return null;

  // Split into lines to parse paragraphs, headers, and bullet lists
  const lines = content.split('\n');
  const elements = [];
  let currentList = [];
  let inCodeBlock = false;
  let codeBlockLines = [];

  const flushList = (keyPrefix) => {
    if (currentList.length > 0) {
      elements.push(
        <ul key={`${keyPrefix}-list`} className="my-2 space-y-1 list-disc pl-5 text-sm text-slate-700">
          {currentList.map((item, idx) => (
            <li key={idx} dangerouslySetInnerHTML={{ __html: renderInline(item) }} />
          ))}
        </ul>
      );
      currentList = [];
    }
  };

  const flushCodeBlock = (keyPrefix) => {
    if (codeBlockLines.length > 0) {
      elements.push(
        <pre key={`${keyPrefix}-code`} className="my-2 p-3 bg-slate-900 text-slate-100 rounded-lg text-xs font-mono overflow-x-auto">
          <code>{codeBlockLines.join('\n')}</code>
        </pre>
      );
      codeBlockLines = [];
    }
  };

  const renderInline = (text) => {
    return text
      // Bold
      .replace(/\*\*(.*?)\*\*/g, '<strong class="font-semibold text-slate-900">$1</strong>')
      // Italic
      .replace(/\*(.*?)\*/g, '<em class="italic text-slate-700">$1</em>')
      // Inline code
      .replace(/`([^`]+)`/g, '<code class="px-1.5 py-0.5 rounded bg-slate-100 text-slate-800 text-xs font-mono border border-slate-200">$1</code>');
  };

  lines.forEach((line, index) => {
    const trimmed = line.trim();

    // Code block toggle
    if (trimmed.startsWith('```')) {
      if (inCodeBlock) {
        flushCodeBlock(`cb-${index}`);
        inCodeBlock = false;
      } else {
        flushList(`before-cb-${index}`);
        inCodeBlock = true;
      }
      return;
    }

    if (inCodeBlock) {
      codeBlockLines.push(line);
      return;
    }

    // Headers
    if (trimmed.startsWith('### ')) {
      flushList(`h3-${index}`);
      elements.push(
        <h3 key={`h3-${index}`} className="text-base font-semibold text-slate-900 mt-3 mb-1.5 flex items-center gap-2">
          {trimmed.replace('### ', '')}
        </h3>
      );
      return;
    }

    if (trimmed.startsWith('#### ')) {
      flushList(`h4-${index}`);
      elements.push(
        <h4 key={`h4-${index}`} className="text-sm font-semibold text-slate-800 mt-2.5 mb-1">
          {trimmed.replace('#### ', '')}
        </h4>
      );
      return;
    }

    // Bullet points
    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      currentList.push(trimmed.substring(2));
      return;
    }

    // Blank line
    if (!trimmed) {
      flushList(`blank-${index}`);
      return;
    }

    // Standard paragraph
    flushList(`p-${index}`);
    elements.push(
      <p
        key={`p-${index}`}
        className="text-sm text-slate-700 leading-relaxed my-1.5"
        dangerouslySetInnerHTML={{ __html: renderInline(trimmed) }}
      />
    );
  });

  flushList('end');
  flushCodeBlock('end');

  return <div className="space-y-1">{elements}</div>;
}

// Dynamic Visualization Component with Chart Type Switching
function DynamicChart({ spec }) {
  const [activeType, setActiveType] = useState(spec?.chart_type || 'bar');

  if (!spec || !spec.data || spec.data.length === 0) {
    return (
      <div className="my-3 p-4 bg-slate-50 border border-slate-200 rounded-xl text-center text-xs text-slate-500">
        <Database className="w-5 h-5 mx-auto text-slate-400 mb-1" />
        No visualization data points available for this dataset.
      </div>
    );
  }

  const { title, data, x_key = 'label', y_key = 'value', description } = spec;

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-navy-900 text-white text-xs px-3 py-2 rounded-lg shadow-lg border border-navy-700">
          <p className="font-semibold text-navy-100">{label || payload[0].name}</p>
          <p className="text-accent-light font-mono font-medium mt-0.5">
            Value: {payload[0].value}
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="my-3 p-4 bg-white border border-slate-200 rounded-xl shadow-xs">
      {/* Chart Header & Type Switcher */}
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3 pb-2 border-b border-slate-100">
        <div>
          <h4 className="text-sm font-semibold text-slate-900 flex items-center gap-1.5">
            {activeType === 'pie' ? (
              <PieIcon className="w-4 h-4 text-accent" />
            ) : activeType === 'line' ? (
              <TrendingUp className="w-4 h-4 text-accent" />
            ) : (
              <BarChart2 className="w-4 h-4 text-accent" />
            )}
            {title}
          </h4>
          {description && (
            <p className="text-xs text-slate-500 mt-0.5">{description}</p>
          )}
        </div>

        {/* View switcher buttons */}
        <div className="inline-flex items-center rounded-lg bg-slate-100 p-0.5 border border-slate-200 text-xs">
          <button
            type="button"
            onClick={() => setActiveType('bar')}
            className={`px-2 py-1 rounded-md font-medium flex items-center gap-1 transition-colors ${
              activeType === 'bar' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'
            }`}
            title="Bar View"
          >
            <BarChart2 className="w-3.5 h-3.5" />
            Bar
          </button>
          <button
            type="button"
            onClick={() => setActiveType('pie')}
            className={`px-2 py-1 rounded-md font-medium flex items-center gap-1 transition-colors ${
              activeType === 'pie' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'
            }`}
            title="Pie View"
          >
            <PieIcon className="w-3.5 h-3.5" />
            Pie
          </button>
          <button
            type="button"
            onClick={() => setActiveType('line')}
            className={`px-2 py-1 rounded-md font-medium flex items-center gap-1 transition-colors ${
              activeType === 'line' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'
            }`}
            title="Line View"
          >
            <TrendingUp className="w-3.5 h-3.5" />
            Line
          </button>
        </div>
      </div>

      {/* Responsive Chart Container */}
      <div className="w-full h-64">
        <ResponsiveContainer width="100%" height="100%">
          {activeType === 'pie' ? (
            <PieChart>
              <Pie
                data={data}
                dataKey={y_key}
                nameKey={x_key}
                cx="50%"
                cy="50%"
                outerRadius={80}
                innerRadius={30}
                paddingAngle={2}
                label={({ name, value }) => `${name}: ${value}`}
              >
                {data.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
              <Legend
                verticalAlign="bottom"
                height={36}
                formatter={(val) => <span className="text-xs text-slate-700">{val}</span>}
              />
            </PieChart>
          ) : activeType === 'line' ? (
            <LineChart data={data} margin={{ top: 10, right: 20, left: -10, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey={x_key} tick={{ fontSize: 11, fill: '#64748b' }} angle={-15} textAnchor="end" />
              <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#64748b' }} />
              <Tooltip content={<CustomTooltip />} />
              <Line
                type="monotone"
                dataKey={y_key}
                stroke="#3b82f6"
                strokeWidth={2.5}
                dot={{ r: 4, fill: '#3b82f6' }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          ) : (
            <BarChart data={data} margin={{ top: 10, right: 20, left: -10, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey={x_key} tick={{ fontSize: 11, fill: '#64748b' }} angle={-15} textAnchor="end" />
              <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#64748b' }} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey={y_key} radius={[4, 4, 0, 0]}>
                {data.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>

      {/* Provenance Footer */}
      <div className="mt-2 pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
        <span className="flex items-center gap-1">
          <Database className="w-3 h-3 text-slate-400" />
          Source: CogniTrace Analytics Engine
        </span>
        <span>{data.length} data point(s) rendered</span>
      </div>
    </div>
  );
}

// Citation Reference Cards Component
function CitationsList({ citations }) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!citations || citations.length === 0) return null;

  const displayList = isExpanded ? citations : citations.slice(0, 3);

  const getSourceIcon = (type) => {
    switch (type) {
      case 'task':
        return <ListTodo className="w-3.5 h-3.5 text-blue-500" />;
      case 'git':
        return <GitCommit className="w-3.5 h-3.5 text-purple-500" />;
      case 'chat':
        return <MessageSquare className="w-3.5 h-3.5 text-emerald-500" />;
      default:
        return <FileText className="w-3.5 h-3.5 text-amber-500" />;
    }
  };

  const getSourceBadgeColor = (type) => {
    switch (type) {
      case 'task':
        return 'bg-blue-50 text-blue-700 border-blue-200';
      case 'git':
        return 'bg-purple-50 text-purple-700 border-purple-200';
      case 'chat':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200';
      default:
        return 'bg-amber-50 text-amber-700 border-amber-200';
    }
  };

  return (
    <div className="mt-3 pt-3 border-t border-slate-100">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-slate-700 flex items-center gap-1.5">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
          Verified Evidence Citations ({citations.length})
        </span>
        {citations.length > 3 && (
          <button
            type="button"
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-xs text-accent hover:text-accent-dark font-medium flex items-center gap-0.5"
          >
            {isExpanded ? (
              <>Show Less <ChevronUp className="w-3.5 h-3.5" /></>
            ) : (
              <>View All ({citations.length}) <ChevronDown className="w-3.5 h-3.5" /></>
            )}
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-2">
        {displayList.map((c, i) => (
          <div
            key={i}
            className="p-2.5 bg-slate-50/80 rounded-lg border border-slate-200/80 text-xs flex flex-col gap-1 transition-colors hover:bg-slate-50"
          >
            <div className="flex flex-wrap items-center justify-between gap-1">
              <div className="flex items-center gap-1.5">
                {getSourceIcon(c.source_type)}
                <span className="font-semibold text-slate-900 truncate max-w-xs">
                  {c.source_filename}
                </span>
                <span className={`px-1.5 py-0.2 rounded text-[10px] font-medium border uppercase tracking-wider ${getSourceBadgeColor(c.source_type)}`}>
                  {c.source_type || 'doc'}
                </span>
              </div>

              <div className="flex items-center gap-1 text-[11px] text-slate-500">
                {c.record_id && (
                  <span className="font-mono bg-white px-1 rounded border border-slate-200">
                    {c.record_id}
                  </span>
                )}
                {c.chunk_id && <span>Chunk #{c.chunk_id}</span>}
                {c.claim_id && <span>Claim #{c.claim_id}</span>}
                <Link
                  to="/evidence"
                  className="ml-1 text-slate-400 hover:text-accent"
                  title="View in Evidence Explorer"
                >
                  <ExternalLink className="w-3 h-3" />
                </Link>
              </div>
            </div>

            <p className="text-slate-600 italic bg-white/70 p-1.5 rounded border border-slate-100 line-clamp-3">
              "{c.excerpt}"
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

// Chat History Sidebar Component
function ChatHistorySidebar({ conversations, activeConversationId, onSelect, onDelete, onNewChat, isOpen, onToggle }) {
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);

  const handleDelete = async (e, convId) => {
    e.stopPropagation();
    if (confirmDeleteId === convId) {
      await onDelete(convId);
      setConfirmDeleteId(null);
    } else {
      setConfirmDeleteId(convId);
      setTimeout(() => setConfirmDeleteId(null), 3000);
    }
  };

  if (!isOpen) {
    return (
      <button
        type="button"
        onClick={onToggle}
        className="absolute left-0 top-3 z-10 p-2 bg-white border border-slate-200 rounded-r-lg shadow-xs text-slate-500 hover:text-accent transition-colors"
        title="Show chat history"
      >
        <PanelLeftOpen className="w-4 h-4" />
      </button>
    );
  }

  return (
    <div className="w-64 shrink-0 bg-white border border-slate-200 rounded-xl shadow-xs flex flex-col overflow-hidden mr-3">
      {/* Header */}
      <div className="p-3 border-b border-slate-100 flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-700 flex items-center gap-1.5">
          <History className="w-3.5 h-3.5 text-accent" />
          Chat History
        </span>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={onNewChat}
            className="p-1.5 rounded-lg text-slate-500 hover:text-accent hover:bg-accent/10 transition-colors"
            title="New Chat"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={onToggle}
            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-700 transition-colors"
            title="Hide sidebar"
          >
            <PanelLeftClose className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {conversations.length === 0 && (
          <p className="text-xs text-slate-400 text-center py-6">No conversations yet</p>
        )}
        {conversations.map((conv) => (
          <button
            key={conv.id}
            type="button"
            onClick={() => onSelect(conv.id)}
            className={`w-full text-left p-2.5 rounded-lg text-xs transition-all group ${
              activeConversationId === conv.id
                ? 'bg-accent/10 border border-accent/30 text-accent'
                : 'hover:bg-slate-50 border border-transparent text-slate-700'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="font-medium truncate flex-1 mr-1">{conv.title}</span>
              <button
                type="button"
                onClick={(e) => handleDelete(e, conv.id)}
                className={`shrink-0 p-1 rounded transition-colors ${
                  confirmDeleteId === conv.id
                    ? 'text-rose-600 bg-rose-50'
                    : 'text-slate-400 opacity-0 group-hover:opacity-100 hover:text-rose-500'
                }`}
                title={confirmDeleteId === conv.id ? 'Click again to confirm' : 'Delete conversation'}
              >
                <Trash2 className="w-3 h-3" />
              </button>
            </div>
            <div className="flex items-center gap-2 mt-1 text-[10px] text-slate-400">
              <span>{conv.message_count || 0} messages</span>
              <span>·</span>
              <span>{new Date(conv.updated_at).toLocaleDateString()}</span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

// Main AI Assistant Page Component
export default function AiAssistant() {
  // Conversation state
  const [conversationId, setConversationId] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Legacy session fallback
  const [sessionId, setSessionId] = useState(() => {
    const saved = sessionStorage.getItem('cognitrace_chat_session_id');
    if (saved) return saved;
    const newId = generateSessionId();
    sessionStorage.setItem('cognitrace_chat_session_id', newId);
    return newId;
  });

  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorBanner, setErrorBanner] = useState('');
  const [suggestions, setSuggestions] = useState([]);

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Auto-scroll to bottom on new messages
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  // Load starter suggestions
  const fetchSuggestions = useCallback(async () => {
    try {
      const data = await getChatSuggestions();
      if (data?.suggestions) {
        setSuggestions(data.suggestions);
      }
    } catch (err) {
      console.warn('Failed to fetch chat suggestions:', err);
    }
  }, []);

  // Load persistent conversations
  const fetchConversations = useCallback(async () => {
    try {
      const data = await listConversations();
      setConversations(data || []);
    } catch (err) {
      console.warn('Failed to fetch conversations:', err);
    }
  }, []);

  useEffect(() => {
    fetchSuggestions();
    fetchConversations();
  }, [fetchSuggestions, fetchConversations]);

  // Load a specific conversation's messages from the backend
  const handleSelectConversation = useCallback(async (convId) => {
    setConversationId(convId);
    setErrorBanner('');
    try {
      const detail = await getConversationDetail(convId);
      const loaded = (detail.messages || []).map((m) => ({
        role: m.role,
        content: m.content,
        intent: m.intent || null,
        citations: m.citations || [],
        chart_spec: m.chart_spec || null,
        follow_up_suggestions: m.follow_up_suggestions || [],
        timestamp: m.created_at
          ? new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          : '',
      }));
      setMessages(loaded);
    } catch (err) {
      console.error('Failed to load conversation:', err);
      setErrorBanner('Failed to load conversation history.');
    }
  }, []);

  // Handle New Chat / Reset Session
  const handleNewChat = async () => {
    try {
      const conv = await createConversation();
      setConversationId(conv.id);
      await fetchConversations();
    } catch {
      // fallback to legacy session
      const newId = generateSessionId();
      setSessionId(newId);
      sessionStorage.setItem('cognitrace_chat_session_id', newId);
      setConversationId(null);
    }
    setMessages([]);
    setErrorBanner('');
    setInputMessage('');
    if (inputRef.current) inputRef.current.focus();
  };

  // Delete a conversation
  const handleDeleteConversation = async (convId) => {
    try {
      await deleteConversation(convId);
      if (conversationId === convId) {
        setConversationId(null);
        setMessages([]);
      }
      await fetchConversations();
    } catch (err) {
      console.error('Failed to delete conversation:', err);
      setErrorBanner('Failed to delete conversation.');
    }
  };

  // Send message
  const handleSendMessage = async (textToSend = null) => {
    const text = (textToSend !== null ? textToSend : inputMessage).trim();
    if (!text || isLoading) return;

    setErrorBanner('');
    const userTurn = {
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userTurn]);
    setInputMessage('');
    setIsLoading(true);

    try {
      const response = await sendChatMessage(sessionId, text, conversationId);

      // Track the conversation_id returned by the backend
      if (response.conversation_id && !conversationId) {
        setConversationId(response.conversation_id);
        // Refresh sidebar to show the new conversation
        fetchConversations();
      }

      const assistantTurn = {
        role: 'assistant',
        content: response.answer,
        intent: response.intent,
        citations: response.citations || [],
        chart_spec: response.chart_spec || null,
        follow_up_suggestions: response.follow_up_suggestions || [],
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setMessages((prev) => [...prev, assistantTurn]);
    } catch (err) {
      console.error('Chat error:', err);
      setErrorBanner(err.message || 'Failed to communicate with CogniTrace backend.');
    } finally {
      setIsLoading(false);
      if (inputRef.current) inputRef.current.focus();
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="flex h-[calc(100vh-8rem)] max-w-7xl mx-auto relative">
      {/* Chat History Sidebar */}
      <ChatHistorySidebar
        conversations={conversations}
        activeConversationId={conversationId}
        onSelect={handleSelectConversation}
        onDelete={handleDeleteConversation}
        onNewChat={handleNewChat}
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
      />

      {/* Main Chat Area */}
      <div className="flex flex-col flex-1 min-w-0">
      {/* Top Controls Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3 p-3 bg-white rounded-xl border border-slate-200 shadow-xs">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-accent/10 text-accent flex items-center justify-center font-semibold">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold text-slate-900 leading-none">
                CogniTrace AI Assistant
              </h2>
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                <ShieldCheck className="w-3 h-3" />
                No Citation, No Assertion
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Evidence-grounded project analysis & dynamic visualization
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono text-slate-400 bg-slate-100 px-2 py-1 rounded border border-slate-200 truncate max-w-[130px]">
            {conversationId || sessionId}
          </span>
          <button
            type="button"
            onClick={handleNewChat}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 border border-slate-200 transition-colors"
            title="Start a fresh conversation"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            New Chat
          </button>
        </div>
      </div>

      {/* Error Banner */}
      {errorBanner && (
        <div className="mb-3 p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{errorBanner}</span>
          </div>
          <button
            type="button"
            onClick={() => handleSendMessage()}
            className="text-xs font-semibold text-rose-700 underline hover:text-rose-900 ml-2"
          >
            Retry
          </button>
        </div>
      )}

      {/* Chat Messages Container */}
      <div className="flex-1 overflow-y-auto px-1 py-2 space-y-4 rounded-xl">
        {/* Welcome Empty State */}
        {messages.length === 0 && (
          <div className="my-auto py-8 px-4 text-center max-w-2xl mx-auto">
            <div className="w-14 h-14 mx-auto rounded-2xl bg-gradient-to-tr from-accent to-blue-400 text-white flex items-center justify-center shadow-md mb-4">
              <Bot className="w-7 h-7" />
            </div>
            <h3 className="text-lg font-bold text-slate-900 tracking-tight">
              What would you like to explore today?
            </h3>
            <p className="text-xs text-slate-500 mt-1.5 max-w-md mx-auto leading-relaxed">
              Ask natural-language questions about task progress, Git commit velocity,
              unresolved conflicts, or ask for dynamic visual charts.
            </p>

            {/* Quick Starters */}
            <div className="mt-6 text-left">
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2.5 text-center">
                Recommended Inquiries
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {[
                  {
                    icon: <CheckCircle2 className="w-4 h-4 text-emerald-500" />,
                    text: 'What is the current project status?',
                    desc: 'High-level health and metrics snapshot',
                  },
                  {
                    icon: <ListTodo className="w-4 h-4 text-blue-500" />,
                    text: 'Which tasks are completed and pending?',
                    desc: 'Deduplicated tasks & assignees',
                  },
                  {
                    icon: <BarChart2 className="w-4 h-4 text-indigo-500" />,
                    text: 'Show completed vs pending tasks in a bar graph',
                    desc: 'Visual task comparison bar chart',
                  },
                  {
                    icon: <TrendingUp className="w-4 h-4 text-accent" />,
                    text: 'Show Git commits over time using a line chart',
                    desc: 'Chronological commit activity graph',
                  },
                  {
                    icon: <PieIcon className="w-4 h-4 text-amber-500" />,
                    text: 'Generate a pie chart of task priority distribution',
                    desc: 'Critical vs High vs Medium tasks',
                  },
                  {
                    icon: <AlertTriangle className="w-4 h-4 text-rose-500" />,
                    text: 'Explain all detected contradictions',
                    desc: 'Discrepancies across tasks and chat records',
                  },
                ].map((item, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => handleSendMessage(item.text)}
                    className="p-3 bg-white hover:bg-slate-50 rounded-xl border border-slate-200 text-left transition-all hover:border-accent/60 hover:shadow-xs group"
                  >
                    <div className="flex items-center gap-2 text-xs font-semibold text-slate-800 group-hover:text-accent">
                      {item.icon}
                      <span>{item.text}</span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-1 pl-6">
                      {item.desc}
                    </p>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Message Thread */}
        {messages.map((msg, index) => {
          const isUser = msg.role === 'user';

          return (
            <div
              key={index}
              className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}
            >
              {/* Assistant Avatar */}
              {!isUser && (
                <div className="w-8 h-8 rounded-lg bg-navy-900 text-white flex items-center justify-center shrink-0 mt-1 shadow-xs">
                  <Bot className="w-4 h-4" />
                </div>
              )}

              {/* Bubble Body */}
              <div
                className={`max-w-3xl rounded-2xl p-4 shadow-xs ${
                  isUser
                    ? 'bg-navy-900 text-white rounded-tr-xs'
                    : 'bg-white border border-slate-200 text-slate-800 rounded-tl-xs'
                }`}
              >
                {/* Header info */}
                <div className="flex items-center justify-between gap-2 mb-1.5 text-[11px] opacity-70">
                  <span className="font-semibold">
                    {isUser ? 'You' : 'CogniTrace Assistant'}
                  </span>
                  <span>{msg.timestamp}</span>
                </div>

                {/* Content */}
                {isUser ? (
                  <p className="text-sm leading-relaxed whitespace-pre-wrap">
                    {msg.content}
                  </p>
                ) : (
                  <div>
                    <FormattedMarkdown content={msg.content} />

                    {/* Dynamic Chart if spec present */}
                    {msg.chart_spec && (
                      <DynamicChart spec={msg.chart_spec} />
                    )}

                    {/* Verified Evidence Citations */}
                    {msg.citations && msg.citations.length > 0 && (
                      <CitationsList citations={msg.citations} />
                    )}

                    {/* Follow-up Suggestions Chips */}
                    {msg.follow_up_suggestions && msg.follow_up_suggestions.length > 0 && (
                      <div className="mt-3 pt-2.5 border-t border-slate-100">
                        <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1.5">
                          Follow-up Questions
                        </span>
                        <div className="flex flex-wrap gap-1.5">
                          {msg.follow_up_suggestions.map((suggestion, sIdx) => (
                            <button
                              key={sIdx}
                              type="button"
                              onClick={() => handleSendMessage(suggestion)}
                              className="px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 hover:bg-accent hover:text-white text-slate-700 border border-slate-200 transition-colors"
                            >
                              {suggestion}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* User Avatar */}
              {isUser && (
                <div className="w-8 h-8 rounded-lg bg-accent text-white flex items-center justify-center shrink-0 mt-1 shadow-xs">
                  <User className="w-4 h-4" />
                </div>
              )}
            </div>
          );
        })}

        {/* Loading Indicator */}
        {isLoading && (
          <div className="flex gap-3 justify-start items-start">
            <div className="w-8 h-8 rounded-lg bg-navy-900 text-white flex items-center justify-center shrink-0 mt-1 shadow-xs">
              <Bot className="w-4 h-4 animate-pulse" />
            </div>
            <div className="bg-white border border-slate-200 rounded-2xl rounded-tl-xs p-4 shadow-xs">
              <div className="flex items-center gap-2 text-xs font-medium text-slate-600">
                <span className="flex space-x-1">
                  <span className="w-2 h-2 bg-accent rounded-full animate-bounce [animation-delay:-0.3s]"></span>
                  <span className="w-2 h-2 bg-accent rounded-full animate-bounce [animation-delay:-0.15s]"></span>
                  <span className="w-2 h-2 bg-accent rounded-full animate-bounce"></span>
                </span>
                <span>Retrieving evidence and synthesizing grounded response...</span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Form Bar */}
      <div className="mt-3 pt-2">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage();
          }}
          className="flex items-center gap-2 bg-white rounded-xl border border-slate-200 p-2 shadow-sm focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/10 transition-all"
        >
          <input
            ref={inputRef}
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about project status, tasks, Git commits, contradictions, or request a chart..."
            disabled={isLoading}
            className="flex-1 px-3 py-2 text-sm text-slate-900 bg-transparent border-0 focus:outline-none placeholder-slate-400 disabled:opacity-50"
          />

          <button
            type="submit"
            disabled={!inputMessage.trim() || isLoading}
            className="inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg bg-accent hover:bg-accent-dark text-white text-xs font-semibold shadow-xs transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Send className="w-3.5 h-3.5" />
            <span>Send</span>
          </button>
        </form>

        <p className="text-[11px] text-center text-slate-400 mt-2 flex items-center justify-center gap-1">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
          Answers strictly cite uploaded project records. AI cannot invent unrecorded facts or statuses.
        </p>
      </div>
      </div>
    </div>
  );
}
