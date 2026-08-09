"use client";

import { Fragment } from "react";
import { Linkify } from "@/components/linkify";

/** Render an assistant answer.
 *
 * The model is told to write plain prose, but models emit markdown anyway, and
 * rendering it as plain text meant readers saw literal asterisks. This handles
 * the few things that actually turn up — bold, bullet lists, numbered lists —
 * and leaves everything else as written.
 *
 * It builds React elements rather than HTML, so there is nothing to sanitise:
 * a model that emitted a <script> tag would produce the text of one.
 */
const BOLD = /\*\*(.+?)\*\*|__(.+?)__/g;
const BULLET = /^\s*[-*•]\s+/;
const NUMBERED = /^\s*(\d+)[.)]\s+/;

function Inline({ text }: { text: string }) {
  const parts: React.ReactNode[] = [];
  let last = 0;
  for (const match of text.matchAll(BOLD)) {
    const at = match.index ?? 0;
    if (at > last) {
      parts.push(<Linkify key={`t${last}`} text={text.slice(last, at)} />);
    }
    parts.push(
      <strong key={`b${at}`} className="font-semibold">
        {match[1] ?? match[2]}
      </strong>,
    );
    last = at + match[0].length;
  }
  if (last < text.length) {
    parts.push(<Linkify key={`t${last}`} text={text.slice(last)} />);
  }
  return <>{parts}</>;
}

export function AnswerText({ content }: { content: string }) {
  const lines = content.split("\n");
  const blocks: React.ReactNode[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;

  function flush(key: string) {
    if (!list) return;
    const Tag = list.ordered ? "ol" : "ul";
    blocks.push(
      <Tag
        key={key}
        className={
          list.ordered
            ? "my-1.5 list-decimal space-y-1 ps-5"
            : "my-1.5 list-disc space-y-1 ps-5"
        }
      >
        {list.items.map((item, i) => (
          <li key={i}>
            <Inline text={item} />
          </li>
        ))}
      </Tag>,
    );
    list = null;
  }

  lines.forEach((line, i) => {
    const bullet = line.match(BULLET);
    const numbered = line.match(NUMBERED);

    if (bullet) {
      if (list && list.ordered) flush(`l${i}`);
      list ??= { ordered: false, items: [] };
      list.items.push(line.replace(BULLET, ""));
      return;
    }
    if (numbered) {
      if (list && !list.ordered) flush(`l${i}`);
      list ??= { ordered: true, items: [] };
      list.items.push(line.replace(NUMBERED, ""));
      return;
    }

    flush(`l${i}`);
    if (line.trim() === "") {
      blocks.push(<div key={`s${i}`} className="h-2" />);
      return;
    }
    // A heading marker is stripped rather than rendered: the model was asked
    // not to use them, and a heading inside a chat bubble looks wrong.
    const text = line.replace(/^#{1,6}\s+/, "");
    blocks.push(
      <p key={`p${i}`}>
        <Inline text={text} />
      </p>,
    );
  });
  flush("l-end");

  return <div className="space-y-0.5 text-sm text-foreground">{blocks}</div>;
}
