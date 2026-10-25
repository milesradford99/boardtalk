/**
 * The board is an append-only log of events. Nothing is ever edited or removed:
 * a correction is a new card that `supersedes` an older one, and a pending card
 * (shown the moment a tool starts) is superseded by the scribe's card.
 */

/** Points at the source material a card was written from, e.g. a pi session entry id. */
export interface SourceRef {
  /** Stable id of the source entry (pi: the session entry `id`). */
  entryId: string;
}

export const CARD_KINDS = [
  "goal",
  "plan",
  "action",
  "observation",
  "decision",
  "error",
  "state",
  "handoff",
] as const;
export type CardKind = (typeof CARD_KINDS)[number];

export interface PendingEvent {
  type: "pending";
  /** Card id this placeholder occupies; the scribe's card supersedes it. */
  id: number;
  label: string;
  src: SourceRef[];
}

export interface CardEvent {
  type: "card";
  id: number;
  kind: CardKind;
  title: string;
  body: string;
  /** Exact identifiers (paths, commands, errors) claimed to appear verbatim in the source. */
  verbatim: string[];
  refs: number[];
  supersedes?: number;
  src: SourceRef[];
}

export interface DigestEvent {
  type: "digest";
  id: number;
  /** Card ids this digest summarizes; the cards stay in the log. */
  covers: number[];
  body: string;
}

export type BoardEvent = PendingEvent | CardEvent | DigestEvent;

/** One line of the log: an event plus its position. `seq` starts at 0 and has no gaps. */
export interface LogEntry {
  seq: number;
  event: BoardEvent;
}
