# ADR 0001: The board is the agent's compressed context

Status: **accepted** 2026-10-24 by the user, as compaction-by-board. Still subject to the spike
results below.
Date: 2026-10-24
API facts are as of 2026-10 (Claude API skill, cached 2026-10-06). Re-verify before building on them.

> **Scope note (2026-10-25).** boardtalk's primary goal is to **preserve the canvas** left by a
> human–agent interaction, as a durable, readable artifact for people. This ADR covers a
> *secondary* benefit: the same append-only canvas can also serve as the agent's compressed
> context. The canvas design comes first. Nothing here may compromise it, and the
> board-as-context projector stays an optional mode.

## Context

boardtalk turns the messages of a running agent loop into an append-only whiteboard of processed
cards (see `docs/research/hyperknow-whiteboard-teardown.md`). The ambitious version: the board is
not only a view. Its text serialization **replaces raw history** in the model's context.

This ADR checks that idea against how LLMs and today's API actually work, and finds which variant
is feasible.

## Five fundamentals that constrain the design

**F1. The model is stateless; it only sees tokens.** "Memory" is whatever we put in the request.
The board's layout, colours and arrows are invisible to the model; only its *serialization* matters.
So there are two renderings of one log: a **spatial view for humans** and a **linear text for the
model**. The text serialization is the real product for the model.

**F2. Caching works on exact prefixes.** A change anywhere in the prompt invalidates everything
after it. Reads only land where an earlier request wrote a breakpoint; the lookback spans 20 blocks.
Cache reads cost 0.05× input on Opus 5.5 and 0.025× on Fable 5.1; 5-minute writes cost 1.25×.
- **Append-only text is cache-friendly. Rewritten text is a full miss.**
- A rolling summary is rewritten from scratch at every compaction, so every compaction misses.

**F3. Reasoning is bound to the exact prefix it was produced on (preserved thinking).** On Opus 5.5,
Sonnet 5.5, Haiku 5.5 and Fable 5.1, a thinking block's signature binds the `system`, the `tools` and
every earlier message.
- Editing, removing or replacing an earlier turn **while keeping later turns** invalidates every
  later thinking block. Accounts created on or after 2026-08-31 get a **400**; others can opt into
  `drop_block`.
- What stays valid: append-only histories; server-side compaction and context editing; and
  client-side **simple compaction**, which replaces the *whole* history with one summary message and
  replays nothing older.
- Keep-tail compaction, background swaps, and snipping turns out of the middle all break.

**F4. Training distribution.** Claude models are trained on long-horizon tasks using simple
compaction (summary in, continue), and the docs say it performs comparably to more elaborate
schemes. A structured board summary is close to that distribution. Cards dressed up as fake
`tool_result` blocks, or interleaved into the old transcript, are not.

**F5. Compression is lossy, and importance is only known in hindsight.** The scribe must choose what
to keep without knowing what the agent will need later. Exact tokens (paths, ids, numbers, error
strings) are where summaries fail first.

## Consequence: the naive version is infeasible

"Replace old raw messages with cards, in place, oldest first" edits earlier turns while keeping
later ones (F3). It loses the thinking blocks of every turn after the fold point (or returns a 400),
and puts the model off-distribution (F4). **Rejected.**

## Decision (proposed): compaction-by-board

The live loop stays a normal append-only transcript. The board takes over **only at compaction**,
in the one client-side shape the API supports: simple compaction.

```
request = [frozen system] [frozen tools]
          user: [board page 1][board page 2]…[board delta k]   ← append-only text blocks
                [handoff card] [current goal / last user turn]
          … then the new live window grows append-only until the next fold
```

1. **Scribe runs continuously, off the critical path.** A cheap model (Haiku-class) turns each
   completed raw turn into cards as it happens. When compaction fires, the summary already exists:
   **no compaction latency.** This is safe because the swap starts a new conversation (simple
   compaction), not a mid-transcript swap.
