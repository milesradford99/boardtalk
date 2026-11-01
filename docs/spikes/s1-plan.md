# Spike S1: can a scribe draw the lecture board from a real session?

Status: **run** (approved 2026-10-26, run 2026-10-26/27). Results: `s1-results.md`.

Naming: ADR 0001 and the S0 write-ups used "S1" for a live-loop task-success spike. That spike is
renamed **S2**; this change updates those references.

## Question

The board design (`docs/design/board-ui.md` §4) has only been shown with a session written by hand.
S1 asks whether a cheap scribe, watching a real agent session turn by turn, can produce that board:
design-level cards appended in order (your intent, the agent's design, evidence, open questions),
"You should know" notes, revisions as new cards, and boxes and highlights anchored to text. It also
asks the ADR 0001 question for this new board: are these fewer, higher-level cards still enough as
the model's context?

## Data

The same 10 trajectories as S0 (`spikes/s0/data/trajectories/`): `nebius/SWE-rebench-openhands-trajectories`,
CC-BY-4.0, 5 resolved and 5 unresolved, 63–100 turns each. Turns are rendered and clipped exactly as in
S0 (`render_turn`). S0's 20 recall questions per trajectory (written by `kimi-k3`, with gold answers)
are reused as they are, so no new question generation is needed.

**Limitation:** each trajectory has a single user message (the issue). S1 therefore tests intent
taken from one request, not steering added mid-session. An optional private set (B, below) covers
steering.

## Model

`deepseek-v4.1-flash` for every LLM call (scribe, judge, answering), on the Ark plan, as the user asked.
That means the judge is the same model as the scribe. To keep that honest:

- the headline checks are mechanical where possible (verbatim strings, anchors, counts);
- the judge always gets the source turns or a gold answer, never just the card;
- the user reviews three rendered boards by hand (see "Human review").

## The lecture scribe

One call per agent turn, as in live use. The input is a cacheable prefix (instructions, the task,
the board serialized so far), then the new turn. The output is a forced `emit` tool call carrying 0..n
operations. Most turns should emit nothing.

```
card:  {id, kind: intent | design | evidence | heads_up | question, title, body_md,
        verbatim: [str], src_turns: [int], revises?: id, heads_label?: str}
mark:  {type: box | highlight, card: id, snippet: str, src_turns: [int]}
```

- `heads_up` cards are the "You should know" notes: a tradeoff the agent chose without saying so, a
  limit, or a result that may be off. They come from the same call, matching the spec.
- **Append-only, checked in code** (mirrors `@boardtalk/core`): ids strictly increase; `revises` and
  `card` must name an existing card; a mark's `snippet` must occur in that card's text. Invalid
  operations are dropped and counted, never repaired by editing the board.
- Prompt rule: never one card per tool call; a card is a statement a reviewer would keep.

## Measures

| # | Measure | How | Target |
|---|---|---|---|
| 1 | **Verbatim faithfulness** | Every `verbatim` string and code chip must appear in the source corpus (task, rendered turns, decoded arguments), as in S0 | not-found ≤ 2 % (S0 flash: 1.7 %) |
| 2 | **Claim support** | Judge each card against its `src_turns`: supported, partly supported, or unsupported | ≥ 90 % supported, ≤ 3 % unsupported |
| 3 | **Intent coverage** | One call extracts the issue's atomic requirements into a gold list; the user spot-checks 2 of the 10 lists. Judge: is each requirement on an intent card? | ≥ 90 % of requirements |
| 4 | **"You should know" precision** | Judge each note: true (supported by the transcript) and not already said in the agent's own text | ≥ 70 % precise; median ≤ 3 notes per session |
| 5 | **"You should know" on failed runs** | For the 5 unresolved runs: does some note flag the real problem (e.g. the fix was never verified)? The judge gets `resolved = false` and the final turns | ≥ 3 of 5 |
| 6 | **Formality** | Judge labels each card design-level or tool-step narration; also cards per session and per turn | ≤ 10 % step narration |
| 7 | **Anchors and append-only** | Share of marks whose snippet is found; share of operations dropped as invalid | ≥ 95 % of marks valid; ≤ 5 % dropped |
| 8 | **Board as context** | Answer S0's 20 questions from three contexts: the lecture board, S0's per-turn flash board, S0's summary. Same answerer and judge for all three (flash), identifiers by exact match | Informational: decides the ADR 0001 path |
| 9 | **Live latency and cost** | Per-turn scribe latency (p50, p95) and tokens, cache-read share | p50 ≤ 15 s (brief); report the rest |

Measure 8 decides between two ADR outcomes: if the lecture board scores at least as well as the
summary, the lecture cards can be the compaction context. If not, the per-turn notes stay in the log
as context and the lecture board is a view of them.

## Rendering and human review

`render.py` turns each scribe log into the prototype's step format (agent text → caption, tool calls →
activity line, cards and marks → the board) and writes one self-contained `board.html` per trajectory,
plus an index with each board's numbers. The gallery is published as a private artifact.

**Human review:** the user looks at 3 boards (chosen by seed: 2 resolved, 1 unresolved) and answers
one question per board: "Would you keep this as the record of the session?" (yes / with fixes / no,
plus a line on why). This is the check the model judges can't replace.

## Pass criteria

S1 passes when measures 1, 2, 3 and 7 meet their targets, measure 4 or 5 meets its target, and at
least 2 of the 3 reviewed boards get "yes" or "with fixes".

If it fails:

- **Faithfulness (1, 2):** tighten citation rules and retry once.
- **Formality (6) or density:** switch to two stages: per-turn notes (S0 style) plus a lecture card
  pass every few turns that writes from the notes.
- **"You should know" (4, 5):** move it to its own side-agent pass every N turns, like the Claude Code
  mod, and measure again.

## Budget

| Item | Calls | Est. tokens |
|---|---|---|
| Lecture scribe, per turn | ~830 | ~5M in (mostly cache reads), ~0.4M out |
| Claim, formality and anchor judging | ~10 per trajectory | ~0.6M |
| Intent extraction and coverage | 20 | ~0.2M |
| "You should know" judging | 10 | ~0.2M |
| Answering and grading, 3 contexts | 60 | ~1.2M |
| **Total** | | **~8M. Cap: 15M tokens** (flat-rate plan), enforced by the S0 ledger |

## Implementation (throwaway)

- `spikes/s1/`, Python standard library only, reusing `spikes/s0/common.py` (client, ledger,
  rendering, verbatim corpus). Steps: `scribe.py`, `check.py` (mechanical measures), `judge.py`,
  `context.py` (measure 8), `render.py`, `report.md`.
- Outputs go in `spikes/s1/data/` (gitignored). The Ark key stays in `spikes/s0/.env` and is never
  printed. Runs use `env -u ANTHROPIC_BASE_URL`.
- Dry run first with the fake client, then a smoke run on 1 trajectory, then all 10.
- Results go to `docs/spikes/s1-results.md` and into `board-ui.md` and ADR 0001.

## Optional set B (private, user's call)

Two or three of the user's own Claude Code sessions, which have real steering mid-session. This is the
only way to test intent added mid-session. Their content would go to Ark, and the results could not be
published. Any session that contains a secret must be excluded or redacted first; this boardtalk
session contains the Ark key, so it is excluded. **Recommendation:** skip B in this run and decide
after seeing set A.
