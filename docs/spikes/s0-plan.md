# Spike S0: does a board keep what the agent will need later?

Status: **done** 2026-10-25. Results: `s0-results.md`. Timebox: 2 days of work. Spike code is deleted afterwards,
and the results go into ADR 0001.

## Question

After several compactions, can the agent still answer questions about early details from **the
board** at least as well as from **a rewritten summary**? This tests F5 (lossy compression), the
assumption most likely to sink ADR 0001.

## Transcripts (proposal)

| Source | What it is | Pros | Cons |
|---|---|---|---|
| **A. `nebius/SWE-rebench-openhands-trajectories`** (recommended) | 67,074 OpenHands agent runs on real GitHub issues. CC-BY-4.0, not gated, updated 2025-12. Sampled rows: 85–185 messages, ~40k–100k tokens each, with native `tools` and a `resolved` flag | Public, licensed, realistic tool-calling loops, long enough for 3–4 forced folds, reproducible by anyone | Not Claude-generated (Qwen3-Coder on OpenHands); coding-only |
| B. Your own Claude Code transcripts (`~/.claude/projects`) | 24 files locally. The largest is ~1.45M tokens, 912 tool calls, already compacted twice by Claude Code | Real Claude loops, the exact target use case | Private: content goes to the API and the results can't be published; contains its own compaction summaries |
| C. `nebius/SWE-agent-trajectories` (CC-BY-4.0, 2024) | Older SWE-agent scaffold | Second scaffold for variety | Older, shorter |

**Recommendation: A only.** Take a stratified sample of 10 trajectories: 5 resolved and 5 unresolved,
all ≥ 120 messages, from different repos, chosen by a fixed seed. Add B later as a private
sanity check if you want it.

## Arms

All arms see the same trajectories, cut at the same fold points (a forced fold every ~20k tokens,
at turn boundaries only).

| Arm | Context after the last fold | Writer |
|---|---|---|
| **board-haiku** | card #0 (task, verbatim) + append-only cards + handoff card | scribe `claude-haiku-5-5`, per turn |
| **board-sonnet** | same | scribe `claude-sonnet-5-5`, per turn |
| **summary** (baseline) | simple-compaction summary, rewritten at each fold from the previous summary + window | `claude-opus-5-5`, with the retention prompt the API docs recommend |
| **raw** (ceiling) | the full trajectory | n/a. Checks that each question is answerable at all |

**Scribe model: recommend `claude-haiku-5-5` as the candidate, with `claude-sonnet-5-5` as the
comparison arm.** The scribe runs once per turn, so its price dominates at scale: Haiku 5.5 costs
$0.10/$0.50 per MTok, Sonnet 5.5 $2/$10. S0 tells us whether the cheap one is good enough. The
handoff card is written by `claude-opus-5-5` from the last live window. Offline it lacks the agent's
real thinking, so it is a pessimistic stand-in.

## Questions and grading

- **Generation.** `claude-opus-5-5` reads each full raw trajectory and writes 20 questions whose
  answers sit **before the second fold**, each with a gold answer and its source message index.
  Categories, 5 each:
  1. exact identifiers (paths, function names, error strings, numbers);
  2. decisions and their reasons;
  3. dead ends (what was tried and failed);
  4. current state of the work.
- **Answering.** `claude-opus-5-5` answers every question from each arm's context in one call per
  (trajectory, arm). Allowed answer: "not in context".
- **Grading.** Exact match for category 1. For the others, `claude-sonnet-5-5` acts as a blind judge
  with the gold answer, the arm label hidden and the order shuffled. Spot-check 10% by hand.
- **Mechanical checks, no LLM:**
  - every identifier in a card must appear verbatim in the raw transcript (hallucination rate);
  - board tokens vs summary tokens (compression ratio);
  - the serialized board after fold k+1 must start byte-for-byte with the board after fold k (the
    cache-reuse property).

## Pass criteria

- **board-haiku ≥ summary** on overall recall, and **not worse by > 5 points** on any category.
- Identifier hallucination ≤ 1%.
- Prefix property holds on 100% of folds.
- If only board-sonnet passes: the design holds, but the scribe cost goes up. Record it in the ADR.
- If neither passes: ADR 0001 falls back to a view-only board (as written).

## Cost estimate

| Item | Calls / tokens | Est. |
|---|---|---|
| Scribe Haiku 5.5 | ~600 turn calls, ~1.8M in / 0.1M out | ~$0.25 |
| Scribe Sonnet 5.5 | same | ~$5 |
| Summary arm (Opus 5.5) | 40 folds, ~1M in / 80k out | ~$6 |
| Question generation (Opus 5.5) | 10 × ~65k in | ~$3 |
| Answering (4 arms) + judge | ~40 calls + judge | ~$4 |
| **Total** | | **~$18. Cap: $30.** Batch API (50% off) for everything except the per-turn scribe brings it to ~$12 |

## Implementation (throwaway)

- **Language:** Python with the official `anthropic` SDK. Hugging Face `datasets` to pull the 10
  rows. Both get verified on PyPI before install, and both go in a lockfile.
- **Layout:** `spikes/s0/` contains `sample.py`, `scribe.py`, `fold.py`, `questions.py`,
  `answer.py`, `grade.py` and `report.md`. Raw data goes in `spikes/s0/data/` (gitignored).
- **Budget guard:** each call is logged with `usage`, and the run stops at the cap.
- **Card schema (v0):** `{id:int, kind: goal|plan|action|observation|decision|error|state,
  title, body_md, verbatim:[str], refs:[int], supersedes?:int, src:[msg_idx]}`. It is serialized as
  stable markdown, with one text block per fold delta.

## Run deviations (2026-10-24, decided by the user)

- **Provider:** the run uses the user's Volcengine Ark agent plan (Anthropic-Messages-compatible
  endpoint), not the Claude API. Role mapping:

  | Role | Planned | Actual |
  |---|---|---|
  | cheap scribe | Haiku 5.5 | `deepseek-v4.1-flash` |
  | strong scribe | Sonnet 5.5 | `deepseek-v4-pro` |
  | main agent (summary baseline, handoff, answering) | Opus 5.5 | `deepseek-v4-pro` |
  | question generation and judge | Opus / Sonnet | `kimi-k3` (a different family from the writers) |

- **What still transfers:** the retention question (F5), and the mechanical checks (verbatim
  hallucination, compression, prefix property). Prompt caching works on Ark: cache reads are
  reported, so scribe cache-share numbers are meaningful.
- **What does not transfer:** Claude-specific claims (F3 preserved thinking, Claude prices). Scribe
  quality is measured for DeepSeek, not Haiku/Sonnet. S1 on the Claude API remains the confirmation.
- **Mechanics:** Ark ignores `output_config` JSON schemas, so structured output uses a forced
  single-tool call (`tool_choice: any`; `kimi-k3` rejects `{type: "tool"}`), with required keys
  validated client-side and one retry. There is no effort parameter. The plan is flat-rate, so the
  budget guard is a 40M-token cap instead of $30.
- **Fold threshold:** ~10k tokens instead of ~20k. Clipping tool output shrank the transcripts to
  30–56k tokens, and 10k keeps 3–5 folds per trajectory.