2. **Fold only at turn boundaries.** Never mid tool round (a `tool_use` still waiting on its
   `tool_result`).
3. **Handoff card by the main agent.** The scribe can't see the agent's reasoning (thinking is
   omitted or summarized). At fold time the main agent writes one "where I am / next step / open
   doubts" card. This is one cheap call, while its own context is still intact.
4. **The serialization is append-only too.** Each fold appends new board blocks after the old ones,
   byte-identical. The first message of conversation N+1 then starts with exactly the board blocks
   of conversation N, so the cache **re-reads the old board at 0.05× and writes only the delta**.
   Place an explicit breakpoint after the board, and append ≤20 blocks per fold so the 20-block
   lookback still finds the previous entry. This is the thing rolling summaries can't do (F2).
5. **The view may change; the log may not.** Corrections are new cards (`supersede #12 → #19`). The
   *visual* board can strike out #12. The *text* never re-renders #12, because that would rewrite the
   prefix.
6. **Nothing is lost, only moved out of context.** The raw log stays on disk. A
   `board_read(card_id)` tool, declared in the **first** request because tools are frozen (F3),
   returns a card's source messages verbatim. Cards carry `verbatim` fields for identifiers (F5).
7. **Second-level fold is rare.** When the board itself gets too big (e.g. 30% of the window), pages
   collapse into page summaries. That rewrite costs one full cache miss, but happens on a
   logarithmic schedule.
8. **Card #0 is the original task, verbatim.** It is never summarized, because drift from the
   user's actual request is the classic failure after several compactions.
9. **Model addressing borrowed from Hyperknow.** Small integer card ids, markdown bodies, and
   text-anchored marks (`#7 "snippet"`) rather than coordinates.

### Alternatives considered

| Option | Feasible? | Why not chosen |
|---|---|---|
| Naive in-place replacement | No (F3/F4) | 400s or lost thinking; off-distribution |
| View-only board + server-side context editing (`clear_tool_uses`) or server compaction | Yes, safest | Board never feeds back; doesn't test the idea. **Kept as the fallback and the eval baseline.** |
| Agent writes the board itself as tool calls (board-native) | Yes | Costs main-model tokens on every step; couples the board to one agent. Only the handoff card is borrowed from it. |
| Keep-tail (board + last N raw turns verbatim) | Only with stripped thinking or `drop_block` | Loses the reasoning of the retained turns; keep as an experiment flag |

## Costs, honestly

Per fold, with a 20k-token board growing 2k per fold, on Opus 5.5 ($4/M input, $0.20/M cache read,
$5/M 5-minute write):
- **board:** 20k × $0.20/M + 2k × $5/M ≈ **$0.014**;
- **rolling summary:** about 20k × $5/M ≈ **$0.10**, plus the summarization call's output.

Real, but small in absolute terms. **The stronger reasons are:**
- zero compaction latency;
- a summary that is structured, inspectable and correctable;
- retrieval by id instead of hoping the summary kept the detail.

**Ongoing costs:**
- one scribe call per turn, on a cheap model;
- one handoff call per fold;
- the risk of scribe omissions (F5).

## What must be proven before building UI (acceptance for this ADR)

On the same task set, the board arm must:
1. match the baseline (server compaction, or simple compaction with a rewritten summary) on task
   success, within noise;
2. use ≤ the baseline's input-token cost per completed task;
3. score at least as well on hindsight recall: questions about early details answered after ≥2 folds;
4. produce **zero** `prefix_binding_mismatch` entries with `drop_block` + `input_transformations`
   logging on (proves F3 compliance), and `"error"` in CI.

If 1 or 3 fails, fall back to the view-only board. The UI work is the same either way.

## Validation spike (timeboxed; delete the code afterwards, record the results here)

