// Chat prompt input box with send button and streaming-state disable (Phase 4)
import { FormEvent, KeyboardEvent, useRef } from 'react';

interface Props {
  onSend: (message: string) => void;
  isStreaming: boolean;
}

export default function ChatInput({ onSend, isStreaming }: Props) {
  const ref = useRef<HTMLTextAreaElement>(null);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const text = ref.current?.value.trim();
    if (!text || isStreaming) return;
    onSend(text);
    if (ref.current) ref.current.value = '';
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as unknown as FormEvent);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 items-end">
      <textarea
        ref={ref}
        rows={2}
        disabled={isStreaming}
        onKeyDown={handleKeyDown}
        placeholder="Ask about your finances…"
        className="flex-1 resize-none rounded-lg border border-line bg-surface text-ink placeholder:text-faint px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500 disabled:opacity-50"
        data-testid="chat-input"
      />
      <button
        type="submit"
        disabled={isStreaming}
        className="btn-primary"
        data-testid="chat-send"
      >
        {isStreaming ? 'Thinking…' : 'Send'}
      </button>
    </form>
  );
}
