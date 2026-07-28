/**
 * AgentChat Component - ChatGPT-style conversational interface for the AI receptionist / BI analyst.
 * Driven by React, TypeScript, Tailwind CSS, and communicating with the FastAPI agent backend.
 */

import React, { useState, useEffect, useRef } from 'react';
import { apiClient } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend
} from 'recharts';

/**
 * Lightweight inline Markdown renderer for assistant chat messages.
 * Supports: **bold**, *italic*, `code`, headers (#-####), bullet lists, numbered lists, tables, and line breaks.
 */
function renderMarkdown(text: string): React.ReactNode {
  if (!text) return null;
  const lines = text.split('\n');
  const elements: React.ReactNode[] = [];
  let tableBuffer: string[] = [];
  let listBuffer: { type: 'ul' | 'ol'; items: string[] } | null = null;

  const flushList = () => {
    if (!listBuffer) return;
    const Tag = listBuffer.type === 'ul' ? 'ul' : 'ol';
    elements.push(
      <Tag key={`list-${elements.length}`} className={listBuffer.type === 'ul' ? 'list-disc pl-5 my-1' : 'list-decimal pl-5 my-1'}>
        {listBuffer.items.map((item, i) => <li key={i}>{inlineFormat(item)}</li>)}
      </Tag>
    );
    listBuffer = null;
  };

  const flushTable = () => {
    if (tableBuffer.length < 2) {
      tableBuffer.forEach(l => elements.push(<p key={`p-${elements.length}`}>{inlineFormat(l)}</p>));
      tableBuffer = [];
      return;
    }
    // Parse table
    const rows = tableBuffer.filter(r => !r.match(/^\|?[\s\-:|]+\|?$/));
    const parseRow = (row: string) => row.split('|').map(c => c.trim()).filter(c => c.length > 0);
    const headerCells = rows.length > 0 ? parseRow(rows[0]) : [];
    const bodyRows = rows.slice(1).map(parseRow);
    elements.push(
      <div key={`tbl-${elements.length}`} className="overflow-x-auto my-3 rounded-xl border border-neutral-800">
        <table className="min-w-full border-collapse text-xs">
          {headerCells.length > 0 && (
            <thead>
              <tr className="border-b border-neutral-800 bg-neutral-900/60">
                {headerCells.map((c, i) => <th key={i} className="px-3 py-2 text-left font-semibold text-neutral-300">{inlineFormat(c)}</th>)}
              </tr>
            </thead>
          )}
          <tbody>
            {bodyRows.map((row, ri) => (
              <tr key={ri} className="border-b border-neutral-800/60 last:border-0">
                {row.map((c, ci) => <td key={ci} className="px-3 py-2 text-neutral-300">{inlineFormat(c)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
    tableBuffer = [];
  };

  const inlineFormat = (text: string): React.ReactNode => {
    // Bold + Italic
    const parts: React.ReactNode[] = [];
    const regex = /(\*\*\*(.+?)\*\*\*|\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`)/g;
    let lastIndex = 0;
    let match;
    while ((match = regex.exec(text)) !== null) {
      if (match.index > lastIndex) parts.push(text.slice(lastIndex, match.index));
      if (match[2]) parts.push(<strong key={match.index}><em>{match[2]}</em></strong>);
      else if (match[3]) parts.push(<strong key={match.index} className="text-neutral-50 font-semibold">{match[3]}</strong>);
      else if (match[4]) parts.push(<em key={match.index}>{match[4]}</em>);
      else if (match[5]) parts.push(<code key={match.index} className="bg-neutral-800 px-1.5 py-0.5 rounded text-[13px] text-neutral-200 font-mono">{match[5]}</code>);
      lastIndex = regex.lastIndex;
    }
    if (lastIndex < text.length) parts.push(text.slice(lastIndex));
    return parts.length === 1 ? parts[0] : <>{parts}</>;
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    // Table rows
    if (trimmed.startsWith('|') || (trimmed.includes('|') && tableBuffer.length > 0)) {
      flushList();
      tableBuffer.push(trimmed);
      continue;
    } else if (tableBuffer.length > 0) {
      flushTable();
    }

    // Bullet list
    const ulMatch = trimmed.match(/^[\-\*•+]\s+(.+)/);
    if (ulMatch) {
      if (listBuffer && listBuffer.type !== 'ul') flushList();
      if (!listBuffer) listBuffer = { type: 'ul', items: [] };
      listBuffer.items.push(ulMatch[1]);
      continue;
    }

    // Numbered list
    const olMatch = trimmed.match(/^\d+[\.\)]\s+(.+)/);
    if (olMatch) {
      if (listBuffer && listBuffer.type !== 'ol') flushList();
      if (!listBuffer) listBuffer = { type: 'ol', items: [] };
      listBuffer.items.push(olMatch[1]);
      continue;
    }

    // Flush any pending list
    if (listBuffer) flushList();

    // Headers
    if (trimmed.startsWith('#### ')) {
      elements.push(<h6 key={`h-${i}`} className="text-xs font-semibold text-neutral-200 mt-3 mb-1">{inlineFormat(trimmed.slice(5))}</h6>);
    } else if (trimmed.startsWith('### ')) {
      elements.push(<h5 key={`h-${i}`} className="text-sm font-semibold text-neutral-200 mt-3 mb-1">{inlineFormat(trimmed.slice(4))}</h5>);
    } else if (trimmed.startsWith('## ')) {
      elements.push(<h4 key={`h-${i}`} className="text-base font-semibold text-neutral-100 mt-3 mb-1">{inlineFormat(trimmed.slice(3))}</h4>);
    } else if (trimmed.startsWith('# ')) {
      elements.push(<h3 key={`h-${i}`} className="text-lg font-semibold text-neutral-100 mt-3 mb-1.5">{inlineFormat(trimmed.slice(2))}</h3>);
    } else if (trimmed === '' || trimmed === '---') {
      if (trimmed === '---') elements.push(<hr key={`hr-${i}`} className="border-neutral-800 my-3" />);
      else if (elements.length > 0) elements.push(<div key={`br-${i}`} className="h-2" />);
    } else {
      elements.push(<p key={`p-${i}`} className="my-1">{inlineFormat(trimmed)}</p>);
    }
  }

  // Flush remaining
  if (tableBuffer.length > 0) flushTable();
  if (listBuffer) flushList();

  return <div>{elements}</div>;
}

interface InlineChartRendererProps {
  data: {
    type: 'bar' | 'line' | 'pie';
    title?: string;
    series: Array<{ label: string; value: number }>;
  };
}

const COLORS = ['#3b82f6', '#10b981', '#8b5cf6', '#f59e0b', '#ec4899', '#06b6d4', '#f43f5e'];

const InlineChartRenderer: React.FC<InlineChartRendererProps> = React.memo(({ data }) => {
  if (!data || !data.series || !Array.isArray(data.series) || data.series.length === 0) {
    return null;
  }

  const chartType = data.type || 'bar';
  const chartTitle = data.title || 'Analytics Graph';
  const chartData = data.series.map(item => ({
    name: item.label,
    value: Number(item.value)
  }));

  return (
    <div className="w-full mt-3 p-4 rounded-2xl bg-neutral-900 border border-neutral-800">
      <h5 className="text-xs font-medium text-neutral-400 mb-3">{chartTitle}</h5>
      <div className="w-full h-48 text-xs font-medium">
        <ResponsiveContainer width="100%" height="100%">
          {chartType === 'line' ? (
            <LineChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#292929" />
              <XAxis dataKey="name" stroke="#737373" tickLine={false} />
              <YAxis stroke="#737373" tickLine={false} />
              <Tooltip
                contentStyle={{ backgroundColor: '#171717', borderColor: '#404040', borderRadius: '8px' }}
                labelStyle={{ color: '#a3a3a3', fontWeight: 'bold' }}
              />
              <Line type="monotone" dataKey="value" stroke="#3b82f6" strokeWidth={2} dot={{ fill: '#3b82f6', r: 3 }} activeDot={{ r: 5 }} />
            </LineChart>
          ) : chartType === 'pie' ? (
            <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="50%"
                innerRadius={40}
                outerRadius={65}
                paddingAngle={3}
                dataKey="value"
              >
                {chartData.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{ backgroundColor: '#171717', borderColor: '#404040', borderRadius: '8px' }}
                itemStyle={{ color: '#fff' }}
              />
              <Legend verticalAlign="bottom" height={36} iconType="circle" iconSize={8} wrapperStyle={{ fontSize: '10px' }} />
            </PieChart>
          ) : (
            <BarChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#292929" />
              <XAxis dataKey="name" stroke="#737373" tickLine={false} />
              <YAxis stroke="#737373" tickLine={false} />
              <Tooltip
                contentStyle={{ backgroundColor: '#171717', borderColor: '#404040', borderRadius: '8px' }}
                labelStyle={{ color: '#a3a3a3', fontWeight: 'bold' }}
              />
              <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]}>
                {chartData.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  );
});


// Structured interface for chat messages
interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  data?: any;
  response_type?: string;
}

interface Accent {
  avatarBg: string;
  avatarText: string;
  sendBg: string;
}

// Memoized so an unrelated re-render of the chat (e.g. the input box
// changing, or a new message being appended) doesn't re-run the markdown
// parser over every prior message in the conversation — without this, a
// long chat session gets progressively slower to type in as history grows.
const ChatMessageBubble = React.memo<{ msg: Message; assistantInitial: string; accent: Accent }>(
  ({ msg, assistantInitial, accent }) => {
    const isUser = msg.role === 'user';
    const renderedContent = React.useMemo(
      () => (isUser ? null : renderMarkdown(msg.content)),
      [isUser, msg.content]
    );

    return (
      <div className="w-full py-3">
        <div className={`max-w-3xl mx-auto px-4 md:px-6 flex gap-4 ${isUser ? 'justify-end' : ''}`}>
          {!isUser && (
            <div className={`w-8 h-8 rounded-full flex items-center justify-center font-semibold text-xs shrink-0 mt-0.5 ${accent.avatarBg} ${accent.avatarText}`}>
              {assistantInitial}
            </div>
          )}

          <div className={`flex flex-col ${isUser ? 'items-end max-w-[75%]' : 'flex-1 min-w-0'}`}>
            {isUser ? (
              <div className="px-4 py-2.5 rounded-3xl bg-neutral-700/70 text-neutral-50 text-[14px] leading-relaxed">
                <p className="whitespace-pre-wrap">{msg.content}</p>
              </div>
            ) : (
              <div className="text-[14px] leading-relaxed text-neutral-100 whitespace-pre-wrap">
                {renderedContent}
                {msg.response_type === 'visualization' && msg.data && (
                  <InlineChartRenderer data={msg.data} />
                )}
              </div>
            )}
            <span className="text-[10px] text-neutral-500 mt-1">{msg.timestamp}</span>
          </div>
        </div>
      </div>
    );
  }
);

// Session metadata interface
interface ChatSession {
  id: string;
  title: string;
  lastActive: string;
  messages: Message[];
}

interface AgentChatProps {
  onRefreshAppointments?: () => void;
  intentOverride?: string;
}

export const AgentChat: React.FC<AgentChatProps> = ({ onRefreshAppointments, intentOverride }) => {
  const isBI = intentOverride === 'business_intelligence';
  const assistantName = isBI ? 'Atlas' : 'Clara';
  const assistantSubtitle = isBI ? 'Business Intelligence Analyst' : 'AI Salon Receptionist';
  const assistantInitial = isBI ? 'A' : 'C';
  const accent: Accent = isBI
    ? { avatarBg: 'bg-violet-500/15', avatarText: 'text-violet-400', sendBg: 'bg-violet-600 hover:bg-violet-500' }
    : { avatarBg: 'bg-blue-500/15', avatarText: 'text-blue-400', sendBg: 'bg-blue-600 hover:bg-blue-500' };

  // --- States ---
  const { user } = useAuth();
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string>('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [isHistoryOpen, setIsHistoryOpen] = useState<boolean>(true); // Open by default

  // References for scrolling / textarea auto-grow
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Get user-specific localStorage key
  const getStorageKey = (): string => {
    const prefix = isBI ? 'salonai_bi_sessions' : 'salonai_sessions';
    if (!user || !user.id) {
      return `${prefix}_anonymous`;
    }
    return `${prefix}_${user.id}`;
  };

  // --- Load Initial Sessions & Restore State ---
  useEffect(() => {
    const storageKey = getStorageKey();
    const savedSessions = localStorage.getItem(storageKey);
    if (savedSessions) {
      try {
        const parsed = JSON.parse(savedSessions) as ChatSession[];
        setSessions(parsed);
        if (parsed.length > 0) {
          setActiveSessionId(parsed[0].id);
          setMessages(parsed[0].messages);
        } else {
          createNewSession();
        }
      } catch (e) {
        console.error('Failed to parse saved sessions from localStorage:', e);
        createNewSession();
      }
    } else {
      createNewSession();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  // --- Auto-scroll to Bottom on New Messages ---
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // --- Auto-grow the input textarea as the user types ---
  useEffect(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = 'auto';
      el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
    }
  }, [inputMessage]);

  // --- Helper: Save sessions to localStorage ---
  const saveSessions = (updatedSessions: ChatSession[]) => {
    setSessions(updatedSessions);
    const storageKey = getStorageKey();
    localStorage.setItem(storageKey, JSON.stringify(updatedSessions));
  };

  // --- Action: Create New Session ---
  const createNewSession = () => {
    const newSessionId = `sess_${Math.random().toString(36).substring(2, 11)}`;
    const newSession: ChatSession = {
      id: newSessionId,
      title: isBI
        ? `BI Analysis - ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
        : `Booking Session - ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`,
      lastActive: new Date().toLocaleDateString(),
      messages: [
        {
          id: `msg_welcome_${Date.now()}`,
          role: 'assistant',
          content: isBI
            ? "Welcome to SalonAI Business Assistant. I'm Atlas, your corporate growth analyst and operational consultant. Ask me any analytical questions about revenue performance, top stylists, customer retention cohorts, lead conversions, reviews complaints, or forecasts."
            : "Hello! I'm Clara, your AI Salon Receptionist. How can I style your schedule today? I can help you check available slots, book haircuts or stone massages, reschedule, or review your historical bookings.",
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]
    };

    const updatedSessions = [newSession, ...sessions];
    saveSessions(updatedSessions);
    setActiveSessionId(newSessionId);
    setMessages(newSession.messages);
    setError(null);
  };

  // --- Action: Switch Session ---
  const handleSwitchSession = (sessionId: string) => {
    const target = sessions.find(s => s.id === sessionId);
    if (target) {
      setActiveSessionId(sessionId);
      setMessages(target.messages);
      setError(null);
    }
  };

  // --- Action: Delete Session ---
  const handleDeleteSession = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation(); // Avoid switching to the session being deleted
    const filtered = sessions.filter(s => s.id !== sessionId);

    if (filtered.length === 0) {
      // If no sessions remain, reset completely
      const storageKey = getStorageKey();
      localStorage.removeItem(storageKey);
      createNewSession();
    } else {
      saveSessions(filtered);
      if (activeSessionId === sessionId) {
        setActiveSessionId(filtered[0].id);
        setMessages(filtered[0].messages);
      }
    }
  };

  // --- Action: Send User Message ---
  const handleSendMessage = async (text: string) => {
    if (!text.trim() || isLoading) return;

    const userMsg: Message = {
      id: `msg_user_${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    // Update message state & local session records immediately
    const updatedMessages = [...messages, userMsg];
    setMessages(updatedMessages);
    setInputMessage('');
    setIsLoading(true);
    setError(null);

    // Persist user message immediately in sessions list
    const updatedSessions = sessions.map(s => {
      if (s.id === activeSessionId) {
        return { ...s, messages: updatedMessages };
      }
      return s;
    });
    saveSessions(updatedSessions);

    // Call FastAPI agent backend API
    try {
      // Pre-format context matching standard role queries
      const chatHistoryForBackend = updatedMessages
        .slice(0, -1) // Exclude the very last message we just appended
        .map(msg => ({
          role: msg.role,
          content: msg.content
        }));

      const payload: any = {
        message: text,
        'session id': activeSessionId,
        'chat history': chatHistoryForBackend
      };
      if (intentOverride) {
        payload['intent override'] = intentOverride;
      }

      const response = await apiClient.post('/agent/chat', payload);

      if (response.data && response.data.success) {
        if (onRefreshAppointments) {
          onRefreshAppointments();
        }
        const assistantMsg: Message = {
          id: `msg_assistant_${Date.now()}`,
          role: 'assistant',
          content: response.data.response,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          data: response.data.data,
          response_type: response.data.response_type
        };

        const finalMessages = [...updatedMessages, assistantMsg];
        setMessages(finalMessages);

        // Update title dynamically if it was a generic default
        const currentSession = sessions.find(s => s.id === activeSessionId);
        const hasCustomTitle = currentSession && !currentSession.title.startsWith('Booking Session -');
        const newTitle = hasCustomTitle
          ? currentSession.title
          : text.length > 25
            ? `${text.substring(0, 22)}...`
            : text;

        const finalSessions = sessions.map(s => {
          if (s.id === activeSessionId) {
            return {
              ...s,
              title: newTitle,
              messages: finalMessages
            };
          }
          return s;
        });
        saveSessions(finalSessions);
      } else {
        // If backend returned success=false but has a response field, show it as a chat message
        const fallbackMsg = response.data?.response || response.data?.error || `Failed to receive a valid response from ${assistantName}.`;
        const errorAssistantMsg: Message = {
          id: `msg_error_${Date.now()}`,
          role: 'assistant',
          content: fallbackMsg,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        const errorFinalMessages = [...updatedMessages, errorAssistantMsg];
        setMessages(errorFinalMessages);
        const errorSessions = sessions.map(s => {
          if (s.id === activeSessionId) {
            return { ...s, messages: errorFinalMessages };
          }
          return s;
        });
        saveSessions(errorSessions);
      }
    } catch (err: any) {
      console.error('Error sending chat query:', err);
      const errorMsg = err.response?.data?.detail || err.message || `Connecting to ${assistantName} timed out or failed. Is the backend API running?`;
      setError(errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  // --- Action: Retry Failed Message ---
  const handleRetry = () => {
    const lastUserMsg = [...messages].reverse().find(m => m.role === 'user');
    if (lastUserMsg) {
      setError(null);
      handleSendMessage(lastUserMsg.content);
    }
  };

  // --- Predefined Suggestions Cards ---
  const suggestions = isBI ? [
    { title: 'Revenue Analysis', prompt: 'How much revenue did we earn this month? Which branch or service earns the most?' },
    { title: 'Staff Performance', prompt: 'Who are our top performing stylists? Show stylist ratings and appointment counts.' },
    { title: 'Forecast & Growth', prompt: "Forecast next month's expected revenue and appointments." },
    { title: 'Executive Insights', prompt: 'Give me an executive context summary of salon performance.' }
  ] : [
    { title: 'Check Availability', prompt: 'What slots are available for a Signature Haircut tomorrow?' },
    { title: 'Book Appointment', prompt: "I'd like to book a Signature Haircut for tomorrow at 11 AM with Marcus." },
    { title: 'My Appointments', prompt: 'Can you show me my upcoming appointments history?' },
    { title: 'Cancel Appointment', prompt: 'I need to cancel my upcoming appointment.' }
  ];

  const isEmptyState = messages.length <= 1 && !isLoading;

  return (
    <div className="w-full max-w-7xl mx-auto flex bg-neutral-950 rounded-2xl border border-neutral-800 overflow-hidden h-full">

      {/* --- Sidebar Section (Chat Session History) --- */}
      <aside className={`bg-neutral-950 flex flex-col border-r border-neutral-800 transition-all duration-200 ease-in-out ${isHistoryOpen ? 'w-64 opacity-100' : 'w-0 opacity-0 overflow-hidden border-none'
        }`}>
        <div className="px-4 py-3.5 border-b border-neutral-800 flex items-center justify-between shrink-0">
          <span className="text-xs font-black uppercase tracking-wider text-neutral-500">Chat History</span>
          <button
            onClick={() => setIsHistoryOpen(false)}
            className="p-1.5 rounded-md hover:bg-neutral-850 text-neutral-400 hover:text-neutral-200 transition-colors cursor-pointer"
            title="Collapse Sidebar"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
          </button>
        </div>

        <div className="p-3">
          <button
            onClick={createNewSession}
            className="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg border border-neutral-700 hover:bg-neutral-800 text-sm text-neutral-200 transition-colors cursor-pointer"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            New chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-2 pb-2 space-y-0.5 custom-scrollbar">
          {sessions.map((s) => (
            <div
              key={s.id}
              onClick={() => handleSwitchSession(s.id)}
              className={`group flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer transition-colors ${s.id === activeSessionId
                  ? 'bg-neutral-800 text-neutral-100'
                  : 'text-neutral-400 hover:bg-neutral-900 hover:text-neutral-200'
                }`}
            >
              <span className="truncate text-sm">{s.title}</span>
              <button
                onClick={(e) => handleDeleteSession(e, s.id)}
                className="opacity-40 group-hover:opacity-100 p-1 rounded hover:bg-neutral-700 text-neutral-500 hover:text-red-400 transition-all cursor-pointer shrink-0"
                title="Delete Session"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>
          ))}
        </div>
      </aside>

      {/* --- Main Chat Section --- */}
      <section className="flex-1 bg-neutral-950 flex flex-col min-w-0">

        {/* Chat Area Header */}
        <header className="px-4 py-3 border-b border-neutral-800 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            {!isHistoryOpen && (
              <button
                onClick={() => setIsHistoryOpen(true)}
                className="p-1.5 rounded-md hover:bg-neutral-800 text-neutral-400 hover:text-neutral-200 transition-colors cursor-pointer"
                title="Show History"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>
            )}
            <span className="text-sm font-medium text-neutral-200">{assistantName}</span>
            <span className="text-xs text-neutral-500">{assistantSubtitle}</span>
          </div>
          <button
            onClick={createNewSession}
            className="p-1.5 rounded-md hover:bg-neutral-800 text-neutral-400 hover:text-neutral-200 transition-colors cursor-pointer"
            title="New chat"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
          </button>
        </header>

        {isEmptyState ? (
          /* --- Centered empty-state hero, ChatGPT home-screen style --- */
          <div className="flex-1 overflow-y-auto flex flex-col items-center justify-center px-6 text-center custom-scrollbar">
            <div className={`w-12 h-12 rounded-full flex items-center justify-center text-lg font-semibold mb-4 ${accent.avatarBg} ${accent.avatarText}`}>
              {assistantInitial}
            </div>
            <h2 className="text-xl font-semibold text-neutral-100 mb-1.5">{assistantName}</h2>
            <p className="text-sm text-neutral-500 max-w-md mb-8">
              {isBI
                ? 'Ask analytical questions about revenue, staff performance, retention, or forecasts.'
                : 'Ask me to check availability, book, reschedule, or review your appointments.'}
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full max-w-xl">
              {suggestions.map((card, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSendMessage(card.prompt)}
                  className="p-3 text-left bg-neutral-900 hover:bg-neutral-800 border border-neutral-800 rounded-xl transition-colors cursor-pointer"
                >
                  <span className="block font-medium text-sm text-neutral-200 mb-0.5">{card.title}</span>
                  <span className="text-xs text-neutral-500 line-clamp-1">{card.prompt}</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          /* --- Message Log --- */
          <div className="flex-1 overflow-y-auto custom-scrollbar">
            {messages.map((msg) => (
              <ChatMessageBubble
                key={msg.id}
                msg={msg}
                assistantInitial={assistantInitial}
                accent={accent}
              />
            ))}

            {/* Typing Loading Indicator */}
            {isLoading && (
              <div className="w-full py-3">
                <div className="max-w-3xl mx-auto px-4 md:px-6 flex gap-4">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center font-semibold text-xs shrink-0 mt-0.5 ${accent.avatarBg} ${accent.avatarText}`}>
                    {assistantInitial}
                  </div>
                  <div className="flex items-center gap-1.5 pt-2.5">
                    <span className="w-1.5 h-1.5 bg-neutral-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-1.5 h-1.5 bg-neutral-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-1.5 h-1.5 bg-neutral-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}

        {/* Error Banner with Retry */}
        {error && (
          <div className="max-w-3xl w-full mx-auto px-4 md:px-6 pb-2 shrink-0">
            <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 text-xs rounded-xl flex items-center justify-between">
              <div className="flex items-center gap-2">
                <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <span className="font-medium">{error}</span>
              </div>
              <button
                onClick={handleRetry}
                className="px-3 py-1 bg-red-500/10 hover:bg-red-500/20 text-red-300 rounded-lg text-xs font-medium transition-colors cursor-pointer flex-shrink-0 ml-3"
              >
                Retry
              </button>
            </div>
          </div>
        )}

        {/* Chat Input Console */}
        <footer className="border-t border-neutral-800 px-4 pt-3 pb-2 shrink-0">
          <div className="max-w-3xl mx-auto flex items-end gap-2 rounded-3xl border border-neutral-700 bg-neutral-900 px-3 py-2 focus-within:border-neutral-500 transition-colors">
            <textarea
              ref={textareaRef}
              rows={1}
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSendMessage(inputMessage);
                }
              }}
              placeholder={isBI
                ? 'Ask Atlas a business question...'
                : 'Message Clara...'}
              disabled={isLoading}
              className="flex-1 resize-none bg-transparent text-sm text-neutral-100 placeholder-neutral-500 focus:outline-none max-h-48 py-1.5 disabled:text-neutral-600"
            />
            <button
              onClick={() => handleSendMessage(inputMessage)}
              disabled={isLoading || !inputMessage.trim()}
              className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center transition-colors cursor-pointer disabled:cursor-not-allowed ${inputMessage.trim() && !isLoading
                  ? `${accent.sendBg} text-white`
                  : 'bg-neutral-800 text-neutral-600'
                }`}
              title="Send"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 19V5m0 0l-6 6m6-6l6 6" />
              </svg>
            </button>
          </div>
          <p className="text-center text-[10px] text-neutral-600 mt-1.5">{assistantName} can make mistakes. Verify important details.</p>
        </footer>

      </section>

    </div>
  );
};

export default AgentChat;
