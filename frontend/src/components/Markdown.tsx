// Minimal, dependency-free Markdown renderer for assistant chat messages.
// Renders to React nodes (never dangerouslySetInnerHTML), so it is XSS-safe. Handles
// the subset LLMs actually emit: bold, italics, inline code, bullet/numbered lists,
// and headings. Anything unrecognised falls through as plain text.
import type { ReactNode } from 'react';

function parseInline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  // bold (** or __), italic (* or _), inline code (`)
  const regex = /\*\*(.+?)\*\*|__(.+?)__|\*(.+?)\*|_(.+?)_|`(.+?)`/g;
  let last = 0;
  let n = 0;
  let m: RegExpExecArray | null;
  while ((m = regex.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    if (m[1] !== undefined || m[2] !== undefined) {
      nodes.push(<strong key={`${keyPrefix}-${n++}`}>{m[1] ?? m[2]}</strong>);
    } else if (m[3] !== undefined || m[4] !== undefined) {
      nodes.push(<em key={`${keyPrefix}-${n++}`}>{m[3] ?? m[4]}</em>);
    } else if (m[5] !== undefined) {
      nodes.push(
        <code
          key={`${keyPrefix}-${n++}`}
          className="px-1 py-0.5 rounded bg-elevated font-mono text-[0.85em]"
        >
          {m[5]}
        </code>,
      );
    }
    last = regex.lastIndex;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

interface ListItem {
  indent: number;
  content: string;
}

export default function Markdown({ text }: { text: string }): JSX.Element {
  const lines = text.replace(/\r\n/g, '\n').split('\n');
  const blocks: ReactNode[] = [];
  let para: string[] = [];
  let list: { ordered: boolean; items: ListItem[] } | null = null;
  let key = 0;

  const flushPara = (): void => {
    if (para.length === 0) return;
    const children: ReactNode[] = [];
    para.forEach((ln, i) => {
      if (i > 0) children.push(<br key={`br-${key}-${i}`} />);
      for (const node of parseInline(ln, `p${key}-${i}`)) children.push(node);
    });
    blocks.push(
      <p key={key++} className="mb-2 last:mb-0">
        {children}
      </p>,
    );
    para = [];
  };

  const flushList = (): void => {
    if (!list || list.items.length === 0) {
      list = null;
      return;
    }
    const cur = list;
    const Tag = cur.ordered ? 'ol' : 'ul';
    blocks.push(
      <Tag
        key={key++}
        className={`mb-2 last:mb-0 pl-5 space-y-1 ${cur.ordered ? 'list-decimal' : 'list-disc'}`}
      >
        {cur.items.map((it, i) => (
          <li
            key={i}
            style={it.indent > 0 ? { marginLeft: `${it.indent}rem` } : undefined}
          >
            {parseInline(it.content, `li${key}-${i}`)}
          </li>
        ))}
      </Tag>,
    );
    list = null;
  };

  for (const line of lines) {
    if (line.trim() === '') {
      flushPara();
      flushList();
      continue;
    }

    const header = /^(#{1,6})\s+(.*)$/.exec(line);
    const bullet = /^(\s*)[*-]\s+(.*)$/.exec(line);
    const ordered = /^(\s*)\d+\.\s+(.*)$/.exec(line);

    if (header) {
      flushPara();
      flushList();
      blocks.push(
        <p key={key++} className="font-semibold text-ink mt-1 mb-1">
          {parseInline(header[2], `h${key}`)}
        </p>,
      );
    } else if (bullet || ordered) {
      flushPara();
      const m = (bullet ?? ordered) as RegExpExecArray;
      const isOrdered = Boolean(ordered);
      const indent = Math.floor(m[1].replace(/\t/g, '  ').length / 2);
      if (!list) list = { ordered: isOrdered, items: [] };
      list.items.push({ indent, content: m[2] });
    } else {
      flushList();
      para.push(line);
    }
  }
  flushPara();
  flushList();

  return <div className="text-sm leading-relaxed">{blocks}</div>;
}
