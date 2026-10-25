# Spike S0b results: at equal size, the board still wins

Run 2026-10-25 on the Ark agent plan. Same 10 trajectories, 199 questions, answerer
(`deepseek-v4-pro`) and judge (`kimi-k3`) as S0. Method: `s0b-plan.md`. Raw table:
`spikes/s0/report_s0b.md`.

## Result

| budget (allowance) | arm | achieved tokens (mean) | recall | identifier | decision | dead end | state | board beats summary on |
|---|---|---|---|---|---|---|---|---|
| 2k | summary | 1,715 | 65.3 | 72 | 73 | 39.8 | 76 | |
| 2k | board (pro scribe) | 2,040 | **79.9** | 82 | 88 | 63.3 | 86 | 8/10 traj |
| 2k | board (flash scribe) | 1,946 | **84.9** | 86 | 92 | 70.4 | 91 | 10/10 |
| 5k | summary | 2,422 | 68.3 | 72 | 85 | 50.0 | 66 | |
| 5k | board (pro) | 3,722 | 87.2 | 82 | 92 | 82.7 | 92 | 9/10 |
| 5k | board (flash) | 4,057 | 88.4 | 86 | 95 | 78.6 | 94 | 10/10 |
| 10k | summary | 2,473 | 66.6 | 70 | 86 | 46.9 | 63 | |
| 10k | board (pro) | 5,173 | 89.4 | 92 | 95 | 82.7 | 88 | 10/10 |
| 10k | board (flash) | 4,167 | 86.4 | 82 | 90 | 81.6 | 92 | 9/10 |

For reference (S0, uncompressed): raw transcript 96.5%; full boards 95–97% at 22–34k tokens.

## Reading

1. **Structure does the work, not size.** At the 2k allowance the arms are nearly the same size
   (board 1.9–2.0k tokens, summary 1.7k), and the board recalls **15–20 points more**. The board at
   ~2.0k tokens also beats the summary at ~2.4–2.5k (the 5k/10k allowances). Even where the board
   is *smaller*, it wins. By the plan's rule: **"board ≥ summary at 2k and 5k → ADR 0001's cost
   case stands."**
2. **The summary doesn't use extra room.** Given 5k or 10k it still writes about 2.4k tokens, and
   recall stays flat (65 → 68 → 67). The board keeps improving with budget (80/85 → 87/88 → 89/86),
   because more pages stay verbatim.
3. **Dead ends remain the clearest gap.** At 2k the board keeps 63–70% against the summary's 40%.
   Digesting each page once preserves "tried X, failed because Y" much better than rewriting a
   summary at every fold.
4. **The cheap scribe is fine once digested.** At 2k and 5k the flash board (digested by the pro
   model) matches or beats the pro board. Its verbosity becomes raw material for the digest.
   S0's verbatim-hallucination concern about flash still stands for undigested pages.

## Fairness notes

- Both S0b arms got the same anti-role-play closing line and a hard length limit. This lifted the
  summary baseline from 60.1% (S0) to 65–68%. The comparison above is the fairer one.
- **Budgets are allowances, not exact sizes.** Neither arm fills 5k or 10k. Compare by achieved
  tokens; the 2k row is the closest to equal size.
- **Digests were built once, at the end,** from the final board. That matches the online
  design (a page is digested once, when it ages out), but the digest writer saw only that page's
  cards, not later context.
- **No retrieval** (`board_read(id)`) for the board. In the real design the agent can fetch a card
  by id, so these board numbers are a floor.
- **Hand spot check:** 7 of 8 sampled judge grades at 2k agree with my reading; the one
  disagreement was lenient *towards the summary*.
- **Harness hiccups:** two Ark network drops on long calls were resumed from cache with no data
  loss. The safety token cap was raised from 40M to 60M (flat-rate plan) after a discarded first
  build. Total ledger: 47.8M tokens (S0 + S0b).
- **Same caveats as S0:** n = 10, one scaffold and domain, DeepSeek writers. This measures memory,
  not task success.

## Implication for ADR 0001

The value case holds at equal token budget. A board with second-level folding beat recursive
summaries by 15–20 points at ~2k tokens, and by ~20 points at 4–5k. The remaining unknown is
**task success** in a live agent loop (S1), plus Claude-specific behavior (preserved thinking,
caching prices).
