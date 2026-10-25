import type { CardEvent } from "./events.ts";

const normalize = (s: string) => s.replace(/\s+/g, " ").trim();

export interface VerbatimCheck {
  verified: string[];
  /** Claimed verbatim strings not found in the source: shown as unverified, never as fact. */
  unverified: string[];
}

/** Check a card's verbatim claims against the source text it cites (whitespace-normalized). */
export function checkVerbatim(card: CardEvent, sourceText: string): VerbatimCheck {
  const haystack = normalize(sourceText);
  const result: VerbatimCheck = { verified: [], unverified: [] };
  for (const v of card.verbatim) {
    if (!v.trim()) continue;
    (haystack.includes(normalize(v)) ? result.verified : result.unverified).push(v);
  }
  return result;
}

/** True when every serialized snapshot is a byte prefix of the next (the append-only property). */
export function isPrefixChain(snapshots: readonly string[]): boolean {
  return snapshots.every((s, i) => i === 0 || s.startsWith(snapshots[i - 1] ?? ""));
}
