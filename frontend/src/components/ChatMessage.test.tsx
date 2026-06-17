// Tests: ChatMessage citation rendering (FR-013)
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import ChatMessage from './ChatMessage';

describe('ChatMessage', () => {
  it('renders user message bubble on the right', () => {
    const { container } = render(
      <ChatMessage role="user" content="Hello Raseed" />,
    );
    expect(screen.getByText('Hello Raseed')).toBeDefined();
    expect(container.querySelector('.justify-end')).toBeDefined();
  });

  it('renders assistant message bubble on the left', () => {
    const { container } = render(
      <ChatMessage role="assistant" content="Your balance is £500." />,
    );
    expect(screen.getByText('Your balance is £500.')).toBeDefined();
    expect(container.querySelector('.justify-start')).toBeDefined();
  });

  it('renders one citation chip per source when citations provided', () => {
    render(
      <ChatMessage
        role="assistant"
        content="You should save 3-6 months of expenses."
        citations={[
          { document_slug: 'emergency-funds', heading_path: 'How Much Should You Save?' },
          { document_slug: 'building-savings', heading_path: 'The Pay-Yourself-First Principle' },
        ]}
      />,
    );
    const chips = screen.getAllByTestId('citation-chip');
    expect(chips).toHaveLength(2);
    expect(chips[0].textContent).toContain('emergency-funds');
    expect(chips[1].textContent).toContain('building-savings');
  });

  it('renders no citation section when citations is empty array', () => {
    render(
      <ChatMessage role="assistant" content="Your balance is fine." citations={[]} />,
    );
    expect(screen.queryByTestId('citation-chip')).toBeNull();
  });

  it('renders no citation section when citations is not provided', () => {
    render(<ChatMessage role="assistant" content="Hello" />);
    expect(screen.queryByTestId('citation-chip')).toBeNull();
  });

  it('shows streaming cursor when isStreaming=true', () => {
    const { container } = render(
      <ChatMessage role="assistant" content="Thinking" isStreaming />,
    );
    expect(container.textContent).toContain('▊');
  });
});
