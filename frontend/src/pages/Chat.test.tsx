// Tests: streaming chat page — sends message, renders incremental deltas, disables input during stream
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import Chat from './Chat';

vi.mock('../api/chatApi', () => ({
  streamChat: vi.fn(),
}));

import { streamChat } from '../api/chatApi';

const mockStreamChat = vi.mocked(streamChat);

function renderChat() {
  return render(
    <MemoryRouter>
      <Chat />
    </MemoryRouter>,
  );
}

describe('Chat page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear(); // chat now persists to localStorage — isolate tests
  });

  it('renders prompt input and send button', () => {
    renderChat();
    expect(screen.getByTestId('chat-input')).toBeDefined();
    expect(screen.getByTestId('chat-send')).toBeDefined();
  });

  it('disables input while response is streaming', async () => {
    let resolveFn: (() => void) | undefined;
    mockStreamChat.mockImplementation(async (_msg, _sid, callbacks) => {
      callbacks.onDelta('Hello ');
      await new Promise<void>((resolve) => {
        resolveFn = resolve;
      });
    });

    renderChat();
    const input = screen.getByTestId('chat-input') as HTMLTextAreaElement;
    const sendBtn = screen.getByTestId('chat-send') as HTMLButtonElement;

    fireEvent.change(input, { target: { value: 'What is my balance?' } });
    await act(async () => {
      fireEvent.click(sendBtn);
    });

    // Input and button should be disabled while streaming
    expect(input.disabled).toBe(true);
    expect(sendBtn.disabled).toBe(true);

    // Resolve the stream
    await act(async () => {
      resolveFn?.();
    });

    // After stream ends, input re-enabled
    await waitFor(() => expect(input.disabled).toBe(false));
  });

  it('renders user message immediately', async () => {
    mockStreamChat.mockImplementation(async (_msg, _sid, callbacks) => {
      callbacks.onDelta('Your balance is £1,234.');
      callbacks.onFinal({ done: true, route: 'deterministic', citations: [], bounded: false });
    });

    renderChat();
    const input = screen.getByTestId('chat-input');
    fireEvent.change(input, { target: { value: 'balance?' } });
    await act(async () => {
      fireEvent.click(screen.getByTestId('chat-send'));
    });

    expect(screen.getByText('balance?')).toBeDefined();
  });

  it('renders assistant response after streaming', async () => {
    mockStreamChat.mockImplementation(async (_msg, _sid, callbacks) => {
      callbacks.onDelta('Your balance is £500.');
      callbacks.onFinal({ done: true, route: 'deterministic', citations: [], bounded: false });
    });

    renderChat();
    fireEvent.change(screen.getByTestId('chat-input'), { target: { value: 'Balance?' } });
    await act(async () => {
      fireEvent.click(screen.getByTestId('chat-send'));
    });

    await waitFor(() => expect(screen.getByText('Your balance is £500.')).toBeDefined());
  });
});
