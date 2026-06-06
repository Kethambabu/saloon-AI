/**
 * AgentChat Component - Enterprise AI Receptionist Dashboard
 * Driven by React, TypeScript, Tailwind CSS, and communicating with the FastAPI agent backend.
 */

import React, { useState, useEffect, useRef, useMemo } from 'react';
import { apiClient } from '../../api/client';
import { useAuth } from '../../context/AuthContext';

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
      <div key={`tbl-${elements.length}`} className="overflow-x-auto my-2">
        <table className="min-w-full border-collapse text-xs">
          {headerCells.length > 0 && (
            <thead>
              <tr className="border-b border-slate-700">
                {headerCells.map((c, i) => <th key={i} className="px-3 py-1.5 text-left font-semibold text-blue-300">{inlineFormat(c)}</th>)}
              </tr>
            </thead>
          )}
          <tbody>
            {bodyRows.map((row, ri) => (
              <tr key={ri} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                {row.map((c, ci) => <td key={ci} className="px-3 py-1.5 text-slate-300">{inlineFormat(c)}</td>)}
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
      else if (match[3]) parts.push(<strong key={match.index}>{match[3]}</strong>);
      else if (match[4]) parts.push(<em key={match.index}>{match[4]}</em>);
      else if (match[5]) parts.push(<code key={match.index} className="bg-slate-800 px-1 py-0.5 rounded text-blue-300 text-xs">{match[5]}</code>);
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
      elements.push(<h6 key={`h-${i}`} className="text-xs font-bold text-blue-300 mt-2 mb-0.5">{inlineFormat(trimmed.slice(5))}</h6>);
    } else if (trimmed.startsWith('### ')) {
      elements.push(<h5 key={`h-${i}`} className="text-sm font-bold text-blue-300 mt-2 mb-0.5">{inlineFormat(trimmed.slice(4))}</h5>);
    } else if (trimmed.startsWith('## ')) {
      elements.push(<h4 key={`h-${i}`} className="text-sm font-bold text-blue-200 mt-2 mb-1">{inlineFormat(trimmed.slice(3))}</h4>);
    } else if (trimmed.startsWith('# ')) {
      elements.push(<h3 key={`h-${i}`} className="text-base font-bold text-blue-200 mt-2 mb-1">{inlineFormat(trimmed.slice(2))}</h3>);
    } else if (trimmed === '' || trimmed === '---') {
      if (trimmed === '---') elements.push(<hr key={`hr-${i}`} className="border-slate-700 my-2" />);
      else if (elements.length > 0) elements.push(<div key={`br-${i}`} className="h-1" />);
    } else {
      elements.push(<p key={`p-${i}`} className="my-0.5">{inlineFormat(trimmed)}</p>);
    }
  }

  // Flush remaining
  if (tableBuffer.length > 0) flushTable();
  if (listBuffer) flushList();

  return <div className="space-y-0.5">{elements}</div>;
}

