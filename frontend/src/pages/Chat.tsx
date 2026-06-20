// Chat page: streaming chat surface (Phase 4, FR-001/002).
// Conversation persists across navigation via localStorage and survives until it is
// idle past CHAT_TTL_MS or the user clicks "New chat".
import { useCallback, useEffect, useRef, useState } from 'react';
import AppLayout from '../components/AppLayout';
import ChatInput from '../components/ChatInput';
import ChatMessage from '../components/ChatMessage';
import type { Citation } from '../api/chatApi';
import { streamChat } from '../api/chatApi';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
}

const CHAT_STORAGE_KEY = 'raseed_chat';
// Keep the conversation for 60 minutes of inactivity; after that it starts fresh.
const CHAT_TTL_MS = 60 * 60 * 1000;

interface StoredChat {
  sessionId: string;
  messages: Message[];
  updatedAt: number;
}

function loadStoredChat(): { sessionId: string; messages: Message[] } {
  try {
    const raw = localStorage.getItem(CHAT_STORAGE_KEY);
    if (raw) {
      const data = JSON.parse(raw) as StoredChat;
      if (data && Array.isArray(data.messages) && Date.now() - data.updatedAt < CHAT_TTL_MS) {
        return { sessionId: data.sessionId, messages: data.messages };
      }
    }
  } catch {
    /* corrupt storage — fall through to a fresh session */
  }
  localStorage.removeItem(CHAT_STORAGE_KEY);
  return { sessionId: crypto.randomUUID(), messages: [] };
}

function saveStoredChat(sessionId: string, messages: Message[]): void {
  try {
    localStorage.setItem(
      CHAT_STORAGE_KEY,
      JSON.stringify({ sessionId, messages, updatedAt: Date.now() } satisfies StoredChat),
    );
  } catch {
    /* quota exceeded / storage unavailable — non-fatal */
  }
}

export default function Chat() {
  const [initial] = useState(loadStoredChat); // runs once
  const [messages, setMessages] = useState<Message[]>(initial.messages);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const sessionIdRef = useRef<string>(initial.sessionId);
  const bottomRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView?.({ behavior: 'smooth' });
  }, []);

  // Persist the conversation (and refresh the idle timer) whenever it changes.
  useEffect(() => {
    if (messages.length > 0) saveStoredChat(sessionIdRef.current, messages);
  }, [messages]);

  // Jump to the latest message when returning to a restored conversation.
  useEffect(() => {
    if (initial.messages.length > 0) scrollToBottom();
  }, [initial.messages.length, scrollToBottom]);

  function handleNewChat() {
    setMessages([]);
    setStreamingContent('');
    sessionIdRef.current = crypto.randomUUID();
    localStorage.removeItem(CHAT_STORAGE_KEY);
  }

  async function handleSend(text: string) {
    const userMsg: Message = { id: crypto.randomUUID(), role: 'user', content: text };
    setMessages(prev => [...prev, userMsg]);
    setIsStreaming(true);
    setStreamingContent('');

    let accumulated = '';
    let finalCitations: Citation[] = [];

    await streamChat(text, sessionIdRef.current, {
      onDelta(delta) {
        accumulated += delta;
        setStreamingContent(accumulated);
        scrollToBottom();
      },
      onFinal(event) {
        finalCitations = event.citations;
      },
      onError(err) {
        setMessages(prev => [
          ...prev,
          { id: crypto.randomUUID(), role: 'assistant', content: `Sorry, something went wrong: ${err}` },
        ]);
        setIsStreaming(false);
        setStreamingContent('');
      },
    });

    if (accumulated) {
      setMessages(prev => [
        ...prev,
        { id: crypto.randomUUID(), role: 'assistant', content: accumulated, citations: finalCitations },
      ]);
    }
    setIsStreaming(false);
    setStreamingContent('');
    scrollToBottom();
  }

  return (
    <AppLayout>
      <div className="mx-auto w-full max-w-5xl px-6 py-6 flex flex-col h-screen">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-xl font-semibold text-ink">Ask Raseed</h1>
          <button
            onClick={handleNewChat}
            disabled={isStreaming || messages.length === 0}
            className="btn-secondary px-3 py-1.5"
          >
            New chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto mb-4 space-y-2">
          {messages.length === 0 && !isStreaming && (
            <p className="text-center text-faint text-sm mt-12">
              Ask me about your balance, subscriptions, spending, or any finance question.
            </p>
          )}
          {messages.map(msg => (
            <ChatMessage key={msg.id} role={msg.role} content={msg.content} citations={msg.citations} />
          ))}
          {isStreaming && streamingContent && (
            <ChatMessage role="assistant" content={streamingContent} isStreaming />
          )}
          <div ref={bottomRef} />
        </div>

        <ChatInput onSend={handleSend} isStreaming={isStreaming} />
      </div>
    </AppLayout>
  );
}
