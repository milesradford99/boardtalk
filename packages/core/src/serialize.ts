import type { CardEvent, LogEntry } from "./events.ts";

/**
 * Stable text form of a card, the form a model reads (ADR 0001). Written once and never
 * re-rendered, so a serialized log only ever grows at the end.
 */
export function serializeCard(c: CardEvent): string {
  const lines = [`### #${c.id} [${c.kind}] ${c.title.trim()}`];
  if (c.body.trim()) lines.push(c.body.trim());
  if (c.verbatim.length) lines.push("verbatim: " + c.verbatim.map((v) => `\`${v}\``).join(" | "));
  const tail: string[] = [];
  if (c.refs.length) tail.push("refs: " + c.refs.map((r) => `#${r}`).join(" "));
  if (c.supersedes !== undefined && c.supersedes !== c.id) tail.push(`supersedes #${c.supersedes}`);
  if (tail.length) lines.push(tail.join(" · "));
  return lines.join("\n");
}

/** One JSON object per line, in seq order: the durable `.board` log body. */
export function toJsonl(log: readonly LogEntry[]): string {
  return log.map((e) => JSON.stringify(e)).join("\n") + (log.length ? "\n" : "");
}

export function fromJsonl(text: string): LogEntry[] {
  return text
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line) as LogEntry);
}