// Structured interface for chat messages
interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

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
  // --- States ---
  const { user } = useAuth();
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string>('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [isHistoryOpen, setIsHistoryOpen] = useState<boolean>(false); // Collapsed by default

  // References for scrolling
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Get user-specific localStorage key
  const getStorageKey = (): string => {
    const prefix = intentOverride === 'business_intelligence' ? 'salonai_bi_sessions' : 'salonai_sessions';
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
  }, [user]);

  // --- Auto-scroll to Bottom on New Messages ---
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

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
      title: intentOverride === 'business_intelligence'
        ? `BI Analysis - ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
        : `Booking Session - ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`,
      lastActive: new Date().toLocaleDateString(),
      messages: [
        {
          id: `msg_welcome_${Date.now()}`,
          role: 'assistant',
          content: intentOverride === 'business_intelligence'
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
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
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
        const fallbackMsg = response.data?.response || response.data?.error || `Failed to receive a valid response from ${intentOverride === 'business_intelligence' ? 'Atlas' : 'Clara'}.`;
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
      const errorMsg = err.response?.data?.detail || err.message || `Connecting to ${intentOverride === 'business_intelligence' ? 'Atlas' : 'Clara'} timed out or failed. Is the backend API running?`;
      setError(errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  // --- Predefined Suggestions Cards ---
  const suggestions = intentOverride === 'business_intelligence' ? [
    { title: "Revenue Analysis", prompt: "How much revenue did we earn this month? Which branch or service earns the most?" },
    { title: "Staff Performance", prompt: "Who are our top performing stylists? Who deserves a bonus or has the highest rating?" },
    { title: "Forecast & Growth", prompt: "Forecast next month's expected revenue and appointments." },
    { title: "Business Metrics RAG", prompt: "Why is revenue decreasing? Compare with last 3 months performance." }
  ] : [
    { title: "Haircut Availability", prompt: "What slots are available for a Signature Haircut tomorrow?" },
    { title: "My History", prompt: "Can you check my booking history? My Customer ID is FefffEEb-AE98-4BB2-BFF7-E4DaA09B4Fa5." },
    { title: "Book Hot Stone", prompt: "I'd like to book a Himalayan Hot Stone Massage tomorrow. Branch: Downtown Elite, Customer: Alice Smith (6b09fca3-c8a5-46a1-88dc-72c081668be9)." },
    { title: "Cancel Booking", prompt: "Can you cancel my appointment? The booking ID is 0fbaddb8-1fbe-49d5-931f-f46b5de81293." }
  ];

  return (
    <div className="w-full max-w-7xl mx-auto flex flex-col md:flex-row bg-slate-950/40 backdrop-blur-md rounded-2xl shadow-2xl border border-slate-800/80 overflow-hidden" style={{ height: '70vh', minHeight: '600px' }}>
      
      {/* --- Sidebar Section (Chat Session History) --- */}
      <aside className={`bg-slate-950/60 text-slate-100 flex flex-col border-r border-slate-800/80 transition-all duration-300 ease-in-out ${
        isHistoryOpen ? 'w-full md:w-80 opacity-100' : 'w-0 opacity-0 overflow-hidden border-none'
      }`}>
        
        {/* Sidebar Header */}
        <div className="p-4 border-b border-slate-800/80 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 rounded-lg bg-blue-500 flex items-center justify-center font-bold text-white shadow-md shadow-blue-500/20">
              S
            </div>
            <span className="font-semibold text-lg tracking-wide text-slate-200">Conversations</span>
          </div>
          <button 
            onClick={createNewSession}
            className="p-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800/60 transition-all cursor-pointer"
            title="Create New Session"
          >
            <svg className="w-5 h-5 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
          </button>
        </div>

        {/* Sessions List */}
        <div className="flex-1 overflow-y-auto p-3 space-y-2 custom-scrollbar">
          {sessions.map((s) => (
            <div
              key={s.id}
              onClick={() => handleSwitchSession(s.id)}
              className={`p-3.5 rounded-xl flex items-center justify-between group cursor-pointer transition-all ${
                s.id === activeSessionId
                  ? 'bg-blue-600 text-white font-medium shadow-lg shadow-blue-500/20'
                  : 'hover:bg-slate-900/60 text-slate-400 hover:text-slate-200'
              }`}
            >
              <div className="flex items-center space-x-3 overflow-hidden">
                <svg className={`w-5 h-5 flex-shrink-0 ${s.id === activeSessionId ? 'text-white' : 'text-slate-500'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
                <span className="truncate text-sm text-left">{s.title}</span>
              </div>
              <button
                onClick={(e) => handleDeleteSession(e, s.id)}
                className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-slate-850/60 text-slate-400 hover:text-red-400 transition-all cursor-pointer"
                title="Delete Session"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>
          ))}
        </div>
      </aside>

      {/* --- Main Chat Section --- */}
      <section className="flex-1 bg-slate-900/20 backdrop-blur-md flex flex-col relative">
        
        {/* Chat Area Header */}
        <header className="p-4 border-b border-slate-800/80 bg-slate-950/40 flex items-center justify-between">
          <div className="flex items-center space-x-3.5">
            {/* Toggle Sidebar Button */}
            <button
              onClick={() => setIsHistoryOpen(!isHistoryOpen)}
              className={`p-2 rounded-xl border transition-all duration-300 cursor-pointer flex items-center justify-center shadow-sm ${
                isHistoryOpen
                  ? 'bg-blue-950/50 border-blue-900 text-blue-400 hover:bg-blue-900/50'
                  : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-blue-400 hover:border-slate-700'
              }`}
              title={isHistoryOpen ? "Hide History" : "Show History"}
            >
              <svg className="w-5 h-5 animate-pulse-subtle" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                {isHistoryOpen ? (
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h12M4 18h16" />
                )}
              </svg>
            </button>

            <div className="relative">
              <div className="w-10 h-10 rounded-full bg-blue-950/50 border border-blue-900/60 flex items-center justify-center font-bold text-blue-400 shadow-sm">
                {intentOverride === 'business_intelligence' ? 'A' : 'C'}
              </div>
              <span className="absolute bottom-0 right-0 w-3 h-3 rounded-full bg-green-500 border-2 border-white animate-pulse" title="Online" />
            </div>
            <div>
              <h2 className="text-white font-bold leading-tight">{intentOverride === 'business_intelligence' ? 'Atlas - AI Business Analyst' : 'Clara - AI Receptionist'}</h2>
              <span className="text-xs text-slate-450 font-medium">{intentOverride === 'business_intelligence' ? 'Executive Analytics Advisor' : 'SalonAI Workforce Co-pilot'}</span>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <span className="text-xs px-2.5 py-1 rounded-full bg-blue-950/40 text-blue-400 font-semibold border border-blue-900/40">
              PostgreSQL Active
            </span>
          </div>
        </header>

        {/* Message Log */}
        <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4 custom-scrollbar bg-slate-950/20">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex items-start space-x-3.5 max-w-[85%] ${
                msg.role === 'user' ? 'ml-auto flex-row-reverse space-x-reverse' : 'mr-auto'
              }`}
            >
              {/* Avatar Icon */}
              <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm shadow-sm border ${
                msg.role === 'user'
                  ? 'bg-gradient-to-tr from-blue-600 to-indigo-600 border-indigo-700 text-white'
                  : 'bg-slate-900 border-slate-800 text-blue-400'
              }`}>
                {msg.role === 'user' ? 'U' : (intentOverride === 'business_intelligence' ? 'A' : 'C')}
              </div>

              {/* Chat Bubble */}
              <div className="flex flex-col max-w-full">
                <div className={`p-4 rounded-2xl shadow-sm text-sm leading-relaxed border ${
                  msg.role === 'user'
                    ? 'bg-gradient-to-tr from-blue-600 to-indigo-600 border-indigo-750 text-white rounded-tr-none shadow-md shadow-blue-600/10'
                    : 'bg-slate-900/60 border border-slate-800/80 text-slate-100 rounded-tl-none'
                }`}>
                    {msg.role === 'assistant' ? (
                    <div className="whitespace-pre-wrap text-left prose-sm prose-invert max-w-none">{renderMarkdown(msg.content)}</div>
                  ) : (
                    <p className="whitespace-pre-wrap text-left">{msg.content}</p>
                  )}
                </div>
                <span className={`text-[10px] text-slate-400 mt-1 ${msg.role === 'user' ? 'text-right' : 'text-left'}`}>
                  {msg.timestamp}
                </span>
              </div>
            </div>
          ))}

          {/* Typing Loading Indicator */}
          {isLoading && (
            <div className="flex items-start space-x-3.5 mr-auto max-w-[85%]">
              <div className="w-8 h-8 rounded-full bg-slate-900 border border-slate-800 flex items-center justify-center font-bold text-sm text-blue-400 shadow-sm">
                {intentOverride === 'business_intelligence' ? 'A' : 'C'}
              </div>
              <div className="flex flex-col">
                <div className="p-4 bg-slate-900/60 border border-slate-800/80 rounded-2xl rounded-tl-none shadow-sm flex items-center space-x-1.5">
                  <span className="w-2.5 h-2.5 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-2.5 h-2.5 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-2.5 h-2.5 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
                <span className="text-[10px] text-slate-555 mt-1 text-left">{intentOverride === 'business_intelligence' ? 'Atlas' : 'Clara'} is thinking...</span>
              </div>
            </div>
          )}

          {/* Error Banner */}
          {error && (
            <div className="p-3 bg-red-950/30 border border-red-900/50 text-red-400 text-xs rounded-xl flex items-center space-x-2 shadow-sm animate-pulse">
              <svg className="w-5 h-5 flex-shrink-0 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <span className="text-left font-medium">{error}</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Suggestion Prompt Cards */}
        {messages.length === 1 && !isLoading && (
          <div className="p-4 bg-slate-950/40 border-t border-slate-800/80">
            <p className="text-xs font-semibold text-slate-450 mb-3 tracking-wide uppercase text-left">
              {intentOverride === 'business_intelligence' ? 'Quick analysis queries' : 'Quick booking suggestions'}
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
              {suggestions.map((card, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSendMessage(card.prompt)}
                  className="p-3 text-left bg-slate-900/60 hover:bg-slate-800/60 border border-slate-800 hover:border-blue-900 hover:text-blue-300 rounded-xl font-medium text-xs text-slate-350 shadow-sm transition-all duration-200 cursor-pointer"
                >
                  <span className="block font-bold mb-0.5 text-blue-400">{card.title}</span>
                  <span className="text-slate-500 line-clamp-1">{card.prompt}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Chat Input Console */}
        <footer className="p-4 border-t border-slate-800/80 bg-slate-950/40 flex items-center space-x-3">
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSendMessage(inputMessage);
            }}
            placeholder={intentOverride === 'business_intelligence' 
              ? "Ask Atlas a business question (e.g., 'Why is revenue decreasing? Compare with last 3 months')..." 
              : "Type a booking query (e.g., 'book a haircut tomorrow for Alice Smith')..."}
            disabled={isLoading}
            className="flex-1 px-4 py-3 bg-slate-900/80 border border-slate-800 hover:border-slate-700 focus:border-blue-500 focus:ring-2 focus:ring-blue-950 rounded-xl text-sm focus:outline-none transition-all text-white placeholder-slate-500 disabled:bg-slate-950 disabled:text-slate-600"
          />
          <button
            onClick={() => handleSendMessage(inputMessage)}
            disabled={isLoading || !inputMessage.trim()}
            className="px-5 py-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-sm tracking-wide shadow-md shadow-blue-600/10 transition-all flex items-center justify-center space-x-2 disabled:bg-slate-800 disabled:text-slate-650 disabled:shadow-none cursor-pointer"
          >
            <span>Send</span>
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M14 5l7 7m0 0l-7 7m7-7H3" />
            </svg>
          </button>
        </footer>

      </section>
      
    </div>
  );
};

export default AgentChat;

