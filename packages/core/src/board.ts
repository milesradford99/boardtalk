import type { BoardEvent, CardEvent, DigestEvent, LogEntry, PendingEvent } from "./events.ts";

export class AppendOnlyViolation extends Error {}

/** The board state a log replays to. Superseded items stay in `all`; `visible` hides them. */
export interface Board {
  all: Map<number, PendingEvent | CardEvent | DigestEvent>;
  superseded: Set<number>;
  visible: Array<PendingEvent | CardEvent | DigestEvent>;
}

/**
 * Append one event to a log, enforcing the board's invariants:
 * ids are never reused except by a card superseding its own pending placeholder,
 * `supersedes` and `refs` must point to existing items, and `seq` has no gaps.
 */
export function append(log: readonly LogEntry[], event: BoardEvent): LogEntry[] {
  const board = replay(log);
  const existing = board.all.get(event.id);
  const fillsPlaceholder =
    event.type === "card" && existing?.type === "pending" && event.supersedes === event.id;
  if (existing && !fillsPlaceholder) {
    throw new AppendOnlyViolation(`id #${event.id} already exists; append a superseding card instead`);
  }
  if (event.type === "card") {
    if (event.supersedes !== undefined && !board.all.has(event.supersedes)) {
      throw new AppendOnlyViolation(`#${event.id} supersedes unknown #${event.supersedes}`);
    }
    const missing = event.refs.filter((r) => !board.all.has(r));
    if (missing.length) throw new AppendOnlyViolation(`#${event.id} refs unknown ${missing.join(", ")}`);
  }
  return [...log, { seq: log.length, event }];
}

export function replay(log: readonly LogEntry[]): Board {
  const all = new Map<number, PendingEvent | CardEvent | DigestEvent>();
  const superseded = new Set<number>();
  log.forEach((entry, i) => {
    if (entry.seq !== i) throw new AppendOnlyViolation(`seq gap at position ${i} (found ${entry.seq})`);
    const e = entry.event;
    if (e.type === "card" && e.supersedes !== undefined && e.supersedes !== e.id) superseded.add(e.supersedes);
    all.set(e.id, e);
  });
  const visible = [...all.values()].filter((e) => !superseded.has(e.id));
  return { all, superseded, visible };
}
