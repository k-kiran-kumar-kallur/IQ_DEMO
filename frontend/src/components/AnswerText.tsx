import type { ReactNode } from "react";

type Props = { text: string; onCite: (cid: string) => void; validCids: Set<string> };

/** Renders the answer: paragraphs, bullet lists, **bold**, and [C#] citations as clickable chips. */
export function AnswerText({ text, onCite, validCids }: Props) {
  const inline = (line: string, key: string): ReactNode[] => {
    const parts = line.split(/(\[C\d+\]|\*\*[^*]+\*\*)/g).filter(Boolean);
    return parts.map((p, i) => {
      const cite = p.match(/^\[(C\d+)\]$/);
      if (cite) {
        const ok = validCids.has(cite[1]);
        return (
          <button
            key={`${key}-${i}`}
            className={`cite ${ok ? "" : "cite-bad"}`}
            onClick={() => ok && onCite(cite[1])}
            title={ok ? `Show evidence ${cite[1]}` : "Citation not found in evidence"}
          >
            {cite[1]}
          </button>
        );
      }
      if (p.startsWith("**") && p.endsWith("**")) return <strong key={`${key}-${i}`}>{p.slice(2, -2)}</strong>;
      return <span key={`${key}-${i}`}>{p}</span>;
    });
  };

  const blocks: ReactNode[] = [];
  let list: string[] = [];
  const flush = () => {
    if (list.length) {
      const items = list;
      blocks.push(
        <ul key={`ul-${blocks.length}`}>
          {items.map((l, i) => (
            <li key={i}>{inline(l, `li-${blocks.length}-${i}`)}</li>
          ))}
        </ul>
      );
      list = [];
    }
  };
  text.split("\n").forEach((raw, i) => {
    const line = raw.trim();
    const bullet = line.match(/^([-*•]|\d+[.)])\s+(.*)$/);
    if (bullet) {
      list.push(bullet[2]);
    } else {
      flush();
      if (line) blocks.push(<p key={`p-${i}`}>{inline(line, `p-${i}`)}</p>);
    }
  });
  flush();
  return <div className="answer-text">{blocks}</div>;
}
