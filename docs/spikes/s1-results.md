# Spike S1 results: the lecture board is a good view and a poor memory

Run 2026-10-26/27 on the Ark agent plan, `deepseek-v4.1-flash` for every call. Same 10 trajectories
and S0 questions as before. Method: `s1-plan.md`. Raw table: `spikes/s1/report.md`. Rendered boards:
private gallery artifact (link in the PR).

**Verdict: S1 does not pass as planned.** Measures 4–7 and 9 meet their targets; 1, 2 and 3 do not.
The human review (3 boards) is still open. Measure 8 answers the ADR question clearly: the lecture
board should not be the model's memory.

## Result

| # | Measure | Result | Target | Met |
|---|---|---|---|---|
| 1 | Verbatim not found | 3.8 % (64 / 1,696) | ≤ 2 % | no |
| 2 | Claim support | 61.0 % supported, 37.9 % partial, 1.1 % unsupported (351 cards) | ≥ 90 %, ≤ 3 % | no |
| 3 | Intent coverage | 64.5 % yes, 14.5 % partial (62 requirements); 73.6 % / 88.7 % without one bad gold list | ≥ 90 % | no |
| 4 | "You should know" precision | 92.6 % true and new (25 / 27); median 3 per session | ≥ 70 %, ≤ 3 | yes |
| 5 | Flags the problem on failed runs | 4 of 4 judged (sqlglot pending); 1 false alarm on 5 resolved runs | ≥ 3 of 5 | yes |
| 6 | Step narration | 1.1 % | ≤ 10 % | yes |
| 7 | Marks valid / operations dropped | 97.5 % / 1.3 % | ≥ 95 %, ≤ 5 % | yes |
| 8 | Memory (S0 questions, after the last fold) | lecture 58.8 · per-turn board 97.2 · summary 58.8 | informational | – |
| 9 | Scribe latency | p50 7.1 s, p95 14.9 s; 80 % of input from cache | p50 ≤ 15 s | yes |

Tokens: 7.8M of the 15M cap (scribe 5.1M including two smoke runs, judging 1.8M, memory test 0.9M).

## Reading

1. **The board reads as a design record.** Only 1.1 % of cards narrate steps. Revisions are used
   (1–18 per session), and the scribe marks key facts with 97.5 % valid anchors.
2. **"You should know" is the strongest part.** 25 of 27 notes are true and not already said by the
   agent. On every failed run judged so far, a note named a real reason for the failure: the fix
   checked only with the agent's own script, a reproduction that never ran, a heuristic that
   mis-aligns region names, a test run against a hand-copied file in `site-packages`. The one false
   alarm (MontePy) predicted an `AttributeError` that the transcript contradicts.
3. **Claims are mostly right but cite too narrowly.** Only 1.1 % are unsupported. The 38 % "partial"
   are mostly cards that combine the current turn with what the board already knew, or add an
   inference, while citing only the current turn. The judge sees only the cited turns, so this is
   partly a citation problem. It still fails the bar: a reader can't check a claim whose source
   isn't cited.
4. **Verbatim misses are composed strings.** For example `falcon/asgi/app.py:669` joins a path and
   a line number that appear separately, and `md_in_html is not what triggers the leak` is prose in
   backticks. S0's per-turn flash scribe missed 1.7 %, so the higher-level writing costs exactness.
5. **Intent misses generic requirements.** The scribe records the issue well but often skips
   boilerplate constraints ("run the existing tests", "keep the change minimal"). One gold list
   (geopandas) is wrong: the extractor invented a `to_wgs84` keyword that the issue never mentions,
   which is why the plan asked for a human spot-check of these lists.
6. **The card budget isn't kept on long sessions.** Boards have 15–52 cards. The prompt asks for
   8–15, which held only on the shortest session.
7. **Memory: lecture cards are not enough.** At about 2.7k tokens the lecture board recalls 58.8 %,
   the same as the 2.0k-token summary. In S0b, the digested per-turn board at about 2k tokens
   recalled 85 %. Size is not the issue: the lecture omits the dead ends (35.7 %) and exact
   identifiers that a continuing agent needs. The per-turn board (33k tokens) recalls 97.2 %.

## What this means

- **ADR 0001: the per-turn notes stay the model's context** (with S0b's digest for folds), and the
  lecture board is a **view** for the human. By the plan's rule the lecture ties the summary, but
  it is 38 points below the per-turn board, so recommending it as context would lose most of the
  ADR's gain.
- **Next scribe design: two stages,** the fallback the plan named for density. Stage one is the S0
  per-turn notes (exact, 97 % recall). Stage two writes lecture cards *from the notes*, citing note
  ids instead of turns. This should fix measures 1 and 2: a card's source is a short note that already
  holds the exact strings, and the judge can check against it. It also makes the card budget easier,
  since the lecture writer sees a compact log.
- Keep "You should know" in the lecture stage; it already works.
- Add the generic constraints from the request to the intent prompt explicitly ("tests to run",
  "files not to touch", "minimal change").

## Human review

Open. The gallery picks (seed 20261026): falconry/falcon (resolved), MycroftAI/lingua-franca
(resolved, 52 cards), tobymao/sqlglot (unresolved). The question for each: "Would you keep this as
the record of the session?" Pass needs 2 of 3 answered "yes" or "with fixes".

## Notes on method

- The prompt was tuned on one session (falcon) in two smoke runs before the main run: the first draw
  had 26 cards with 13 per-test-run evidence cards and 8 notes. All 10 sessions, falcon included,
  then ran once on the final prompt. No tuning on the measured run.
- The judge is the same model as the scribe. Mechanical measures (1, 7, 9) don't depend on it.
- Prototype issue found while rendering: long code chips overflow the 380 px column.
