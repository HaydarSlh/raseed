// Chat message bubble with optional citations (Phase 4)
import type { Citation } from '../api/chatApi';
import Markdown from './Markdown';

interface Props {
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  isStreaming?: boolean;
}

export default function ChatMessage({ role, content, citations = [], isStreaming = false }: Props) {
  const isUser = role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-3 shadow-card ${
          isUser
            ? 'bg-indigo-600 text-white rounded-br-md'
            : 'bg-surface border border-line text-ink rounded-bl-md'
        }`}
      >
        {isUser ? (
          <p className="text-sm whitespace-pre-wrap">{content}</p>
        ) : (
          <div className="text-sm">
            <Markdown text={content} />
            {isStreaming && <span className="animate-pulse ml-1">▊</span>}
          </div>
        )}

        {citations.length > 0 && (
          <div className="mt-2 pt-2 border-t border-line">
            <p className="text-xs text-faint mb-1">Sources:</p>
            <div className="flex flex-wrap gap-1">
              {citations.map((c, i) => (
                <span
                  key={i}
                  data-testid="citation-chip"
                  className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-indigo-50 text-indigo-700 border border-indigo-200 dark:bg-indigo-500/10 dark:text-indigo-300 dark:border-indigo-500/30"
                  title={c.heading_path}
                >
                  {c.document_slug}
                  {c.heading_path && (
                    <span className="ml-1 text-indigo-500 dark:text-indigo-400">› {c.heading_path.split(' > ').pop()}</span>
                  )}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
