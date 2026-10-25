import assert from "node:assert/strict";
import { test } from "node:test";

import {
  AppendOnlyViolation,
  append,
  checkVerbatim,
  fromJsonl,
  isPrefixChain,
  replay,
  serializeCard,
  toJsonl,
  type CardEvent,
  type LogEntry,
} from "../src/index.ts";

const card = (over: Partial<CardEvent> = {}): CardEvent => ({
  type: "card",
  id: 1,
  kind: "observation",
  title: "Found the DAS writer",
  body: "Malformed line comes from the iterable branch.",
  verbatim: ["src/pydap/responses/das.py", "build_attributes"],
  refs: [],
  src: [{ entryId: "a1b2c3d4" }],
  ...over,
});

test("a scribe card fills its pending placeholder; the placeholder disappears from view", () => {
  let log: LogEntry[] = [];
  log = append(log, { type: "pending", id: 1, label: "bash: grep -rn WMO_code", src: [{ entryId: "e1" }] });
  log = append(log, card({ supersedes: 1 }));
  const board = replay(log);
  assert.equal(board.visible.length, 1);
  assert.equal(board.visible[0]?.type, "card");
});

test("a correction is a new card that supersedes the old one; both stay in the log", () => {
  let log: LogEntry[] = [];
  log = append(log, card());
  log = append(log, card({ id: 2, title: "Correction", supersedes: 1 }));
  const board = replay(log);
  assert.deepEqual(board.visible.map((e) => e.id), [2]);
  assert.equal(board.all.size, 2);
  assert.ok(board.superseded.has(1));
});

test("reusing an id, superseding or referencing an unknown card is rejected", () => {
  const log = append([], card());
  assert.throws(() => append(log, card()), AppendOnlyViolation);
  assert.throws(() => append(log, card({ id: 2, supersedes: 9 })), AppendOnlyViolation);
  assert.throws(() => append(log, card({ id: 2, refs: [7] })), AppendOnlyViolation);
});

test("replay rejects a log with a seq gap (an entry was removed)", () => {
  const log = append(append([], card()), card({ id: 2 }));
  assert.throws(() => replay([log[1]!]), AppendOnlyViolation);
});

test("verbatim claims are checked against the source, whitespace-normalized", () => {
  const source = "cat -n src/pydap/responses/das.py\n  def   build_attributes(attr, values, level=0):";
  const result = checkVerbatim(card({ verbatim: ["src/pydap/responses/das.py", "def build_attributes(", "IndexError: list index out of range"] }), source);
  assert.deepEqual(result.verified, ["src/pydap/responses/das.py", "def build_attributes("]);
  assert.deepEqual(result.unverified, ["IndexError: list index out of range"]);
});

test("serialized snapshots of a growing log form a prefix chain", () => {
  const cards = [card(), card({ id: 2, refs: [1] }), card({ id: 3, supersedes: 2 })];
  const snapshots = cards.map((_, i) => cards.slice(0, i + 1).map(serializeCard).join("\n\n"));
  assert.ok(isPrefixChain(snapshots));
  assert.ok(!isPrefixChain([snapshots[1]!, snapshots[0]!]));
});

test("the JSONL log round-trips", () => {
  const log = append(append([], card()), card({ id: 2, refs: [1] }));
  assert.deepEqual(fromJsonl(toJsonl(log)), log);
});
