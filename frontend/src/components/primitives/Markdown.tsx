import type { ReactNode } from "react";

/** Minimal, dependency-free markdown → React: headings, bold, inline code, code
 *  fences, bullet/numbered lists, and horizontal rules. Unmatched text degrades to
 *  plain paragraphs, so it never renders worse than raw text. */
function renderInline(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) {
      out.push(<strong key={i++}>{tok.slice(2, -2)}</strong>);
    } else {
      out.push(
        <code key={i++} className="mono rounded bg-canvas-deep px-1 py-0.5 text-[12px]">
          {tok.slice(1, -1)}
        </code>,
      );
    }
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export function Markdown({ text, className = "" }: { text: string; className?: string }) {
  const lines = (text || "").split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (line.trim().startsWith("```")) {
      const code: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        code.push(lines[i]);
        i++;
      }
      i++; // skip closing fence
      blocks.push(
        <pre
          key={key++}
          className="mono my-2 overflow-x-auto rounded-lg bg-canvas-deep p-3 text-[12px] leading-relaxed text-ink"
        >
          <code>{code.join("\n")}</code>
        </pre>,
      );
      continue;
    }

    if (/^---+$/.test(line.trim())) {
      blocks.push(<div key={key++} className="rule my-3" />);
      i++;
      continue;
    }

    const h = line.match(/^(#{1,6})\s+(.*)$/);
    if (h) {
      blocks.push(
        <div key={key++} className="mt-3 mb-1 text-[13px] font-bold text-ink">
          {renderInline(h[2])}
        </div>,
      );
      i++;
      continue;
    }

    const li = line.match(/^(\s*)([-*]|\d+\.)\s+(.*)$/);
    if (li) {
      const ordered = /\d/.test(li[2]);
      blocks.push(
        <div key={key++} className="ml-3 flex gap-2 text-[13px] leading-relaxed text-ink">
          <span className="shrink-0 text-ink-mute">{ordered ? li[2] : "•"}</span>
          <span>{renderInline(li[3])}</span>
        </div>,
      );
      i++;
      continue;
    }

    if (line.trim() === "") {
      blocks.push(<div key={key++} className="h-2" />);
      i++;
      continue;
    }

    blocks.push(
      <p key={key++} className="text-[13px] leading-relaxed text-ink">
        {renderInline(line)}
      </p>,
    );
    i++;
  }

  return <div className={`flex flex-col ${className}`}>{blocks}</div>;
}
