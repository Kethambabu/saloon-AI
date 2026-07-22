import React, { useState, useEffect, useRef } from 'react';
import { apiClient } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import {
  User,
  Sparkles,
  Send,
  Calendar,
  History,
  Trash2,
  Plus,
  MessageSquare,
  Clock,
  TrendingUp,
  FileText,
  SendHorizontal,
  ChevronLeft,
  ChevronRight,
  UserCheck
} from 'lucide-react';

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
      <Tag key={`list-${elements.length}`} className={listBuffer.type === 'ul' ? 'list-disc pl-5 my-1.5 text-[12px] text-slate-300 space-y-1' : 'list-decimal pl-5 my-1.5 text-[12px] text-slate-300 space-y-1'}>
        {listBuffer.items.map((item, i) => <li key={i}>{inlineFormat(item)}</li>)}
      </Tag>
    );
    listBuffer = null;
  };

  const flushTable = () => {
    if (tableBuffer.length < 2) {
      tableBuffer.forEach(l => elements.push(<p key={`p-${elements.length}`} className="my-1 text-[12px] text-slate-300">{inlineFormat(l)}</p>));
      tableBuffer = [];
      return;
    }
    const rows = tableBuffer.filter(r => !r.match(/^\|?[\s\-:|]+\|?$/));
    const parseRow = (row: string) => row.split('|').map(c => c.trim()).filter(c => c.length > 0);
    const headerCells = rows.length > 0 ? parseRow(rows[0]) : [];
    const bodyRows = rows.slice(1).map(parseRow);
    elements.push(
      <div key={`tbl-${elements.length}`} className="overflow-x-auto my-3 rounded-xl border border-slate-800 bg-slate-950/40 shadow-inner">
        <table className="min-w-full border-collapse text-left text-[12px]">
          {headerCells.length > 0 && (
            <thead>
              <tr className="border-b border-slate-800 bg-slate-950/60">
                {headerCells.map((c, i) => <th key={i} className="px-4 py-2.5 font-extrabold text-emerald-400 tracking-wide uppercase text-[10px]">{inlineFormat(c)}</th>)}
              </tr>
            </thead>
          )}
          <tbody>
            {bodyRows.map((row, ri) => (
              <tr key={ri} className="border-b border-slate-900/50 last:border-0 hover:bg-slate-800/20 transition-all">
                {row.map((c, ci) => <td key={ci} className="px-4 py-2.5 text-slate-300 font-medium">{inlineFormat(c)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
    tableBuffer = [];
  };

  const inlineFormat = (text: string): React.ReactNode => {
    const parts: React.ReactNode[] = [];
    const regex = /(\*\*\*(.+?)\*\*\*|\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`)/g;
    let lastIndex = 0;
    let match;
    while ((match = regex.exec(text)) !== null) {
      if (match.index > lastIndex) parts.push(text.slice(lastIndex, match.index));
      if (match[2]) parts.push(<strong key={match.index}><em>{match[2]}</em></strong>);
      else if (match[3]) parts.push(<strong key={match.index} className="text-white font-bold">{match[3]}</strong>);
      else if (match[4]) parts.push(<em key={match.index} className="text-slate-200">{match[4]}</em>);
      else if (match[5]) parts.push(<code key={match.index} className="bg-slate-950 px-1.5 py-0.5 rounded text-emerald-400 text-[11px] font-mono border border-slate-800">{match[5]}</code>);
      lastIndex = regex.lastIndex;
    }
    if (lastIndex < text.length) parts.push(text.slice(lastIndex));
    return parts.length === 1 ? parts[0] : <>{parts}</>;
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    if (trimmed.startsWith('|') || (trimmed.includes('|') && tableBuffer.length > 0)) {
      flushList();
      tableBuffer.push(trimmed);
      continue;
    } else if (tableBuffer.length > 0) {
      flushTable();
    }

    const ulMatch = trimmed.match(/^[\-\*•+]\s+(.+)/);
    if (ulMatch) {
      if (listBuffer && listBuffer.type !== 'ul') flushList();
      if (!listBuffer) listBuffer = { type: 'ul', items: [] };
      listBuffer.items.push(ulMatch[1]);
      continue;
    }

    const olMatch = trimmed.match(/^\d+[\.\)]\s+(.+)/);
    if (olMatch) {
      if (listBuffer && listBuffer.type !== 'ol') flushList();
      if (!listBuffer) listBuffer = { type: 'ol', items: [] };
      listBuffer.items.push(olMatch[1]);
      continue;
    }

    if (listBuffer) flushList();

    if (trimmed.startsWith('#### ')) {
      elements.push(<h6 key={`h-${i}`} className="text-[11px] font-black text-emerald-400 mt-3 mb-1 uppercase tracking-wider">{inlineFormat(trimmed.slice(5))}</h6>);
    } else if (trimmed.startsWith('### ')) {
      elements.push(<h5 key={`h-${i}`} className="text-xs font-black text-emerald-300 mt-3 mb-1 uppercase tracking-wide">{inlineFormat(trimmed.slice(4))}</h5>);
    } else if (trimmed.startsWith('## ')) {
      elements.push(<h4 key={`h-${i}`} className="text-sm font-black text-slate-200 mt-4 mb-1.5 uppercase tracking-wide border-b border-slate-800 pb-1">{inlineFormat(trimmed.slice(3))}</h4>);
    } else if (trimmed.startsWith('# ')) {
      elements.push(<h3 key={`h-${i}`} className="text-base font-black text-white mt-5 mb-2.5 uppercase tracking-widest">{inlineFormat(trimmed.slice(2))}</h3>);
    } else if (trimmed === '' || trimmed === '---') {
      if (trimmed === '---') elements.push(<hr key={`hr-${i}`} className="border-slate-800 my-4" />);
      else if (elements.length > 0) elements.push(<div key={`br-${i}`} className="h-2" />);
    } else {
      elements.push(<p key={`p-${i}`} className="my-1.5 text-slate-300 text-[12px] leading-relaxed font-medium">{inlineFormat(trimmed)}</p>);
    }
  }

  if (tableBuffer.length > 0) flushTable();
  if (listBuffer) flushList();

  return <div className="space-y-1.5">{elements}</div>;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

// Memoized so an unrelated re-render of the chat (new message appended,
// input state changing) doesn't re-run the markdown parser over every prior
// message in the conversation — same fix applied to AgentChat.tsx.
const StaffChatMessageBubble = React.memo<{ msg: Message }>(({ msg }) => {
  const isUser = msg.role === 'user';
  const renderedContent = React.useMemo(
    () => (isUser ? null : renderMarkdown(msg.content)),
    [isUser, msg.content]
  );

  return (
    <div
      className={`flex items-start space-x-3.5 max-w-[85%] ${
        isUser ? 'ml-auto flex-row-reverse space-x-reverse' : 'mr-auto'
      }`}
    >
      {/* Avatar Icon wrapper */}
      <div className={`w-9 h-9 rounded-xl flex items-center justify-center shadow-md flex-shrink-0 border transition-all ${
        isUser
          ? 'bg-gradient-to-br from-emerald-500 to-teal-600 border-emerald-400/30 text-white'
          : 'bg-slate-900 border-slate-800 text-emerald-400'
      }`}>
        {isUser ? <User className="w-4 h-4" /> : <Sparkles className="w-4 h-4" />}
      </div>

      <div className="flex flex-col">
        {/* Chat bubble content */}
        <div className={`p-4 rounded-2xl shadow-lg leading-relaxed text-[12.5px] border ${
          isUser
            ? 'bg-gradient-to-br from-emerald-600/90 to-teal-700/95 text-white rounded-tr-none border-emerald-500/20 shadow-emerald-500/5'
            : 'bg-slate-900/85 border border-slate-800/80 text-slate-100 rounded-tl-none shadow-black/10 backdrop-blur-sm'
        }`}>
          {isUser ? (
            <p className="whitespace-pre-wrap text-left font-medium">{msg.content}</p>
          ) : (
            <div className="whitespace-pre-wrap text-left prose prose-invert max-w-none">
              {renderedContent}
            </div>
          )}
        </div>

        {/* Timestamp */}
        <span className={`text-[9px] text-slate-500 font-bold mt-1.5 uppercase tracking-wider ${isUser ? 'text-right' : 'text-left'}`}>
          {msg.timestamp}
        </span>
      </div>
    </div>
  );
});

interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
}

export const StaffChat: React.FC = () => {
  const { user } = useAuth();
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string>('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [isHistoryOpen, setIsHistoryOpen] = useState<boolean>(true);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const getStorageKey = (): string => {
    return `salonai_staff_sessions_${user?.id || 'anonymous'}`;
  };

  useEffect(() => {
    const saved = localStorage.getItem(getStorageKey());
    if (saved) {
      try {
        const parsed = JSON.parse(saved) as ChatSession[];
        setSessions(parsed);
        if (parsed.length > 0) {
          setActiveSessionId(parsed[0].id);
          setMessages(parsed[0].messages);
        } else {
          createNewSession();
        }
      } catch (e) {
        createNewSession();
      }
    } else {
      createNewSession();
    }
  }, [user]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const saveSessions = (updated: ChatSession[]) => {
    setSessions(updated);
    localStorage.setItem(getStorageKey(), JSON.stringify(updated));
  };

  const createNewSession = () => {
    const sessId = `staff_sess_${Math.random().toString(36).substring(2, 11)}`;
    const newSession: ChatSession = {
      id: sessId,
      title: `Co-Stylist Workspace - ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`,
      messages: [
        {
          id: `welcome_${Date.now()}`,
          role: 'assistant',
          content: "Welcome to the Staff Co-Stylist AI Workspace. I'm Atlas, your productivity copilot. Ask me to:\n- Show today's appointments\n- Check client histories & color formulas\n- Analyze revenue & metrics\n- Log a leave request",
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]
    };
    const updated = [newSession, ...sessions];
    saveSessions(updated);
    setActiveSessionId(sessId);
    setMessages(newSession.messages);
    setError(null);
  };

  const handleSwitchSession = (id: string) => {
    const target = sessions.find(s => s.id === id);
    if (target) {
      setActiveSessionId(id);
      setMessages(target.messages);
      setError(null);
    }
  };

  const handleDeleteSession = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    const filtered = sessions.filter(s => s.id !== id);
    if (filtered.length === 0) {
      localStorage.removeItem(getStorageKey());
      createNewSession();
    } else {
      saveSessions(filtered);
      if (activeSessionId === id) {
        setActiveSessionId(filtered[0].id);
        setMessages(filtered[0].messages);
      }
    }
  };

  const handleSendMessage = async (text: string) => {
    if (!text.trim() || isLoading) return;

    const userMsg: Message = {
      id: `user_${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    const updatedMessages = [...messages, userMsg];
    setMessages(updatedMessages);
    setInputMessage('');
    setIsLoading(true);
    setError(null);

    const updatedSessions = sessions.map(s => {
      if (s.id === activeSessionId) {
        return { ...s, messages: updatedMessages };
      }
      return s;
    });
    saveSessions(updatedSessions);

    try {
      const chatHistory = updatedMessages.slice(0, -1).map(msg => ({
        role: msg.role,
        content: msg.content
      }));

      const response = await apiClient.post('/staff/chat', {
        message: text,
        'session id': activeSessionId,
        'chat history': chatHistory
      });

      if (response.data && response.data.success) {
        const assistantMsg: Message = {
          id: `assistant_${Date.now()}`,
          role: 'assistant',
          content: response.data.response,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };

        const finalMessages = [...updatedMessages, assistantMsg];
        setMessages(finalMessages);

        const currentSession = sessions.find(s => s.id === activeSessionId);
        const hasCustomTitle = currentSession && !currentSession.title.startsWith('Co-Stylist Workspace -');
        const newTitle = hasCustomTitle ? currentSession.title : (text.length > 25 ? `${text.substring(0, 22)}...` : text);

        const finalSessions = sessions.map(s => {
          if (s.id === activeSessionId) {
            return { ...s, title: newTitle, messages: finalMessages };
          }
          return s;
        });
        saveSessions(finalSessions);
      } else {
        const fallback = response.data?.response || response.data?.error || "Failed to receive a response.";
        setError(fallback);
      }
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || "Connection to Co-Stylist AI failed. Is the API online?";
      setError(errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  const suggestions = [
    { title: "Today's Agenda", prompt: "Show my appointments today.", icon: <Calendar className="w-4 h-4 text-emerald-400" /> },
    { title: "Next Client", prompt: "Who is my next customer?", icon: <UserCheck className="w-4 h-4 text-teal-400" /> },
    { title: "Formula Search", prompt: "Show customer history of Alice Smith", icon: <FileText className="w-4 h-4 text-violet-400" /> },
    { title: "Request Leave", prompt: "Apply leave on 2026-06-12 (reason: family event)", icon: <Clock className="w-4 h-4 text-amber-400" /> },
    { title: "Send Reminders", prompt: "Send reminders to my customers.", icon: <Send className="w-4 h-4 text-sky-400" /> },
    { title: "My Analytics", prompt: "How am I performing?", icon: <TrendingUp className="w-4 h-4 text-rose-400" /> }
  ];

  return (
    <div className="w-full flex flex-col md:flex-row bg-slate-900/10 backdrop-blur-xl rounded-3xl border border-slate-850/60 overflow-hidden shadow-2xl" style={{ height: '75vh', minHeight: '650px' }}>
      
      {/* Sidebar history */}
      <aside className={`bg-slate-950/45 text-slate-100 flex flex-col border-r border-slate-900/60 transition-all duration-300 relative ${
        isHistoryOpen ? 'w-full md:w-64 opacity-100' : 'w-0 opacity-0 overflow-hidden'
      }`}>
        <div className="p-4 border-b border-slate-900/60 flex items-center justify-between bg-slate-950/20">
          <div className="flex items-center space-x-2">
            <History className="w-4 h-4 text-slate-400" />
            <span className="font-extrabold text-xs tracking-wider uppercase text-slate-300">Workspace Logs</span>
          </div>
          <button 
            onClick={createNewSession} 
            title="Start New Session"
            className="p-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-850 hover:border-slate-700 cursor-pointer transition-all hover:scale-105 active:scale-95"
          >
            <Plus className="w-3.5 h-3.5 text-emerald-400" />
          </button>
        </div>
        
        <div className="flex-1 overflow-y-auto p-3 space-y-2 custom-scrollbar">
          {sessions.map((s) => {
            const isActive = s.id === activeSessionId;
            return (
              <div
                key={s.id}
                onClick={() => handleSwitchSession(s.id)}
                className={`p-3 rounded-2xl flex items-center justify-between group cursor-pointer border transition-all ${
                  isActive 
                    ? 'bg-gradient-to-r from-emerald-600/95 to-teal-600/95 border-emerald-500/30 text-white shadow-md shadow-emerald-600/10' 
                    : 'bg-slate-900/20 border-slate-900 hover:bg-slate-900/50 hover:border-slate-800 text-slate-400 hover:text-slate-200'
                }`}
              >
                <div className="flex items-center space-x-2.5 min-w-0 flex-1">
                  <MessageSquare className={`w-3.5 h-3.5 flex-shrink-0 ${isActive ? 'text-white' : 'text-slate-500 group-hover:text-emerald-400'}`} />
                  <span className="truncate text-xs font-bold leading-none">{s.title}</span>
                </div>
                <button 
                  onClick={(e) => handleDeleteSession(e, s.id)} 
                  className={`p-1 rounded-md opacity-0 group-hover:opacity-100 hover:bg-slate-850 transition-all ${
                    isActive ? 'hover:bg-emerald-700/60 text-white' : 'text-slate-500 hover:text-red-400'
                  } cursor-pointer`}
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            );
          })}
        </div>
      </aside>

      {/* Main chat section */}
      <section className="flex-1 bg-gradient-to-b from-slate-950/20 to-slate-900/10 flex flex-col relative">
        <header className="p-4 border-b border-slate-900/60 bg-slate-950/25 flex items-center justify-between">
          <div className="flex items-center space-x-3.5">
            <button
              onClick={() => setIsHistoryOpen(!isHistoryOpen)}
              title={isHistoryOpen ? "Hide History" : "Show History"}
              className={`p-2 rounded-xl border transition-all cursor-pointer hover:scale-105 active:scale-95 ${
                isHistoryOpen 
                  ? 'bg-emerald-950/40 border-emerald-800/80 text-emerald-400' 
                  : 'bg-slate-900 border-slate-850 text-slate-400 hover:text-emerald-400 hover:border-slate-700'
              }`}
            >
              {isHistoryOpen ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
            </button>
            
            <div className="relative">
              <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-emerald-950/80 to-teal-900/40 border border-emerald-500/30 flex items-center justify-center font-black text-emerald-450 shadow-md shadow-emerald-950/20">
                <Sparkles className="w-5 h-5 text-emerald-400 animate-pulse" />
              </div>
              <span className="absolute bottom-0 right-0 w-3 h-3 rounded-full bg-emerald-500 border-2 border-slate-950 shadow-sm" />
            </div>
            
            <div className="text-left">
              <h2 className="text-xs font-black text-white leading-tight flex items-center gap-1.5">
                Atlas
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-450 inline-block animate-ping" />
              </h2>
              <span className="text-[10px] text-slate-500 font-bold tracking-wider uppercase">Stylist Success Agent</span>
            </div>
          </div>
          
          <div className="flex items-center space-x-2">
            <span className="hidden sm:inline-flex text-[9px] px-2.5 py-1 rounded-full bg-emerald-950/30 text-emerald-400 font-black border border-emerald-800/25 uppercase tracking-widest">
              Production Copilot
            </span>
          </div>
        </header>

        {/* Message Log */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5 custom-scrollbar bg-slate-950/5">
          {messages.map((msg) => (
            <StaffChatMessageBubble key={msg.id} msg={msg} />
          ))}

          {isLoading && (
            <div className="flex items-start space-x-3.5 mr-auto max-w-[85%]">
              <div className="w-9 h-9 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-center shadow-md text-emerald-400">
                <Sparkles className="w-4 h-4 animate-spin" />
              </div>
              <div className="flex flex-col">
                <div className="p-4 bg-slate-900/60 border border-slate-800/80 rounded-2xl rounded-tl-none flex items-center space-x-1.5 shadow-sm">
                  <span className="w-2.5 h-2.5 bg-emerald-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-2.5 h-2.5 bg-emerald-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-2.5 h-2.5 bg-emerald-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
                <span className="text-[9px] text-slate-500 font-bold mt-1.5 tracking-wider uppercase text-left">Atlas is fetching details...</span>
              </div>
            </div>
          )}

          {error && (
            <div className="p-3.5 bg-red-950/20 border border-red-900/30 text-red-400 text-xs font-bold rounded-2xl flex items-center space-x-2.5 shadow-md animate-pulse">
              <span className="w-2 h-2 rounded-full bg-red-500" />
              <span>{error}</span>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Suggestion prompt cards */}
        {messages.length === 1 && !isLoading && (
          <div className="p-5 bg-slate-950/30 border-t border-slate-900/60 text-left">
            <p className="text-[9px] font-black text-slate-500 mb-3.5 tracking-widest uppercase flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-emerald-500" /> Quick Copilot Suggestions
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              {suggestions.map((card, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSendMessage(card.prompt)}
                  className="p-3 bg-slate-900/35 hover:bg-slate-850/40 border border-slate-850/60 hover:border-emerald-500/50 hover:text-emerald-450 rounded-2xl shadow-sm hover:shadow-md transition-all duration-200 hover:-translate-y-0.5 cursor-pointer text-left flex items-start space-x-3 group"
                >
                  <div className="p-2 rounded-xl bg-slate-950/50 border border-slate-800/80 group-hover:bg-slate-900/80 group-hover:border-emerald-500/30 transition-all flex-shrink-0">
                    {card.icon}
                  </div>
                  <div className="min-w-0">
                    <span className="block font-black text-[11px] text-slate-200 group-hover:text-emerald-400 mb-0.5 transition-colors">{card.title}</span>
                    <span className="text-[10px] text-slate-500 font-bold block truncate leading-snug">{card.prompt}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Chat input footer */}
        <footer className="p-5 border-t border-slate-900/60 bg-slate-950/25 flex items-center space-x-3">
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSendMessage(inputMessage);
            }}
            placeholder="Ask Atlas about scheduling, history, performance metrics, or leaves..."
            disabled={isLoading}
            className="flex-1 px-4.5 py-3 bg-slate-900/80 border border-slate-800 hover:border-slate-750 focus:border-emerald-500 rounded-2xl text-xs focus:outline-none transition-all text-white placeholder-slate-600 disabled:text-slate-500 shadow-inner"
          />
          <button
            onClick={() => handleSendMessage(inputMessage)}
            disabled={isLoading || !inputMessage.trim()}
            className="p-3 rounded-2xl bg-emerald-600 hover:bg-emerald-500 text-white font-extrabold text-xs tracking-wider transition-all disabled:bg-slate-800 disabled:text-slate-600 cursor-pointer shadow-md hover:shadow-emerald-500/10 active:scale-95 flex items-center justify-center"
          >
            <SendHorizontal className="w-4 h-4" />
          </button>
        </footer>
      </section>
    </div>
  );
};

export default StaffChat;
