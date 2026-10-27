# Spike S1b: lecture cards written from per-turn notes

Status: **run** (approved and run 2026-10-27). Results: `s1b-results.md`.

## Question

S1 (`s1-results.md`) showed that a scribe watching raw turns draws a readable design board with
good "You should know" notes, but its claims are hard to check (61 % supported), it composes exact
strings that never appeared (3.8 %), it misses generic intent items, and it overruns the card budget
on long sessions. S1 also settled that the per-turn notes stay the model's memory.

S1b asks: if the lecture writer reads the **per-turn notes** instead of raw turns, and cites them, do
claim support, verbatim and intent coverage reach their bars without losing what S1 got right?

## Design

- **Stage 1: per-turn notes.** Reuse S0's `deepseek-v4.1-flash` notes as they are
  (`spikes/s0/data/out/<tid>/board_flash.json`): 975 notes over 833 turns, with exact strings in
  `verbatim`. No new calls. This is the memory layer from ADR 0001, so the lecture adds no second
  memory.
- **Stage 2: the lecture writer.** It runs after every 5 agent turns and at the final turn (about 175
  calls). Input: the request, the lecture board so far, and the notes added since the last call,
  each with its note id. Output: the same card and mark schema as S1, except that `src_turns`
  becomes `src_notes` (note ids, or -1 for the request).
- **Exact strings come from notes.** A card's `verbatim` items and code chips must occur in its
  cited notes or the request, checked in code. A card that fails the check is dropped and counted, as
  in S1.
- **Intent prompt** lists the kinds of requirement to look for: the behaviour asked for, files or
  areas not to touch, tests to run or keep passing, "minimal change" and similar constraints.
- **Card budget:** as in S1 (8–15 per session, at most 3 notes). The five-turn window should make
  this easier, because the writer sees a short burst of work at once.
- Everything else (append-only checks, marks, rendering) is unchanged from S1.

## Measures

The same as S1, with three changes:

| # | Measure | Change from S1 | Target |
|---|---|---|---|
| 1 | Verbatim | Checked against the raw source as in S1, and separately against the cited notes | ≤ 2 % missing from the source |
| 2 | Claim support | The judge sees the cited notes **and** the raw turns those notes come from | ≥ 90 % supported, ≤ 3 % unsupported |
| 3 | Intent coverage | Requirement lists regenerated with a stricter prompt ("only what the text says; no outside knowledge"). The user spot-checks 2. S1's boards are re-scored on the same lists so the two are comparable | ≥ 90 % |
| 4, 5 | "You should know" | As in S1. The risk is losing detail that the notes dropped | ≥ 70 % precise; ≥ 3 of 5 |
| 6, 7 | Formality, anchors | As in S1 | ≤ 10 %; ≥ 95 % / ≤ 5 % |
| 8 | Memory | Dropped: the notes are the memory, already measured in S0/S0b | – |
| 9 | Delay | Turns between a fact appearing in the session and its card appearing on the board (median), plus latency per call | median ≤ 5 turns; p50 ≤ 15 s |

Card count per session is reported, with the 8–15 budget as the reference.

## Human review

The same three sessions as S1 (falcon, lingua-franca, sqlglot), shown **side by side**: S1's board
and S1b's board. The user answers "Would you keep this as the record?" for each board and which one
they prefer. This also covers S1's open review.

## Pass criteria

Measures 1, 2, 3 and 7 meet their targets; 4 or 5 meets its target; at least 2 of the 3 S1b boards
are kept "yes" or "with fixes". If S1b passes, the two-stage design goes into ADR 0001 and the event
model proposal (card kind, marks, heads-up label, note citations). If it fails on 1 or 2, the
next step is to make the scribe copy exact strings by id rather than by text.

## Budget

| Item | Calls | Est. tokens |
|---|---|---|
| Lecture writer | ~175 | ~1.5M |
| Requirement lists (10) and coverage (S1 + S1b boards) | 30 | ~0.2M |
| Claim, formality judging | ~70 | ~1.2M |
| "You should know" judging (full transcript) | 10 | ~0.8M |
| **Total** | | **~3.7M**, own cap 6M (S1 used 7.9M of its 15M) |

## Implementation

`spikes/s1/` gains `lecture2.py` (stage 2) and options on `judge.py`, `check.py`, `render.py` and
`gallery.py` for the two-stage boards. Outputs go in `spikes/s1/data/out/<tid>/lecture2.json`. Dry
run with the fake client, then 1 session, then all 10.
