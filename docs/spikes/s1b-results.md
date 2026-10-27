# Spike S1b results: writing from notes fixes support, and moves the exactness problem to the notes

Run 2026-10-27 on the Ark agent plan, `deepseek-v4.1-flash` for every call. Method: `s1b-plan.md`.
Raw tables: `spikes/s1/report_2.md` (S1b) and `report.md` (S1, re-scored on the new requirement
lists). Boards for both runs, side by side: the private gallery artifact (link in the PR).

**Verdict: S1b does not pass as planned** (measures 1, 2, 3 and 7 miss). It beats S1 on
faithfulness and density, and the remaining failures have clear, mostly mechanical causes. The human
review is still open.

## Result

| # | Measure | S1 (raw turns) | S1b (from notes) | Target |
|---|---|---|---|---|
| 1 | Verbatim not found in the session | 3.8 % | 4.3 %, **all of it copied from the cited notes** | ≤ 2 % |
| 2 | Claim support | 61.0 % supported, 1.1 % unsupported | **83.6 %** supported, **0 %** unsupported | ≥ 90 %, ≤ 3 % |
| 3 | Intent coverage (strict lists) | 83.3 % | 75.0 % | ≥ 90 % |
| 4 | "You should know" precision | 93.3 % (28 / 30) | 90.0 % (27 / 30) | ≥ 70 % |
| 5 | Flags the problem on failed runs | 5 of 5, 1 false alarm | 5 of 5, **0 false alarms** | ≥ 3 of 5 |
| 6 | Step narration | 1.1 % | 0.4 % | ≤ 10 % |
| 7 | Valid marks / dropped operations | 97.5 % / 1.3 % | 85.2 % / 11.9 % | ≥ 95 %, ≤ 5 % |
| 9 | Latency per call; card delay | 7.1 s per turn | 16.2 s per 5-turn window; delay median 0, max 4 turns | p50 ≤ 15 s; ≤ 5 turns |
| – | Cards per session | 15–52 (351 in all) | 15–30 (238 in all) | 8–15 |

Tokens: S1b used 3.1M of its 6M cap, including two smoke runs on falcon. The S1 re-score used
0.05M.

## Reading

1. **Citing notes makes claims checkable.** Supported claims rose from 61 % to 84 %, and none are
   unsupported. The rest are "partial", mostly a fair inference stated as fact.
2. **The exactness problem now sits in the notes.** Every one of the 60 strings missing from the
   session also appears in the S0 note the card cites: the per-turn note-taker composed them, and
   the writer copied faithfully. So measure 1 is fixed in stage one, mechanically: a note's
   `verbatim` items and code chips are checked against its own turn when the note is written, and
   failing items are removed before the note is stored (nothing on the board is edited).
3. **The strict check costs cards and marks.** S1b drops a card whose exact strings are not in the
   cited sources, and its marks go with it: 11.9 % of operations. A retry with the error as
   feedback, instead of a silent drop, should recover most of these.
4. **Intent is not a stage-two problem.** Both runs write intent from the same request. On the new,
   stricter lists S1 covers 83 % and S1b 75 %; neither reaches 90 %. The misses are mostly secondary
   items such as "keep existing arguments backward compatible" or "update the docstrings". A
   dedicated intent pass at the start (one call, the whole request, no other input) is the obvious
   next try.
5. **"You should know" survives the move.** Same precision, still 5 of 5 failed runs flagged, and the
   one false alarm is gone.
6. **Density improved but not enough.** 32 % fewer cards overall; long sessions still go to 25–30.

## What this means

- **Adopt the two-stage design** for the product: per-turn notes are the memory (ADR 0001) and the
  source the lecture cites; the lecture is written from them. It is better on every faithfulness
  measure that depends on stage two.
- **Three mechanical fixes before the next measurement:** check note strings against the turn at
  note time; retry a rejected lecture card once with the reason; write intent in one dedicated call.
  None needs a new model or more tokens per turn.
- **Measure them in the real integration, not another offline spike.** The fixes are code-level
  checks with obvious effects. The next spike with real value is S2 (the live loop), where the board
  is built while the agent works.

## Human review

Open. Same three sessions as S1 (falcon, lingua-franca, sqlglot), now with both boards each: "Would
you keep this as the record of the session?" for each board, and which of the two you prefer.

## Notes on method

- The writer prompt was tuned on falcon in two smoke runs (30 cards in the first, 14 in the second),
  then all 10 sessions ran once on the final prompt, falcon included.
- The requirement lists were regenerated with a stricter prompt ("only what the request says"); the
  invented `to_wgs84` items are gone. S1 was re-scored on the same lists: 64.5 % on the old lists,
  83.3 % on the new.
- The writer hit its output limit twice on pymdown-extensions; those two windows wrote nothing.
- Same-model judging, as in S1.
