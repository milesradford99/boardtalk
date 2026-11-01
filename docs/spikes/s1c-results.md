# Spike S1c results: the three fixes close exactness and drops

Run 2026-11-01 on the Ark agent plan, `deepseek-v4.1-flash` for every call. This applies the three
fixes named in `s1b-results.md` to the two-stage scribe, on the same 10 sessions. Raw table:
`spikes/s1/report_3.md`. Boards: the private gallery artifact, next to S1 and S1b.

**Verdict: S1c does not pass as planned, and it is the best board so far.** Exact strings are solved.
Claim support (84 %) is the one real miss. Intent (88 %) and valid marks (94.6 %) fall just short.
"You should know" holds up on 9 of the 10 sessions. The human review is still open.

## The fixes

1. **Note strings checked against the session.** Before a note is used, each `verbatim` item and code
   chip must occur in the session up to that turn. A failing chip becomes plain text and a failing
   `verbatim` item is removed. A lecture card's exact strings must also occur in the session.
2. **One retry for rejected operations,** with the reason given back to the writer.
3. **One dedicated intent call** at the start, reading only the request and listing every requirement.

## Result

| # | Measure | S1b | S1c | Target | Met |
|---|---|---|---|---|---|
| 1 | Verbatim not found in the session | 4.3 % | **0 % (0 / 1,352)** | ≤ 2 % | yes |
| 2 | Claim support | 83.6 %, 0 % unsupported | 84.1 %, 0 % unsupported | ≥ 90 %, ≤ 3 % | no |
| 3 | Intent coverage (same strict lists) | 75.0 % | **88.3 %** (95 % with partial) | ≥ 90 % | no |
| 4 | "You should know" precision | 90.0 % | 92.6 % (25 / 27, 9 sessions judged) | ≥ 70 % | yes |
| 5 | Flags the problem on failed runs | 5 of 5, 0 false alarms | 5 of 5, 0 false alarms on 4 of 5 resolved runs | ≥ 3 of 5 | yes |
| 6 | Step narration | 0.4 % | 0 % | ≤ 10 % | yes |
| 7 | Valid marks / dropped operations | 85.2 % / 11.9 % | 94.6 % / **4.0 %** | ≥ 95 %, ≤ 5 % | marks no, drops yes |
| 9 | Latency per call; card delay | 16.2 s; median 0, max 4 turns | 12.5 s; median 0, max 4 turns | p50 ≤ 15 s; ≤ 5 turns | yes |
| – | Cards per session | 15–30 (238 in all) | 14–31 (227 in all) | 8–15 | no |

Tokens: 3.31M, made up of the 2.9M left from S1b's approved 6M plus about 0.4M the user approved to
finish the judging.

## Reading

1. **Exactness is solved by code, not by prompting.** No exact string on any board is missing from
   its session. The check is cheap and belongs in the product scribe. It removes 8.7 % of the strings
   in the notes, far more than S0's 1.7 % rate, because it also covers body chips and only counts
   the session up to that turn. Many removed chips will be fair shorthand, so a removed chip is not
   always a fabrication. It stays in the note as plain text.
2. **Retries work.** 102 operations were rejected on first try, and only 15 stayed dropped.
3. **The dedicated intent call helps.** Coverage rose by 13 points. Of the 7 requirements not fully
   covered, 3 are environment or process items ("compare against the base commit", "do not install
   packages", "existing tests still pass"). The requirement lists were not changed to reach this.
4. **Claim support did not move,** as expected: none of the fixes target it. The 16 % "partial" are
   mostly inferences stated as fact. Closing this gap needs a change to the writer, such as marking
   inferences in the card's wording, or a judge calibration check by a person.
5. **Card count did not move.** Long sessions still reach 28–31 cards.

## Not measured

"You should know" was judged on 9 of the 10 sessions. The tenth, idaholab/MontePy (a resolved run),
was not judged because the ledger reached the 3.3M cap first, so its 4 notes are outside measure 4
and the false-alarm count. It is about 0.05M tokens to finish.

One note in the 27 is a wrong claim that the judge marked untrue: a geopandas card reports a CRS
misfire that later runs in the transcript contradict. That was a failed run, so it does not count
as a false alarm under the plan's definition, but it is the kind of note a reader would be misled by.

## Notes on method

- One smoke run on falcon, with no prompt change after it, so that session's result stands.
- Same-model judging, as in S1 and S1b.
