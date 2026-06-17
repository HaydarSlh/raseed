// Chat page: streaming chat surface (Phase 4, FR-001/002)
import { useCallback, useRef, useState } from 'react';
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

let _sessionId: string | null = null;
function getSessionId(): string {
  if (!_sessionId) {
    _sessionId = crypto.randomUUID();
  }
  return _sessionId;
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView?.({ behavior: 'smooth' });
  }, []);

  async function handleSend(text: string) {
    const userMsg: Message = { id: crypto.randomUUID(), role: 'user', content: text };
    setMessages(prev => [...prev, userMsg]);
    setIsStreaming(true);
    setStreamingContent('');

    let accumulated = '';
    let finalCitations: Citation[] = [];

    await streamChat(text, getSessionId(), {
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
    <div className="max-w-3xl mx-auto px-4 py-6 flex flex-col h-[calc(100vh-4rem)]">
      <h1 className="text-xl font-semibold text-gray-800 mb-4">Ask Raseed</h1>

      <div className="flex-1 overflow-y-auto mb-4 space-y-2">
        {messages.length === 0 && !isStreaming && (
          <p className="text-center text-gray-400 text-sm mt-12">
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
  );
}