- **S0, offline and free (no API spend beyond the scribe).** Take recorded agent transcripts and
  run the scribe over them to build boards. Generate 20 hindsight questions per transcript about
  early details, and answer them from (a) the board and (b) a rewritten summary. This measures F5
  before any loop exists. It needs a transcript source the user picks.
- **S2 (was S1), minimal loop, about 10 tasks × 3 arms** (board / simple-compaction summary / server
  compaction), with a forced low compaction threshold so folds actually happen. Log task success,
  `usage.cache_read_input_tokens`, `cache_creation_input_tokens` and `input_transformations`. This
  spends API money, so it needs a budget the user sets first.
- **Out of the spike:** the UI, the second-level fold and keep-tail. They wait until S2 passes.

Self-review only. No fresh-context critic was run on this ADR. The assumptions most likely to be
wrong: (1) the size of the cache saving on real traces (measure it in S2); (2) whether a
Haiku-class scribe keeps enough exact detail (S0).

## Spike results

**S0 (2026-10-25, run on DeepSeek/Kimi via Ark; see `docs/spikes/s0-results.md`):**
- **Recall:** the board recalls early details at ~raw level (95–97%), against 60% for a rewritten
  summary. The biggest gap is dead ends: 95% vs 33%.
- **Scribe:** the strong-model scribe passes all criteria. The cheap scribe fails the verbatim bar
  (1.7% likely-fabricated identifiers) and loses 2.3% of turns.
- **Cache:** the prefix property held on 100% of folds, and scribes read 90%+ of their input from
  cache.
- **Open:** the boards were 61–95% the size of the raw text they replace, against 5.6% for the
  summary. S0 therefore does not show a win at equal token budget. That is S0b's question, and it
  gates the ADR's cost claims (the "Costs, honestly" section above assumed a board much smaller
  than raw).

**S0b (2026-10-25, equal budget; see `docs/spikes/s0b-results.md`):**
- **2k allowance, near-equal size:** at ~2k tokens (board 1.9–2.0k, summary 1.7k), the board with
  a second-level fold recalls 80–85% against 65% for the recursive summary, and wins on 8–10 of 10
  trajectories.
- **Larger allowances:** at 4–5k the board reaches 86–89%, while the summary stays at ~67%
  because it doesn't use the extra room.
- **Verdict:** structure, not size, drives the gap, so the cost case above stands. Still open:
  task success in a live loop (S2) and Claude-specific behavior.

**S1 (2026-10-27, lecture board; see `docs/spikes/s1-results.md`):**
- **Memory:** design-level lecture cards (~2.7k tokens) recall 58.8 %, the same as the summary and
  38 points below the per-turn board (97.2 %). The per-turn notes therefore stay the model's
  context (with S0b's digest at folds), and the lecture board is a view for the human.
- **View quality:** 1.1 % step narration, 93 % precise "You should know" notes, but claim support
  (61 %), verbatim (3.8 % missing) and intent coverage (65 %) miss their bars. Next: a two-stage
  scribe that writes lecture cards from the per-turn notes.

**S1b (2026-10-27, two-stage; see `docs/spikes/s1b-results.md`):**
- Writing lecture cards from the per-turn notes, citing note ids, raises claim support from 61 % to
  84 % with 0 % unsupported, and cuts the cards by a third. Every remaining verbatim miss comes
  from the notes themselves.
- **Decision proposed:** two stages. Per-turn notes are the memory and the lecture's source; the
  lecture is the human's view. Before S2: check note strings against the turn at note time, retry a
  rejected lecture card once, and write intent in one dedicated call.

## How to reverse

The board writer and the context projector are separate modules. Turning the projector off leaves a
view-only board over a normally compacted agent, with no data migration.

## Open questions (user's call)

- Which agent loop to attach to first: our own minimal Messages-API loop, or an existing harness
  (Claude Agent SDK / Claude Code transcripts)? Existing harnesses manage their own compaction, so
  board-as-context needs our own loop. A view-only board can attach to anything.
- Scribe model and budget.
- Profile: hobby or serious.
