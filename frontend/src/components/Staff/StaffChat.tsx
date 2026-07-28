import React, { useState, useEffect, useRef } from 'react';
import { apiClient } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import {
  Sparkles,
  Calendar,
  Trash2,
  Plus,
  Clock,
  TrendingUp,
  FileText,
  Send,
  Menu,
  UserCheck,
  ArrowUp
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
    const parts: React.ReactNode[] = [];
    const regex = /(\*\*\*(.+?)\*\*\*|\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`)/g;
    let lastIndex = 0;
    let match;
    while ((match = regex.exec(text)) !== null) {
      if (match.index > lastIndex) parts.push(text.slice(lastIndex, match.index));
      if (match[2]) parts.push(<strong key={match.index}><em>{match[2]}</em></strong>);
      else if (match[3]) parts.push(<strong key={match.index} className="text-neutral-50 font-semibold">{match[3]}</strong>);
      else if (match[4]) parts.push(<em key={match.index}>{match[4]}</em>);
      else if (match[5]) parts.push(<code key={match.index} className="bg-neutral-800 px-1.5 py-0.5 rounded text-[13px] text-emerald-300 font-mono">{match[5]}</code>);
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

  if (tableBuffer.length > 0) flushTable();
  if (listBuffer) flushList();

  return <div>{elements}</div>;
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
    <div className="w-full py-3">
      <div className={`max-w-3xl mx-auto px-4 md:px-6 flex gap-4 ${isUser ? 'justify-end' : ''}`}>
        {!isUser && (
          <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 mt-0.5 bg-emerald-500/15 text-emerald-400">
            <Sparkles className="w-4 h-4" />
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
            </div>
          )}
          <span className="text-[10px] text-neutral-500 mt-1">{msg.timestamp}</span>
        </div>
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
  const textareaRef = useRef<HTMLTextAreaElement>(null);

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  useEffect(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = 'auto';
      el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
    }
  }, [inputMessage]);

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
        const fallback = response.data?.response || response.data?.error || 'Failed to receive a response.';
        setError(fallback);
      }
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || 'Connection to Co-Stylist AI failed. Is the API online?';
      setError(errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  const suggestions = [
    { title: "Today's Agenda", prompt: 'Show my appointments today.', icon: <Calendar className="w-4 h-4" /> },
    { title: 'Next Client', prompt: 'Who is my next customer?', icon: <UserCheck className="w-4 h-4" /> },
    { title: 'Formula Search', prompt: 'Show customer history of Alice Smith', icon: <FileText className="w-4 h-4" /> },
    { title: 'Request Leave', prompt: 'Apply leave on 2026-06-12 (reason: family event)', icon: <Clock className="w-4 h-4" /> },
    { title: 'Send Reminders', prompt: 'Send reminders to my customers.', icon: <Send className="w-4 h-4" /> },
    { title: 'My Analytics', prompt: 'How am I performing?', icon: <TrendingUp className="w-4 h-4" /> }
  ];

  const isEmptyState = messages.length <= 1 && !isLoading;

  return (
    <div className="w-full flex bg-neutral-950 rounded-2xl border border-neutral-800 overflow-hidden h-full">

      {/* Sidebar history */}
      <aside className={`bg-neutral-950 flex flex-col border-r border-neutral-800 transition-all duration-200 ${isHistoryOpen ? 'w-64 opacity-100' : 'w-0 opacity-0 overflow-hidden'
        }`}>
        <div className="px-4 py-3.5 border-b border-neutral-800 flex items-center justify-between shrink-0">
          <span className="text-xs font-black uppercase tracking-wider text-neutral-500">Chat History</span>
          <button
            onClick={() => setIsHistoryOpen(false)}
            className="p-1.5 rounded-md hover:bg-neutral-850 text-neutral-400 hover:text-neutral-200 transition-colors cursor-pointer"
            title="Collapse Sidebar"
          >
            <ArrowUp className="w-4 h-4 -rotate-90" />
          </button>
        </div>

        <div className="p-3">
          <button
            onClick={createNewSession}
            className="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg border border-neutral-700 hover:bg-neutral-800 text-sm text-neutral-200 transition-colors cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            New chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-2 pb-2 space-y-0.5 custom-scrollbar">
          {sessions.map((s) => {
            const isActive = s.id === activeSessionId;
            return (
              <div
                key={s.id}
                onClick={() => handleSwitchSession(s.id)}
                className={`group flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer transition-colors ${isActive
                    ? 'bg-neutral-800 text-neutral-100'
                    : 'text-neutral-400 hover:bg-neutral-900 hover:text-neutral-200'
                  }`}
              >
                <span className="truncate text-sm">{s.title}</span>
                <button
                  onClick={(e) => handleDeleteSession(e, s.id)}
                  className="opacity-40 group-hover:opacity-100 p-1 rounded hover:bg-neutral-700 text-neutral-500 hover:text-red-400 transition-all cursor-pointer shrink-0"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            );
          })}
        </div>
      </aside>

      {/* Main chat section */}
      <section className="flex-1 bg-neutral-950 flex flex-col min-w-0">
        <header className="px-4 py-3 border-b border-neutral-800 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            {!isHistoryOpen && (
              <button
                onClick={() => setIsHistoryOpen(true)}
                className="p-1.5 rounded-md hover:bg-neutral-800 text-neutral-400 hover:text-neutral-200 transition-colors cursor-pointer"
                title="Show History"
              >
                <Menu className="w-5 h-5" />
              </button>
            )}
            <span className="text-sm font-medium text-neutral-200">Atlas</span>
            <span className="text-xs text-neutral-500">Stylist Success Agent</span>
          </div>
          <button
            onClick={createNewSession}
            className="p-1.5 rounded-md hover:bg-neutral-800 text-neutral-400 hover:text-neutral-200 transition-colors cursor-pointer"
            title="New chat"
          >
            <Plus className="w-5 h-5" />
          </button>
        </header>

        {isEmptyState ? (
          <div className="flex-1 overflow-y-auto flex flex-col items-center justify-center px-6 text-center custom-scrollbar">
            <div className="w-12 h-12 rounded-full flex items-center justify-center mb-4 bg-emerald-500/15 text-emerald-400">
              <Sparkles className="w-5 h-5" />
            </div>
            <h2 className="text-xl font-semibold text-neutral-100 mb-1.5">Atlas</h2>
            <p className="text-sm text-neutral-500 max-w-md mb-8">
              Ask about your schedule, client history, formulas, performance metrics, or leave requests.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5 w-full max-w-2xl">
              {suggestions.map((card, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSendMessage(card.prompt)}
                  className="p-3 bg-neutral-900 hover:bg-neutral-800 border border-neutral-800 rounded-xl transition-colors cursor-pointer text-left flex items-start gap-2.5"
                >
                  <div className="p-1.5 rounded-lg bg-neutral-800 text-emerald-400 shrink-0">
                    {card.icon}
                  </div>
                  <div className="min-w-0">
                    <span className="block font-medium text-sm text-neutral-200 mb-0.5">{card.title}</span>
                    <span className="text-xs text-neutral-500 block truncate">{card.prompt}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto custom-scrollbar">
            {messages.map((msg) => (
              <StaffChatMessageBubble key={msg.id} msg={msg} />
            ))}

            {isLoading && (
              <div className="w-full py-3">
                <div className="max-w-3xl mx-auto px-4 md:px-6 flex gap-4">
                  <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 mt-0.5 bg-emerald-500/15 text-emerald-400">
                    <Sparkles className="w-4 h-4" />
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

        {error && (
          <div className="max-w-3xl w-full mx-auto px-4 md:px-6 pb-2 shrink-0">
            <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 text-xs rounded-xl flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-red-500 shrink-0" />
              <span className="font-medium">{error}</span>
            </div>
          </div>
        )}

        {/* Chat input footer */}
        <footer className="border-t border-neutral-800 px-4 py-4 shrink-0">
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
              placeholder="Message Atlas..."
              disabled={isLoading}
              className="flex-1 resize-none bg-transparent text-sm text-neutral-100 placeholder-neutral-500 focus:outline-none max-h-48 py-1.5 disabled:text-neutral-600"
            />
            <button
              onClick={() => handleSendMessage(inputMessage)}
              disabled={isLoading || !inputMessage.trim()}
              className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center transition-colors cursor-pointer disabled:cursor-not-allowed ${inputMessage.trim() && !isLoading
                  ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
                  : 'bg-neutral-800 text-neutral-600'
                }`}
              title="Send"
            >
              <ArrowUp className="w-4 h-4" />
            </button>
          </div>
          <p className="text-center text-[10px] text-neutral-600 mt-2">Atlas can make mistakes. Verify important details.</p>
        </footer>
      </section>
    </div>
  );
};

export default StaffChat;
