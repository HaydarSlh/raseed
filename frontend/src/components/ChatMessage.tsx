// Chat message bubble with optional citations (Phase 4)
import type { Citation } from '../api/chatApi';

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
        className={`max-w-[75%] rounded-lg px-4 py-3 ${
          isUser
            ? 'bg-blue-600 text-white'
            : 'bg-white border border-gray-200 text-gray-800'
        }`}
      >
        <p className="text-sm whitespace-pre-wrap">
          {content}
          {isStreaming && <span className="animate-pulse ml-1">▊</span>}
        </p>

        {citations.length > 0 && (
          <div className="mt-2 pt-2 border-t border-gray-200">
            <p className="text-xs text-gray-500 mb-1">Sources:</p>
            <div className="flex flex-wrap gap-1">
              {citations.map((c, i) => (
                <span
                  key={i}
                  data-testid="citation-chip"
                  className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-blue-50 text-blue-700 border border-blue-200"
                  title={c.heading_path}
                >
                  {c.document_slug}
                  {c.heading_path && (
                    <span className="ml-1 text-blue-500">› {c.heading_path.split(' > ').pop()}</span>
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
